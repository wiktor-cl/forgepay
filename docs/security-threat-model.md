# Security Threat Model

ForgePay uses STRIDE to frame risks.

## Spoofing

API keys are generated with secure randomness and only SHA-256 hashes are stored. Requests use
bearer tokens and central scope checks.

## Tampering

Money-changing endpoints require idempotency keys and validate payload fingerprints. Webhooks
are signed with HMAC.

## Repudiation

Business operations append audit logs with actor, action, resource, timestamp, correlation ID,
and metadata.

## Information Disclosure

Errors use stable codes and avoid stack traces. Secrets are provided through environment variables
or Kubernetes Secret templates, not committed plaintext production values.

## Denial of Service

Readiness probes keep broken instances out of rotation. Redis can support rate limiting, but
financial correctness remains in PostgreSQL.

## Elevation of Privilege

API keys carry scopes such as `payments:read`, `payments:write`, `refunds:write`, and
`webhooks:manage`.
