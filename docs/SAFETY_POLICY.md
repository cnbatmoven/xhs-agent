# Safety Policy

The backend applies safety normalization before a job enters the queue.

## Endpoints

- `POST /api/v1/safety/preview`: returns normalized params, risk, warnings, errors, and usage.
- `GET /api/v1/safety/usage`: returns today's local crawl counters.
- `GET /api/v1/safety/policy`: returns active policy thresholds.

## Defaults

- XHS real crawl minimum delay: `6s`.
- Pugongying minimum delay: `12s`.
- Pugongying safe mode is forced on.
- Pugongying requires `cdp_url`.
- XHS over `50` rows per task emits a warning.
- `graph_split` real crawl over `5` rows emits a warning.
- Pugongying over `10` rows per task emits a warning.

## Usage Warnings

Usage is stored in:

`data/safety/usage_YYYYMMDD.json`

The preview warns when estimated usage would exceed:

- XHS: `120` rows/hour or `500` rows/day.
- Pugongying: `20` rows/hour or `60` rows/day.

## Hard Limits

By default:

- XHS hard limits are configured but not enforced.
- Pugongying hard limits are enforced.

Current hard limits:

- XHS: `240` rows/hour, `1000` rows/day.
- Pugongying: `20` rows/hour, `60` rows/day.

This means large XHS jobs can still run after warnings, while large Pugongying jobs are blocked before queueing.

## Verification Commands

Preview policy:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/safety/policy'
```

Preview usage:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/safety/usage'
```

Use the frontend "预览计划" button to see the same safety result before submitting a job.
