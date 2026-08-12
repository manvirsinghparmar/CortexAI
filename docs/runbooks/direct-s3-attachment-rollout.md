# Direct-to-S3 Attachment Production Rollout

## Production invariant

Large attachment bodies must bypass CloudFront, AWS WAF, and FastAPI:

```text
                         small metadata/control requests
Browser -------------------------------------------------> CloudFront/WAF/Cortex
                                                             |
                                                             | presigned POST
                                                             v
Browser =================================================> private S3
              10-20 MB attachment bytes

Browser -------------------------------------------------> Cortex /complete
                                                             |
                                                             v
                                                        S3 HeadObject
                                                             |
                                                             v
                                                     processing or ready
```

Direct upload does not make the bucket public. Cortex authorizes one exact,
short-lived S3 POST. The browser receives no IAM credentials and cannot choose
the bucket, object key, owner, maximum size, or policy lifetime.

Do not solve attachment failures by globally disabling WAF or increasing its
inspection limit. For CloudFront, AWS WAF inspects 16 KB by default and can be
configured only up to 64 KB, far below the product's 10-20 MB file limits. The
direct S3 path is the production solution.

## Ownership boundary

This repository contains no tracked Terraform, CloudFormation, CDK, `aws_wafv2`,
or equivalent AWS resource definitions. Do not claim that this deployment
changes AWS automatically.

| Repository work | AWS/deployment-account work |
| --- | --- |
| Direct-upload API, S3 signing/verification, runtime flags, React queue, migration, cleanup worker, logs, tests, and this runbook | Identify the production workload role; configure and verify S3 Block Public Access, CORS, IAM, bucket policy, default encryption/KMS policy, CloudTrail data events, WAF logging, and any temporary legacy-route exception |
| Optional explicit SSE-S3/SSE-KMS signed fields through the existing `ATTACHMENTS_S3_*` configuration | Choose whether bucket default encryption is sufficient or the bucket policy requires exact encryption fields; grant only the matching KMS permissions |
| Safe rollback through runtime flags | Change production environment values, restart/redeploy the service, verify health, and retain operational evidence |

No AWS mutation was performed while preparing this runbook. The local environment
does not have the AWS CLI, production account identity, bucket name, frontend
origin, web ACL identifiers, bucket policy, or KMS key. The operator must fill
and approve the following record before enabling direct upload:

| Required production fact | Recorded value/evidence |
| --- | --- |
| AWS account and Region | **Unresolved** |
| Cortex public origin, including scheme | **Unresolved** |
| Attachment bucket and key prefix | **Unresolved** |
| Effective Cortex signing principal ARN | **Unresolved** |
| Bucket Block Public Access status | **Unresolved** |
| Bucket CORS JSON | **Unresolved** |
| Bucket default encryption and optional KMS key ARN | **Unresolved** |
| Bucket policy review owner/date | **Unresolved** |
| CloudFront distribution and WAF web ACL | **Unresolved** |
| Cleanup-worker deployment owner | **Unresolved** |
| Staging smoke-test evidence | **Unresolved** |
| Production canary evidence | **Unresolved** |

## How the implemented flow works

For a five-byte `notes.txt`:

1. The browser sends only metadata to Cortex:

   ```json
   {
     "files": [
       {"filename": "notes.txt", "mime_type": "text/plain", "size_bytes": 5}
     ]
   }
   ```

2. Cortex validates the complete batch against the authenticated user's live
   entitlement and provider compatibility, creates a UUID and owner-prefixed
   key, persists `status=uploading`, and returns a presigned POST:

   ```json
   {
     "files": [
       {
         "file_id": "11111111-1111-1111-1111-111111111111",
         "status": "uploading",
         "upload": {
           "url": "https://cortex-files.s3.amazonaws.com",
           "fields": {
             "key": "attachments/users/.../11111111-1111-1111-1111-111111111111-notes.txt",
             "Content-Type": "text/plain",
             "x-amz-meta-cortex-file-id": "11111111-1111-1111-1111-111111111111",
             "policy": "...",
             "x-amz-signature": "..."
           },
           "expires_at": "2026-08-11T12:05:00Z"
         }
       }
     ]
   }
   ```

