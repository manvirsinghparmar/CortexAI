/**
 * Direct Postgres helpers used by the Playwright E2E suite.
 *
 * The browser tests drive the product through the UI, then these helpers assert
 * what the backend persisted for the same case marker and session.
 */
import pg from "pg";

const { Pool } = pg;

/** Quote schema/table names defensively because the helper builds a few raw SQL strings. */
function quoteIdent(value) {
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(String(value || ""))) {
        throw new Error(`Unsafe SQL identifier: ${value}`);
    }
    return `"${String(value).replaceAll('"', '""')}"`;
}

function tableRef(config, tableName) {
    return `${quoteIdent(config.dbSchema)}.${quoteIdent(tableName)}`;
}

/** Match the case marker appended to prompts and stored user messages. */
function casePattern(caseId) {
    const normalized = String(caseId || "").trim();
    return normalized ? `%case:${normalized}]%` : null;
}

function runPattern(runId) {
    return `%[e2e-run:${runId};%`;
}

/** Allow SQLAlchemy-style PostgreSQL URLs in `E2E_DATABASE_URL`. */
function normalizePgConnectionString(connectionString) {
    return String(connectionString || "")
        .replace(/^postgresql\+[A-Za-z0-9_]+:\/\//i, "postgresql://")
        .replace(/^postgres\+[A-Za-z0-9_]+:\/\//i, "postgres://");
}

export function createDbPool(config) {
    return new Pool({
        connectionString: normalizePgConnectionString(config.databaseUrl),
        max: 4,
        idleTimeoutMillis: 5_000,
    });
}

export async function verifyDbConnection(pool) {
    await pool.query("SELECT 1");
}

/**
 * Resolve request ids for one case.
 *
 * Case markers are the primary selector. Session id is only used as a fallback when
 * no case marker is available, which prevents history restoration from polluting
 * case-scoped snapshots with older rows from the same backend session.
 */
async function getCaseRequestIds(client, config, ownerId, caseId, sessionId = null) {
    const query = `
        SELECT requests.id::text AS id
        FROM ${tableRef(config, "llm_requests")} AS requests
        WHERE requests.user_id = $1::uuid
          AND (
              ($2::text IS NOT NULL AND COALESCE(requests.prompt_text, '') ILIKE $2)
              OR ($2::text IS NULL AND $3::uuid IS NOT NULL AND requests.session_id = $3::uuid)
          )
        ORDER BY requests.created_at ASC
    `;
    const result = await client.query(query, [ownerId, casePattern(caseId), sessionId]);
    return result.rows.map(row => row.id);
}

/** Find backend sessions touched by one case so cleanup can remove messages and empty sessions. */
async function getCaseSessionIds(client, config, ownerId, caseId, sessionId = null) {
    const query = `
        SELECT DISTINCT requests.session_id::text AS session_id
        FROM ${tableRef(config, "llm_requests")} AS requests
        WHERE requests.user_id = $1::uuid
          AND requests.session_id IS NOT NULL
          AND (
              ($2::text IS NOT NULL AND COALESCE(requests.prompt_text, '') ILIKE $2)
              OR ($2::text IS NULL AND $3::uuid IS NOT NULL AND requests.session_id = $3::uuid)
          )
        UNION
        SELECT DISTINCT messages.session_id::text AS session_id
        FROM ${tableRef(config, "messages")} AS messages
        JOIN ${tableRef(config, "sessions")} AS sessions
          ON sessions.id = messages.session_id
        WHERE sessions.user_id = $1::uuid
          AND (
              ($2::text IS NOT NULL AND COALESCE(messages.content, '') ILIKE $2)
              OR ($2::text IS NULL AND $3::uuid IS NOT NULL AND messages.session_id = $3::uuid)
          )
    `;
    const result = await client.query(query, [ownerId, casePattern(caseId), sessionId]);
    return result.rows.map(row => row.session_id).filter(Boolean);
}

/**
 * Direct DB backstop for case cleanup.
 *
 * The product history API removes user-visible history, but the E2E suite also has
 * to clear routing telemetry and now-empty sessions to keep shared dev databases clean.
 */
export async function cleanupCaseViaDb(pool, config, ownerId, caseId, sessionId = null) {
    const client = await pool.connect();
    try {
        await client.query("BEGIN");

        const requestIds = await getCaseRequestIds(client, config, ownerId, caseId, sessionId);
        const sessionIds = await getCaseSessionIds(client, config, ownerId, caseId, sessionId);

        if (requestIds.length > 0) {
            await client.query(`
                DELETE FROM ${tableRef(config, "routing_attempts")}
                WHERE routing_decision_id IN (
                    SELECT id
                    FROM ${tableRef(config, "routing_decisions")}
                    WHERE llm_request_id = ANY($1::uuid[])
                )
            `, [requestIds]);
            await client.query(
                `DELETE FROM ${tableRef(config, "routing_decisions")} WHERE llm_request_id = ANY($1::uuid[])`,
                [requestIds],
            );
            await client.query(
                `DELETE FROM ${tableRef(config, "llm_responses")} WHERE llm_request_id = ANY($1::uuid[])`,
                [requestIds],
            );
            await client.query(`
                DELETE FROM ${tableRef(config, "llm_requests")}
                WHERE id = ANY($1::uuid[])
                  AND user_id = $2::uuid
            `, [requestIds, ownerId]);
        }

        if (sessionIds.length > 0) {
            await client.query(
                `DELETE FROM ${tableRef(config, "messages")} WHERE session_id = ANY($1::uuid[])`,
                [sessionIds],
            );
            await client.query(`
                DELETE FROM ${tableRef(config, "sessions")} AS sessions
                WHERE sessions.id = ANY($1::uuid[])
                  AND sessions.user_id = $2::uuid
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ${tableRef(config, "llm_requests")} AS requests
                      WHERE requests.session_id = sessions.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ${tableRef(config, "messages")} AS messages
                      WHERE messages.session_id = sessions.id
                  )
            `, [sessionIds, ownerId]);
        }

        await client.query("COMMIT");
    } catch (error) {
        await client.query("ROLLBACK");
        throw error;
    } finally {
        client.release();
    }
}

/** Cleanup helper for the entire suite run, keyed by the broader run marker. */
export async function cleanupRunViaDb(pool, config, ownerId, runId) {
    const client = await pool.connect();
    try {
        await client.query("BEGIN");

        const requestQuery = `
            SELECT id::text AS id
            FROM ${tableRef(config, "llm_requests")}
            WHERE user_id = $1::uuid
              AND COALESCE(prompt_text, '') ILIKE $2
        `;
        const sessionQuery = `
            SELECT DISTINCT session_id::text AS session_id
            FROM ${tableRef(config, "llm_requests")}
            WHERE user_id = $1::uuid
              AND session_id IS NOT NULL
              AND COALESCE(prompt_text, '') ILIKE $2
            UNION
            SELECT DISTINCT messages.session_id::text AS session_id
            FROM ${tableRef(config, "messages")} AS messages
            JOIN ${tableRef(config, "sessions")} AS sessions
              ON sessions.id = messages.session_id
            WHERE sessions.user_id = $1::uuid
              AND COALESCE(messages.content, '') ILIKE $2
        `;

        const requestIds = (await client.query(requestQuery, [ownerId, runPattern(runId)])).rows.map(row => row.id);
        const sessionIds = (await client.query(sessionQuery, [ownerId, runPattern(runId)])).rows.map(row => row.session_id);

        if (requestIds.length > 0) {
            await client.query(`
                DELETE FROM ${tableRef(config, "routing_attempts")}
                WHERE routing_decision_id IN (
                    SELECT id
                    FROM ${tableRef(config, "routing_decisions")}
                    WHERE llm_request_id = ANY($1::uuid[])
                )
            `, [requestIds]);
            await client.query(
                `DELETE FROM ${tableRef(config, "routing_decisions")} WHERE llm_request_id = ANY($1::uuid[])`,
                [requestIds],
            );
            await client.query(
                `DELETE FROM ${tableRef(config, "llm_responses")} WHERE llm_request_id = ANY($1::uuid[])`,
                [requestIds],
            );
            await client.query(
                `DELETE FROM ${tableRef(config, "llm_requests")} WHERE id = ANY($1::uuid[]) AND user_id = $2::uuid`,
                [requestIds, ownerId],
            );
        }

        if (sessionIds.length > 0) {
            await client.query(
                `DELETE FROM ${tableRef(config, "messages")} WHERE session_id = ANY($1::uuid[])`,
                [sessionIds],
            );
            await client.query(`
                DELETE FROM ${tableRef(config, "sessions")} AS sessions
                WHERE sessions.id = ANY($1::uuid[])
                  AND sessions.user_id = $2::uuid
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ${tableRef(config, "llm_requests")} AS requests
                      WHERE requests.session_id = sessions.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ${tableRef(config, "messages")} AS messages
                      WHERE messages.session_id = sessions.id
                  )
            `, [sessionIds, ownerId]);
        }

        await client.query("COMMIT");
    } catch (error) {
        await client.query("ROLLBACK");
        throw error;
    } finally {
        client.release();
    }
}

/**
 * Snapshot the persisted records for one case.
 *
 * Specs use this to assert backend truth after UI actions complete.
 */
export async function getCaseSnapshot(pool, config, ownerId, caseId, sessionId = null) {
    const pattern = casePattern(caseId);

    const requestsQuery = `
        SELECT
            requests.id::text AS id,
            requests.session_id::text AS session_id,
            requests.request_group_id::text AS request_group_id,
            requests.request_id,
            requests.route_mode,
            requests.provider,
            requests.model,
            requests.prompt_text,
            requests.created_at
        FROM ${tableRef(config, "llm_requests")} AS requests
        WHERE requests.user_id = $1::uuid
          AND (
              ($2::text IS NOT NULL AND COALESCE(requests.prompt_text, '') ILIKE $2)
              OR ($2::text IS NULL AND $3::uuid IS NOT NULL AND requests.session_id = $3::uuid)
          )
        ORDER BY requests.created_at ASC, requests.id ASC
    `;

    const responsesQuery = `
        SELECT
            responses.llm_request_id::text AS llm_request_id,
            responses.total_tokens,
            responses.estimated_cost,
            responses.error_type,
            responses.error_message,
            responses.text
        FROM ${tableRef(config, "llm_responses")} AS responses
        JOIN ${tableRef(config, "llm_requests")} AS requests
          ON requests.id = responses.llm_request_id
        WHERE requests.user_id = $1::uuid
          AND (
              ($2::text IS NOT NULL AND COALESCE(requests.prompt_text, '') ILIKE $2)
              OR ($2::text IS NULL AND $3::uuid IS NOT NULL AND requests.session_id = $3::uuid)
          )
        ORDER BY requests.created_at ASC, responses.llm_request_id ASC
    `;

    const decisionsQuery = `
        SELECT
            decisions.id::text AS id,
            decisions.llm_request_id::text AS llm_request_id,
            decisions.attempt_count,
            decisions.fallback_used,
            decisions.routing_mode,
            decisions.research_mode,
            decisions.trace
        FROM ${tableRef(config, "routing_decisions")} AS decisions
        JOIN ${tableRef(config, "llm_requests")} AS requests
          ON requests.id = decisions.llm_request_id
        WHERE requests.user_id = $1::uuid
          AND (
              ($2::text IS NOT NULL AND COALESCE(requests.prompt_text, '') ILIKE $2)
              OR ($2::text IS NULL AND $3::uuid IS NOT NULL AND requests.session_id = $3::uuid)
          )
        ORDER BY requests.created_at ASC, decisions.id ASC
    `;

    const attemptsQuery = `
        SELECT
            attempts.routing_decision_id::text AS routing_decision_id,
            attempts.attempt_number,
            attempts.provider,
            attempts.model,
            attempts.validation,
            attempts.error_type,
            attempts.error_message
        FROM ${tableRef(config, "routing_attempts")} AS attempts
        JOIN ${tableRef(config, "routing_decisions")} AS decisions
          ON decisions.id = attempts.routing_decision_id
        JOIN ${tableRef(config, "llm_requests")} AS requests
          ON requests.id = decisions.llm_request_id
        WHERE requests.user_id = $1::uuid
          AND (
              ($2::text IS NOT NULL AND COALESCE(requests.prompt_text, '') ILIKE $2)
              OR ($2::text IS NULL AND $3::uuid IS NOT NULL AND requests.session_id = $3::uuid)
          )
        ORDER BY requests.created_at ASC, attempts.attempt_number ASC
    `;

    const requests = (await pool.query(requestsQuery, [ownerId, pattern, sessionId])).rows;
    const sessionIds = [...new Set(requests.map(row => row.session_id).filter(Boolean))];

    let messages = [];
    let sessions = [];
    if (sessionIds.length > 0) {
        const messagesQuery = `
            SELECT
                messages.id::text AS id,
                messages.session_id::text AS session_id,
                messages.role,
                messages.content,
                messages.created_at
            FROM ${tableRef(config, "messages")} AS messages
            WHERE messages.session_id = ANY($1::uuid[])
            ORDER BY messages.created_at ASC, messages.id ASC
        `;
        const sessionsQuery = `
            SELECT
                sessions.id::text AS id,
                sessions.user_id::text AS user_id,
                sessions.mode,
                sessions.title,
                sessions.created_at,
                sessions.updated_at
            FROM ${tableRef(config, "sessions")} AS sessions
            WHERE sessions.id = ANY($1::uuid[])
            ORDER BY sessions.created_at ASC, sessions.id ASC
        `;
        messages = (await pool.query(messagesQuery, [sessionIds])).rows;
        sessions = (await pool.query(sessionsQuery, [sessionIds])).rows;
    }

    const responses = (await pool.query(responsesQuery, [ownerId, pattern, sessionId])).rows;
    const routingDecisions = (await pool.query(decisionsQuery, [ownerId, pattern, sessionId])).rows;
    const routingAttempts = (await pool.query(attemptsQuery, [ownerId, pattern, sessionId])).rows;

    return { requests, responses, routingDecisions, routingAttempts, messages, sessions };
}

/** Find requests by a raw prompt fragment when a spec needs ad-hoc inspection. */
export async function getRequestsByPromptFragment(pool, config, ownerId, promptFragment) {
    const query = `
        SELECT
            id::text AS id,
            session_id::text AS session_id,
            request_group_id::text AS request_group_id,
            provider,
            model,
            route_mode,
            prompt_text,
            created_at
        FROM ${tableRef(config, "llm_requests")}
        WHERE user_id = $1::uuid
          AND COALESCE(prompt_text, '') ILIKE $2
        ORDER BY created_at ASC, id ASC
    `;
    return (await pool.query(query, [ownerId, `%${promptFragment}%`])).rows;
}

export async function getRequestsBySession(pool, config, ownerId, sessionId) {
    const query = `
        SELECT
            id::text AS id,
            session_id::text AS session_id,
            request_group_id::text AS request_group_id,
            provider,
            model,
            route_mode,
            prompt_text,
            created_at
        FROM ${tableRef(config, "llm_requests")}
        WHERE user_id = $1::uuid
          AND session_id = $2::uuid
        ORDER BY created_at ASC, id ASC
    `;
    return (await pool.query(query, [ownerId, sessionId])).rows;
}

/** Sum token usage for one backend session so history totals can be verified end to end. */
export async function sumTokensForSession(pool, config, ownerId, sessionId) {
    const query = `
        SELECT COALESCE(SUM(responses.total_tokens), 0) AS total_tokens
        FROM ${tableRef(config, "llm_requests")} AS requests
        JOIN ${tableRef(config, "llm_responses")} AS responses
          ON responses.llm_request_id = requests.id
        WHERE requests.user_id = $1::uuid
          AND requests.session_id = $2::uuid
    `;
    const result = await pool.query(query, [ownerId, sessionId]);
    return Number(result.rows[0]?.total_tokens || 0);
}