# Security Threat Model

ForgePay uses STRIDE to frame risks.

## Spoofing

API keys are generated with secure randomness and only SHA-256 hashes are stored. Requests use
bearer tokens and central scope checks. Revocation is represented in the schema with `revoked_at`;
the current public demo API does not expose key rotation/revocation endpoints.

## Tampering

Money-changing endpoints require idempotency keys and validate payload fingerprints. Webhooks are
signed with per-endpoint HMAC secrets and include timestamps for replay-window enforcement.

## Repudiation

Business operations append audit logs with actor, action, resource, timestamp, correlation ID,
and metadata.

## Information Disclosure

Errors use stable codes and avoid stack traces. Webhook signing secrets are returned only at
creation/rotation time and are encrypted at rest with an environment-supplied master key. The local
default master key is suitable only for development.

## Denial of Service

Readiness probes keep broken instances out of rotation. Redis can support rate limiting, but
financial correctness remains in PostgreSQL. Full production-grade distributed rate limiting is an
accepted remaining risk in this portfolio version.

## Elevation of Privilege

API keys carry scopes such as `payments:read`, `payments:write`, `refunds:write`, and
`webhooks:manage`.