3. React adds every returned field unchanged to `FormData`, appends the file,
   and sends the form directly to S3 with `XMLHttpRequest`. It adds no custom
   HTTP request headers and does not read S3 response headers.
4. After S3 returns 2xx, React sends a body-free
   `POST /v1/files/{file_id}/complete` request to Cortex.
5. Cortex performs `HeadObject` and accepts the object only when bucket, exact
   server-owned key, nonzero exact size, exact content type, and
   `cortex-file-id` metadata match the database intent.
6. Cortex sets the file to `ready` or `processing`. Chat and Compare accept only
   the authenticated owner's `ready` file IDs.

The POST policy has exact-match conditions for key, content type, Cortex file ID,
optional configured encryption fields, and `content-length-range` from 1 through
the declared size. The form expires after the configured short lifetime.

## Repository deployment configuration

Apply the direct-upload migration before enabling the flag:

```powershell
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260811_add_direct_s3_attachment_upload.sql
```

Deploy the first production release with this safe configuration:

```dotenv
ENABLE_ATTACHMENTS=true
ATTACHMENTS_DIRECT_UPLOAD_ENABLED=false
ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=true
ATTACHMENTS_PRESIGN_TTL_SECONDS=300
ATTACHMENTS_UPLOAD_INTENT_TTL_MINUTES=30
ATTACHMENTS_FILE_TTL_HOURS=168

ATTACHMENTS_OBJECT_STORAGE_BACKEND=s3
ATTACHMENTS_S3_BUCKET=<production-private-bucket>
ATTACHMENTS_S3_REGION=<bucket-region>
ATTACHMENTS_S3_ENDPOINT_URL=
ATTACHMENTS_S3_ACCESS_KEY_ID=
ATTACHMENTS_S3_SECRET_ACCESS_KEY=
ATTACHMENTS_S3_SESSION_TOKEN=
ATTACHMENTS_S3_USE_SSL=true
ATTACHMENTS_S3_FORCE_PATH_STYLE=false
ATTACHMENTS_S3_KEY_PREFIX=attachments

# Leave blank when bucket default encryption satisfies policy.
ATTACHMENTS_S3_SERVER_SIDE_ENCRYPTION=
ATTACHMENTS_S3_SSE_KMS_KEY_ID=

ENABLE_ATTACHMENTS_CLEANUP_WORKER=true
ATTACHMENTS_CLEANUP_INTERVAL_SECONDS=300
ATTACHMENTS_CLEANUP_BATCH_SIZE=200
ATTACHMENTS_CLEANUP_MAX_ATTEMPTS=8
ATTACHMENTS_CLEANUP_RETRY_BACKOFF_SECONDS=60
```

Do not change `ATTACHMENTS_MAX_FILE_BYTES` or subscription-plan values for this
rollout. The authoritative plan limits remain in `config/subscription_plans.yaml`
(approximately Free: one 10 MB file; Plus: three 20 MB files; Pro: five 20 MB
files).

In production, leave static credential variables blank so boto3 uses its normal
credential provider chain and the EC2 instance profile/task/workload role. Never
put permanent access keys, session tokens, presigned fields, policies, or
signatures in frontend configuration or logs.

For MinIO/local S3, set the existing endpoint override and enable path-style
addressing when that server requires it. Verify that server's POST-policy and
CORS implementation before enabling direct mode locally. If it is incompatible,
keep direct mode off and legacy proxy upload on in that environment; do not add a
second storage stack.

## AWS read-only discovery before any change

Run these from the production Cortex host or with the same assumed role. They are
read-only. Record the command output in the deployment ticket without recording
credentials or signed forms.

```bash
export CORTEX_BUCKET='<production-private-bucket>'

aws sts get-caller-identity
python -c "import boto3; c=boto3.Session().get_credentials(); print(c.method if c else 'no-credentials')"
aws s3api get-bucket-location --bucket "$CORTEX_BUCKET"
aws s3api get-public-access-block --bucket "$CORTEX_BUCKET"
aws s3api get-bucket-policy-status --bucket "$CORTEX_BUCKET"
aws s3api get-bucket-cors --bucket "$CORTEX_BUCKET"
aws s3api get-bucket-encryption --bucket "$CORTEX_BUCKET"
aws s3api get-bucket-policy --bucket "$CORTEX_BUCKET" --query Policy --output text
```

