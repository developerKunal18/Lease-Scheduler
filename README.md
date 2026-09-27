# Lease Scheduler

A Flask service demonstrating time-bound leases for distributed systems.

## Features
- Acquire and release resource leases
- Unique lease tokens
- Configurable TTL
- Lease renewal
- Automatic expiration
- Owner-only renewal and release
- Thread-safe in-memory implementation
- Health and statistics endpoints
- Pytest tests

## Run
```bash
pip install -r requirements.txt
python app.py
```

## API
- `POST /api/leases/<resource>` — acquire
- `POST /api/leases/<resource>/renew` — renew
- `DELETE /api/leases/<resource>` — release
- `GET /api/leases/<resource>` — inspect
- `GET /api/leases` — list active leases
- `GET /api/stats`
- `GET /health`

Example:
```json
{
  "owner": "worker-1",
  "ttl": 30
}
```

Use the returned token as:
`Authorization: Bearer <lease-token>`

## Concepts
Distributed leases, TTL, expiration, resource ownership, renewal, safe release, distributed coordination.
