# Direct-to-S3 Attachment Rollout

## Outcome

The browser uploads attachment bytes directly to the private S3 bucket. Cortex
and the WAF-protected origin receive only two small requests: upload metadata
and completion. AWS Shield/WAF protection stays in front of Cortex; removing
file bytes from that path avoids WAF body-size and multipart inspection failures
without broadly weakening the web ACL.

```text
Browser -- small JSON --> Cortex /upload-intents
Browser -- file bytes --> private S3 (presigned POST)
Browser -- no body ----> Cortex /{file_id}/complete
                              |
                              +-- S3 HeadObject verification
```

This repository implements the Cortex/database side. It does not contain AWS
IaC, so bucket CORS, IAM, CloudTrail data events, WAF logging, and the actual
environment values must be configured in the deployment account.

## Simple example

For a five-byte `notes.txt`:

1. Browser sends:

   ```json
   {
     "files": [
       {"filename": "notes.txt", "mime_type": "text/plain", "size_bytes": 5}
     ]
   }
   ```

2. Cortex checks the user's plan/MIME/size, chooses a UUID and key, and returns:

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

3. Browser adds every returned field unchanged to `FormData`, adds the actual
   file, then POSTs the form to `upload.url`.
4. After S3 returns success, browser calls
   `POST /v1/files/11111111-1111-1111-1111-111111111111/complete`.
5. Cortex performs `HeadObject`. It accepts the file only when the object is
   nonempty and its key, bucket, exact five-byte size, `text/plain` content
   type, and `cortex-file-id` metadata all match the database intent.

The POST policy uses exact-match conditions for key, content type, and Cortex
file ID plus `content-length-range` from 1 through the declared size. See the
[AWS S3 POST policy conditions](https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sigv4-HTTPPOSTConstructPolicy.html).

## Required database and application configuration

Apply the migration before enabling direct upload:

```powershell
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260811_add_direct_s3_attachment_upload.sql
```

Start the rollout with:

```dotenv
ENABLE_ATTACHMENTS=true
ATTACHMENTS_DIRECT_UPLOAD_ENABLED=false
ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=true
ATTACHMENTS_PRESIGN_TTL_SECONDS=300
ATTACHMENTS_UPLOAD_INTENT_TTL_MINUTES=30
ATTACHMENTS_FILE_TTL_HOURS=168
ATTACHMENTS_OBJECT_STORAGE_BACKEND=s3
ATTACHMENTS_S3_BUCKET=cortex-production-files
ATTACHMENTS_S3_REGION=us-east-1
ATTACHMENTS_S3_KEY_PREFIX=attachments
ENABLE_ATTACHMENTS_CLEANUP_WORKER=true
ATTACHMENTS_CLEANUP_INTERVAL_SECONDS=300
```

Use the EC2/ECS task role or workload role in production; do not put permanent
AWS access keys in the browser. The browser receives only a short-lived signed
form. Never log `upload.fields`, policy, signature, session token, or file bytes.

## S3 CORS

Allow only the real application origins. A production example:

```json
[
  {
    "AllowedOrigins": [
      "https://app.example.com"
    ],
    "AllowedMethods": [
      "POST"
    ],
    "AllowedHeaders": [
      "*"
    ],
    "ExposeHeaders": [
      "ETag"
    ],
    "MaxAgeSeconds": 300
  }
]
```

Add local origins only to non-production buckets. CORS permits a browser to
make the cross-origin request; it does not grant S3 permission, and bucket/IAM
authorization still applies. See the official
[S3 CORS guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enabling-cors-examples.html).

Keep Block Public Access enabled. Do not add a public-write bucket policy.

## IAM