Expected identity evidence is an assumed workload role, not an IAM user with a
long-lived access key. A missing CORS configuration before Phase 2 is expected;
it must exist before direct upload is enabled.

## S3 bucket privacy

Keep all four S3 Block Public Access controls enabled at the effective
organization/account/bucket level where compatible with the existing account:

- `BlockPublicAcls=true`
- `IgnorePublicAcls=true`
- `BlockPublicPolicy=true`
- `RestrictPublicBuckets=true`

Do not add `public-read` ACL fields, public principals, public object URLs, or
browser `ListBucket` permission. The presigned POST delegates only one constrained
`PutObject` request from the Cortex signing principal. CORS does not grant S3
authorization and does not make the bucket public.

## Exact production S3 CORS shape

Replace the origin placeholder with the exact production Cortex origin. Do not
include a trailing path. This React implementation performs only browser `POST`,
sets only the browser-generated multipart content type, and reads no S3 response
headers, so `GET`, `PUT`, `DELETE`, wildcard origins, wildcard headers, and
exposed headers are not required:

```json
[
  {
    "AllowedOrigins": [
      "https://<production-cortex-domain>"
    ],
    "AllowedMethods": [
      "POST"
    ],
    "AllowedHeaders": [
      "content-type"
    ],
    "MaxAgeSeconds": 300
  }
]
```

Use separate staging and production buckets where possible. If one bucket must
serve both, add only the exact staging origin. Add local origins only to a
non-production bucket. If browser developer tools show an `OPTIONS` preflight
with another `Access-Control-Request-Headers` value, review the client request
and add only that exact required header; do not replace the list with `*` by
default.

After configuring CORS, re-run `get-bucket-cors` and save the returned JSON as
deployment evidence. A CORS error is a browser policy failure; it is not evidence
that IAM or the bucket policy allowed the object write.

## Presigned POST and encryption

Production must continue using presigned POST, not presigned PUT. The repository
signs:

- one exact server-generated key under
  `<prefix>/users/<authenticated-user-id>/YYYY/MM/DD/`;
- the normalized expected `Content-Type`;
- `x-amz-meta-cortex-file-id` equal to the database UUID;
- `content-length-range` from 1 to the declared/authorized size;
- a default 300-second expiration;
- optional exact encryption fields when configured.

S3 POST MIME conditions prevent changing the declared header but are not content
malware detection. Preserve the existing server-side parsing/ingestion safeguards.

Preserve the bucket's current encryption:

| Bucket policy/encryption design | Cortex configuration |
| --- | --- |
| Bucket default SSE-S3 and no explicit encryption-header deny | Leave both encryption variables blank; S3 applies the bucket default |
| Bucket default SSE-KMS and no explicit encryption-header deny | Leave both blank; verify the workload role and KMS key policy permit required reads/writes |
| Policy requires explicit SSE-S3 | `ATTACHMENTS_S3_SERVER_SIDE_ENCRYPTION=AES256`; leave KMS key ID blank |
| Policy requires explicit SSE-KMS | `ATTACHMENTS_S3_SERVER_SIDE_ENCRYPTION=aws:kms` and `ATTACHMENTS_S3_SSE_KMS_KEY_ID=<approved-key-arn>` |

When explicit values are set, Cortex includes them as exact POST fields and
conditions; React already submits every returned signed field unchanged. The
same configuration is used by legacy server-side `PutObject` calls. Do not weaken
encryption or remove a protective bucket-policy deny to make uploads pass.

## Least-privilege IAM

The browser does not receive IAM credentials. The role used by Cortex to sign the
form is the effective principal for the S3 POST. That same application also
performs metadata verification, content reads for ingestion, and deletion.

