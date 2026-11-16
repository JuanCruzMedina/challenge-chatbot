# payments-api v2

Replaces v1. It is the technical basis of FEAT-102 (retry of failed payments).

## Changes from v1

- **Automatic retries:** on a `provider_timeout` failure, the service retries up to 3 times with increasing wait before publishing `payment.failed`.
- **`POST /v2/payments`** accepts the optional field `retry_policy` (`none` or `auto`). The default is `auto`.
- **`POST /v2/payments/{id}/retry`** allows a manual retry of a `FAILED` charge without creating a new charge.
- The `payment.confirmed` and `payment.failed` events now include the field `attempts`.

## Migrating from v1

- Change the base path from `/payments` to `/v2/payments`.
- Treat `attempts` as a new field in events (existing consumers ignore it without breaking).
- v1 is retired on **2027-03-31**. After that date, `payments-api` v1 returns `410 Gone`.
