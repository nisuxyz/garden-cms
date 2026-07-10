# Admin-defined custom request handlers + SMTP email backend

## Summary

Garden CMS currently has no mechanism for handling form submissions on the public site. The seeded Contact page used to POST to `/contact` but no handler existed — the form was replaced with a static placeholder during the de-slopping pass. This issue tracks the design and implementation of a system that lets admins define custom request handlers (e.g. contact forms, newsletter signups) through the admin UI, with an SMTP email backend for delivery.

## Background

During the de-slopping pass (commit a686354), the dead `/contact` form was removed. The user wants a general-purpose handler system rather than a hardcoded contact endpoint. The agreed scope for this pass deferred the feature; this issue is the follow-up.

## Proposed design

### Handler capabilities (TBD — pick one)

1. **Form submission capture only** (recommended starting point)
   - Handlers receive validated form fields and can: store submissions to a DB table, send email via configured SMTP, and return a success/redirect.
   - Define via a structured form-builder UI (field schema + response action), not freeform code.
   - No arbitrary code execution.

2. **Restricted Python via RestrictedPython**
   - Admin writes a Python snippet executed in a RestrictedPython sandbox (no imports, no file/IO access, bounded builtins).
   - Can call a curated API surface (`save_submission`, `send_email`, `log`).
   - More flexible, larger surface to audit.

3. **Isolated subprocess / Pyodide / WASM runtime**
   - Handlers run in a fully isolated runtime.
   - Most secure, most complex to implement and ship.

### SMTP/email backend

Reuse the existing S3-style config pattern: SMTP host/port/user/pass/sender in env vars or admin settings (secret write-only, like `s3_secret_access_key`). Adds a dependency (`aiosmtplib` or similar).

| Variable         | Description                  | Default     |
| ---------------- | ---------------------------- | ----------- |
| `SMTP_HOST`      | SMTP server hostname         | _(unset)_   |
| `SMTP_PORT`      | SMTP server port             | `587`       |
| `SMTP_USERNAME`  | SMTP auth username           | _(unset)_   |
| `SMTP_PASSWORD`  | SMTP auth password (write-only) | _(unset)_ |
| `SMTP_FROM`      | Sender email address         | _(unset)_   |
| `SMTP_USE_TLS`   | Use STARTTLS                 | `true`      |

### Data model

- `FormHandler` table: name, slug (URL path), field schema (JSON), response action (store / email / both), target email address, success redirect URL.
- `FormSubmission` table: handler FK, submitted data (JSON), IP, timestamp.

### Security considerations

- All handler endpoints must have CSRF protection (already in place for admin; needs to extend to public forms).
- Rate limiting on public form submissions.
- Field validation against the schema before processing.
- SMTP password is write-only (never echoed back in the admin UI, same pattern as S3 secret).
- If using RestrictedPython, audit the sandbox boundary carefully.

### Out of scope for this issue

- Webhook delivery (Slack/Discord/etc.) — can be a follow-up.
- File upload in forms — media uploads already exist; can be wired in later.