Scope the workload role to the one attachment prefix. No `s3:ListBucket` or
`s3:*` is required:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CortexAttachmentObjects",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::<production-private-bucket>/attachments/users/*"
    }
  ]
}
```

`HeadObject` uses `s3:GetObject`; there is no separate `s3:HeadObject` IAM
action. Do not add `ListBucket` just to turn a missing-object 403 into 404—the
application safely normalizes its expected S3 errors.

For a customer-managed SSE-KMS key, grant the same role and the KMS key policy
only what the chosen flow requires. `PutObject` with SSE-KMS requires
`kms:GenerateDataKey`; downloading for document ingestion requires
`kms:Decrypt`. Validate both the IAM policy and key policy. Do not grant
`kms:*` or access to unrelated keys.

## Bucket-policy compatibility review

Review every allow and explicit deny before enabling direct upload. Preserve:

- `aws:SecureTransport=false` denial;
- required server-side-encryption algorithm/key conditions;
- the private bucket and approved workload principal;
- organization/security-team controls.

Resolve these common incompatibilities without deleting broad security controls:

- If the policy requires explicit encryption fields, set the Cortex encryption
  variables so the fields are included in the signed form.
- A blanket `aws:SourceVpc`, `aws:SourceVpce`, or private-network deny can reject
  an internet browser's direct S3 request even though the workload role signed
  it. Treat this as an architecture/security review blocker. Use an approved
  narrow policy design for the exact role and attachment prefix, or do not enable
  direct browser upload.
- Confirm any `Principal`, organization ID, object ownership, or ACL conditions
  accept a POST signed by the recorded Cortex role without public ACL fields.
- Confirm the selected KMS key policy accepts the recorded role.

Test with a non-sensitive staging object. Do not change a production bucket policy
merely to make a smoke test pass.

## CloudFront, WAF, and Shield

Keep CloudFront/WAF/Shield in front of Cortex. The direct flow sends only small
control-plane requests through that path:

- `POST /v1/files/upload-intents`: small JSON metadata;
- `POST /v1/files/{file_id}/complete`: no attachment body;
- `GET /v1/files/{file_id}` and `DELETE /v1/files/{file_id}`: no attachment body.

The legacy `/v1/files/upload` and `/v1/files/upload-batch` routes still proxy
large bodies while the compatibility flag is on. Do not create a blanket allow
for `/v1/files/*` and do not disable a managed rule group globally.

Only if WAF logs prove that a specific size rule blocks required legacy traffic,
create a temporary exception with all of these properties:

1. matches only `/v1/files/upload` and `/v1/files/upload-batch`;
2. overrides only the proven body-size rule, not unrelated managed protections;
3. retains normal authentication, rate, IP, and other managed rules;
4. has an owner, expiry/removal ticket, and rollback action;
5. is removed after `ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=false`.

One safe design pattern is to override only the proven managed size rule to
`Count`, then add a later custom block using its emitted label for all paths
except the two exact legacy routes. Copy the actual rule label from WAF logs and
test the complete web ACL; do not hard-code a guessed managed-rule label.

Enable WAF traffic logging. Useful fields include `action`,
`terminatingRuleId`, labels/matched details, `httpRequest.uri`, method, and
request ID. CloudWatch Logs Insights example:

```text
fields @timestamp, action, terminatingRuleId,
       httpRequest.httpMethod, httpRequest.uri, httpRequest.requestId
| filter httpRequest.uri like /\/v1\/files\//
| sort @timestamp desc
| limit 100
```

Interpret the result:

- `BLOCK`: WAF stopped the metadata/completion/legacy request; inspect the exact
  terminating rule and labels.
- `ALLOW` followed by Cortex 4xx: the request reached the app; correlate
  `X-Request-ID` with `upload.*` logs.
- No WAF entry for the large S3 POST is correct. Those bytes must not traverse
  the Cortex web ACL.

## Cleanup worker production gate

Direct upload creates `uploading` rows before S3 receives bytes. A closed tab,
cancelled transfer, or expired form can abandon both a row and an object. Run the
existing worker; do not create a second cleanup implementation.

The integrated worker starts when
`ENABLE_ATTACHMENTS_CLEANUP_WORKER=true`. The standalone alternative is:

```powershell
python scripts/attachment_cleanup_job.py --loop --interval-seconds 300 --limit 200
```

Run one effective worker/service for a queue unless the deployment has separately
validated multi-process ownership. Do not start the integrated worker in every
horizontally scaled API process and also run the standalone script without an
explicit concurrency review.

Verify startup/cycle events:

```text
upload.cleanup.worker.started
upload.cleanup.cycle.completed
upload.cleanup.cycle.failed
```

Safe database health queries:

```sql
SELECT status, COUNT(*)
FROM public.uploaded_files
GROUP BY status
ORDER BY status;

SELECT COUNT(*) AS abandoned_uploading
FROM public.uploaded_files
WHERE status = 'uploading' AND expires_at <= NOW();

SELECT status, COUNT(*), MAX(attempt_count) AS max_attempts
FROM public.file_deletion_queue
GROUP BY status
ORDER BY status;
```

Expected behavior is: expired `uploading` rows are marked `expired`, a deletion
job is enqueued idempotently, an existing object is deleted when present, the row
reaches `deleted`, and transient failures use exponential retry until the
configured attempt cap. Alert on sustained abandoned rows, retry growth,
`delete_failed`, or cleanup-cycle failure.

## Controlled deployment sequence

### Phase 1: backward-compatible database/backend deploy

1. Back up/verify the database according to the migration runbook.
2. Apply `20260811_add_direct_s3_attachment_upload.sql`.
3. Deploy backend/frontend with direct off, legacy on, and cleanup running.
4. Verify startup schema preflight, application health, legacy upload, existing
   attachment reads, and ready attachments in Chat and Compare.
5. Confirm `GET /runtime-config.js` reports direct false and legacy true.

### Phase 2: AWS configuration

1. Record the actual Cortex principal with STS.
2. Verify private-bucket public-access settings.
3. apply the exact approved CORS origin/method/header configuration;
4. apply least-privilege S3 role access and conditional KMS permissions;
5. review bucket/KMS policies and encryption behavior;
6. enable WAF logging and approved S3 audit events;
7. verify POST, `HeadObject`, `GetObject`, and `DeleteObject` with a controlled
   staging object;
8. prove expired, oversized, changed-key, changed-MIME, and changed-signed-field
   POSTs are rejected.

### Phase 3: staging/controlled enablement

Set:

```dotenv
ATTACHMENTS_DIRECT_UPLOAD_ENABLED=true
ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=true
```

Restart/redeploy Cortex and verify `/runtime-config.js` reports both capabilities
true. Exercise Free, Plus, Pro, PDF, Office processing, multiple files, failure,
cancel, retry, remove, Chat, and Compare scenarios.

### Phase 4: mandatory network-path proof

In browser developer tools, select a real 10-20 MB permitted attachment and
inspect the Network tab:

1. `/v1/files/upload-intents` is small JSON.
2. The large request host is the configured S3 endpoint and the method is POST.
3. `/v1/files/{file_id}/complete` is small/body-free.
4. No large `/v1/files/upload` or `/v1/files/upload-batch` request occurs.
5. WAF logs show only Cortex control calls; S3 audit evidence shows object
   activity.

Do not approve production if the attachment body still crosses CloudFront/WAF.

### Phase 5: production canary and enablement

Enable direct mode for the smallest supported production cohort or window. Keep
legacy mode available. Monitor intent creation, S3/CORS/signature failures,
completion reasons, processing duration, abandoned uploads, cleanup/delete
failures, Chat/Compare readiness errors, and WAF activity.

### Phase 6: legacy proxy disablement

Only after the stability window and client inventory are approved, set:

```dotenv
ATTACHMENTS_DIRECT_UPLOAD_ENABLED=true
ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=false
```

Verify old routes return the documented feature-disabled response, then remove
the temporary WAF exception. Source removal of legacy endpoints is a separate
cleanup task.

## Security verification checklist

- [ ] Effective signing identity is an approved workload role using temporary
      credentials.
- [ ] Block Public Access remains enabled; bucket policy status is not public.
- [ ] Role has only Put/Get/Delete on the attachment object prefix.
- [ ] Browser cannot list the bucket or read a private object directly.
- [ ] Intent key contains the authenticated user ID plus a server UUID.
- [ ] Replacing the key with another user's prefix makes S3 reject the POST.
- [ ] Increasing the file past the signed range makes S3 reject it.
- [ ] Changing content type, Cortex file ID metadata, encryption value, KMS key,
      policy, credential, date, or signature makes S3 reject it.
- [ ] Waiting past 300 seconds makes the signed POST fail.
- [ ] Completing another user's file returns not found/denied and changes no row.
- [ ] Completion rejects wrong size/type/metadata and accepts only exact object
      metadata.
- [ ] Existing file parsing/type safeguards remain enabled.
- [ ] Application, WAF, CloudTrail export, support screenshots, and deployment
      evidence contain no policy, signature, token, credentials, or file bytes.

Perform tamper tests only with non-sensitive staging fixtures. Browser devtools
may display signed form fields to the authenticated user who requested them;
never copy those values into tickets or logs.

## Observability

The server cannot report byte-by-byte S3 transfer progress because the bytes do
not pass through it. React progress is client-side only. Server evidence should
distinguish the control-plane lifecycle:

| Stage | Evidence |
| --- | --- |
| intent created | `upload.intent.created`, `storage.presign_post.success` |
| S3 transfer | Browser network timing; optional CloudTrail S3 `PutObject` data event |
| completion pending/rejected/verified | `upload.completion.pending`, `upload.completion.rejected`, `upload.completion.verified`, idempotent retry event |
| processing/ready/failed | `upload.ingestion.*` and `upload.status.lookup.success` status |
| expired/deleted | cleanup cycle stats, uploaded-file state, deletion queue, `storage.delete.*` |

Never log or meter signed fields. Useful aggregate metrics are intent count,
completion success rate/reason, completion latency, processing duration,
expired abandoned-intent count, and delete retries/failures.

Enable CloudTrail **S3 object data events** for the attachment bucket during
staging and according to production audit/cost policy. Data events are not on by
default and do not appear in normal Event history. Use them for `PutObject`,
`GetObject`, and `DeleteObject` investigation:

- no `PutObject`: inspect browser network/CORS, expiry, DNS, CSP, or cancellation;
- denied `PutObject`: inspect the event identity, role/bucket/KMS policy, and
  exact POST conditions;
- successful `PutObject` plus missing completion: compare the bucket and safe
  hashed-key Cortex logs without exporting the signed form;
- successful `PutObject` plus mismatch: inspect object size, content type, and
  Cortex file ID metadata.

Restrict audit access and retention because object keys contain user/file
identifiers. Do not enable object-content logging.

## Manual smoke-test procedure

Use non-sensitive fixtures and an authenticated session for each effective plan.
Capture the Cortex request ID, timestamps, status codes, destination host, final
file state, and safe AWS event IDs—never signed form fields.

### Free

1. Upload a small PDF under 10 MB.
2. Verify browser `POST -> S3`, body-free completion, `ready`, and successful use
   in an Ask prompt.
3. Select a file over the effective Free limit.
4. Verify Cortex rejects the metadata batch before an intent/S3 authorization is
   returned and no S3 object is created.

### Plus and Pro

Upload multiple files up to each effective count/size limit. Verify no more than
two S3 transfers run concurrently, partial sibling success remains visible, and
all ready file IDs work in Ask and Compare.

### Office document

Upload one DOCX, PPTX, or XLSX large enough to enter `processing`. Verify bounded
polling reaches `ready`, then use it in Chat and Compare.

### Failure, retry, remove, and cancel

1. Cause a controlled staging S3 failure and verify only that file fails.
2. Retry and confirm Cortex issues a fresh intent/form.
3. Start a large upload, cancel/remove it, and confirm XHR aborts and deletion is
   queued.
4. Close the browser after intent creation; after the intent TTL and cleanup
   cycle, verify the row/object reach the expired/deleted lifecycle.

### Expiry and tampering

1. Generate an intent and wait beyond the 300-second form expiration before
   sending it; S3 must reject it.
2. In staging, replay a form while changing one item at a time: key, content
   type, metadata file ID, file size, encryption field, or KMS key field.
3. Verify each signed-policy violation fails and Cortex never promotes the row
   to ready.

## Troubleshooting matrix

| Symptom | Boundary | First checks | Expected action |
| --- | --- | --- | --- |
| Cortex 4xx from `/upload-intents` | Application validation/auth/plan | Response code, safe detail code, request ID, entitlement and MIME/count/size | Correct request/plan; do not change WAF or S3 |
| Cortex 5xx/502 authorizing intent | Cortex storage configuration/signing identity | `storage.client.initialized`, `storage.presign_post.failure`, role credentials, bucket/Region | Fix role/config; do not expose provider exception to client |
| Browser CORS error | Browser to S3 | Exact page origin, bucket CORS, OPTIONS request, CSP, S3 host | Correct only the required origin/method/header |
| S3 `AccessDenied` | S3 IAM/bucket/KMS policy | STS identity, object-prefix resource, explicit denies, KMS key policy, encryption fields | Fix least-privilege policy or signed fields; never make bucket public |
| S3 `SignatureDoesNotMatch` | Signed form modified or generated for wrong endpoint/Region/time | Bucket Region, client clock, exact unchanged fields, form expiry | Obtain a fresh intent; do not log the form |
| S3 policy size rejection | Signed `content-length-range` | Declared versus actual file size and effective plan limit | Select valid file; do not raise WAF limit |
| Completion `attachment_upload_not_complete` | S3 object not visible at exact key yet | Browser S3 status, CloudTrail PutObject, expiry, safe key hash | Retry completion briefly or retry upload |
| Completion `attachment_upload_mismatch` | Exact HEAD verification | Object size/type/file-ID metadata and bucket/key configuration | Delete/retry with a fresh intent; investigate tampering/client drift |
| Processing remains pending or fails | Ingestion | `upload.ingestion.*`, object read/KMS decrypt, parser error, status polling | Fix ingestion/KMS read permission; do not bypass readiness gating |
| `attachment_file_not_ready` in Chat/Compare | File lifecycle | File status and whether completion/processing reached ready | Wait/retry/remove; only ready IDs are valid |
| Delete queue retries/fails | Cleanup/S3 | cleanup events, queue attempts, role `DeleteObject`, KMS/bucket denies | Fix worker/permission; preserve retry and alerting |
| WAF block on new direct endpoints | Edge | WAF action, terminating rule, labels, request URI/ID | Fix only the proven small control request issue |
| Large request still targets Cortex | Client rollout/runtime config | `/runtime-config.js`, deployed asset version, Network destination | Stop rollout; restore flags/assets until direct client is active |

## Rollback

During the transition, rollback is configuration-only:

```dotenv
ATTACHMENTS_DIRECT_UPLOAD_ENABLED=false
ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=true
```

1. Change both values together and restart/redeploy Cortex.
2. Verify `/runtime-config.js` reports direct false and legacy true.
3. Verify a supported legacy upload and existing ready attachment in Chat/Compare.
4. Keep the cleanup worker enabled so abandoned direct intents/objects expire.
5. Keep the migration applied. Do not restore `sha256 NOT NULL` while direct
   upload rows may have `sha256=NULL`.
6. Leave private-bucket, CORS, IAM, and encryption protections in place unless a
   separately reviewed security change removes now-unused permissions.

No database rollback is required. Existing `uploading` rows remain compatible
and are cleaned after the intent TTL. If legacy mode had already been disabled,
restore it before disabling direct mode.

## Production exit gates

- [ ] All unresolved production facts at the top of this runbook are filled.
- [ ] Migration and startup schema preflight pass with direct mode still off.
- [ ] Old upload and existing attachments pass backward-compatibility smoke.
- [ ] Private bucket, exact CORS, role, bucket policy, and encryption/KMS evidence
      are approved.
- [ ] Valid and invalid/tampered presigned POST tests pass in staging.
- [ ] Cleanup worker and database health queries are healthy.
- [ ] Browser network proof shows large bytes go only to S3.
- [ ] Required repository tests/build/E2E gates pass.
- [ ] Production canary monitoring and rollback owner are assigned.
- [ ] Legacy mode stays on until client inventory and stability window are
      approved.
- [ ] Any temporary WAF exception has an owner and removal ticket.

## AWS references

- [AWS WAF request-body inspection limits](https://docs.aws.amazon.com/waf/latest/developerguide/web-acl-setting-body-inspection-limit.html)
- [AWS WAF quotas](https://docs.aws.amazon.com/waf/latest/developerguide/limits.html)
- [S3 POST policy conditions](https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html)
- [S3 CORS configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enabling-cors-examples.html)
- [S3 Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)
- [S3 HeadObject permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)
- [SSE-KMS permissions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html)
- [EC2 workload-role temporary credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-ec2.html)
- [AWS WAF traffic logging](https://docs.aws.amazon.com/waf/latest/developerguide/logging.html)
- [AWS WAF log fields](https://docs.aws.amazon.com/waf/latest/developerguide/logging-fields.html)
- [CloudTrail S3 object data events](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudtrail-logging-s3-info.html)