The server role that signs the POST and verifies/processes/deletes objects needs
access only under the configured prefix. `HeadObject` is authorized by
`s3:GetObject`; there is no separate `s3:HeadObject` IAM action.

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
      "Resource": "arn:aws:s3:::cortex-production-files/attachments/users/*"
    }
  ]
}
```

If the bucket uses a customer-managed KMS key, add only the KMS permissions
required by that encryption design to the same workload role and key policy.

## WAF and Shield

Do not create a blanket WAF bypass for `/v1/files/*`. The direct flow leaves
these WAF-inspected calls small:

- `POST /v1/files/upload-intents`: JSON metadata only.
- `POST /v1/files/{file_id}/complete`: no file body.
- `DELETE /v1/files/{file_id}`: no file body.

During migration, the old `/upload` and `/upload-batch` routes can still hit WAF
body-size or multipart rules. If compatibility traffic requires an exception,
scope it to those two paths and the minimum known rule, keep it temporary, and
remove it after clients switch and
`ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=false`.

Enable web ACL traffic logging to CloudWatch Logs (or another supported WAF
destination). AWS documents the fields `action`, `terminatingRuleId`,
`httpRequest.uri`, `httpRequest.httpMethod`, and `httpRequest.requestId` in
[WAF log fields](https://docs.aws.amazon.com/waf/latest/developerguide/logging-fields.html).
Example CloudWatch Logs Insights query:

```text
fields @timestamp, action, terminatingRuleId,
       httpRequest.httpMethod, httpRequest.uri, httpRequest.requestId
| filter httpRequest.uri like /\/v1\/files\//
| sort @timestamp desc
| limit 100
```

Interpretation:

- `action = BLOCK`: WAF stopped the Cortex metadata/completion request. Inspect
  `terminatingRuleId` and any managed-rule match details.
- `action = ALLOW` followed by a Cortex 4xx: the request reached the app; use
  `X-Request-ID` and `upload.*` logs.
- No WAF row for the S3 POST is expected. The browser sent those bytes to S3,
  not through the Cortex web ACL.

AWS WAF logging is best effort and can be delivered to CloudWatch Logs, S3, or
Firehose; see [WAF traffic logging](https://docs.aws.amazon.com/waf/latest/developerguide/logging.html).

## What to do with S3 logs

Enable CloudTrail **S3 object data events** for the attachment bucket during
staging and according to production audit/cost policy. Data events are not on
by default and do not appear in normal CloudTrail Event history. They show
`PutObject`, `GetObject`, and `DeleteObject`; see
[S3 CloudTrail data events](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudtrail-logging-s3-info.html).

Use them when the browser says S3 upload failed or Cortex completion returns
`attachment_upload_not_complete`:

- No `PutObject` event: check browser network/CORS, expired form, DNS, or client
  cancellation.
- Denied `PutObject`: check the event identity, bucket policy, KMS policy, POST
  conditions, exact content type, file size, and unchanged form fields.
- Successful `PutObject` but completion says missing: compare the logged bucket
  and key with the intent's safe hashed-key Cortex logs; the client must not
  replace the returned key.
- Successful `PutObject` plus `attachment_upload_mismatch`: check actual object
  size, content type, and `x-amz-meta-cortex-file-id`.

Do not log or export file content. Limit data-event retention and access to the
operations team because object keys contain user and file identifiers.

## Rollout

1. Apply the migration and restart Cortex.
2. Configure private-bucket CORS, workload-role IAM, encryption, lifecycle/audit
   settings, WAF logging, and S3 data-event logging.
3. Deploy with direct upload off and legacy upload on. Verify old clients.
4. Set `ATTACHMENTS_DIRECT_UPLOAD_ENABLED=true` in staging. Exercise intent,
   direct S3 POST, completion, Office-file processing, delete, and abandoned
   intent cleanup.
5. Verify `/runtime-config.js` exposes `directAttachmentUploads: true`. The
   bundled React client then selects the direct sequence automatically; confirm
   Preparing/Uploading/Processing/Ready progress, pending-Send blocking,
   individual retry/remove, and partial multi-file success. The CSP permits AWS
   S3 HTTPS endpoints, but bucket CORS must still allow the real app origin.
6. Canary production users and compare upload success, latency, WAF blocks,
   completion mismatches, and abandoned intent counts.
7. After all clients are direct and rollback confidence is sufficient, set
   `ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=false` and remove temporary WAF
   exceptions for proxy-upload paths.

## Rollback

Set:

```dotenv
ATTACHMENTS_DIRECT_UPLOAD_ENABLED=false
ATTACHMENTS_LEGACY_PROXY_UPLOAD_ENABLED=true
```

After restart, `/runtime-config.js` makes React return to the legacy batch path
without changing the attachment UI. Do not disable the legacy flag during a
rollback.

No database rollback is required. Existing `uploading` rows expire after the
intent TTL and the cleanup queue removes any abandoned object. Keep the cleanup
worker running. Do not restore `sha256 NOT NULL` while checksum-free rows exist.

## Acceptance checks

- Oversized, unsupported, over-count, and provider-incompatible batches fail
  before any `uploaded_files` insert or S3 authorization is returned.
- A valid intent key contains the authenticated user ID and server UUID.
- Modifying key, MIME type, metadata, or size makes S3 reject the POST or Cortex
  reject completion.
- Completion is idempotent for `ready`/`processing`.
- Ask/Compare rejects `uploading`, `failed`, `expired`, `deleting`, and `deleted`
  file IDs; only `ready` is usable.
- Delete returns `deleting`, enqueues once, and cleanup reaches `deleted`.
- WAF logs show only small Cortex calls; CloudTrail data events show S3 object
  activity; neither application nor WAF logs contain signed form fields or file
  bytes.
