# Deployment Information

## Public URL
https://day12-v1-production.up.railway.app

## Platform
Railway

## Deployment Metadata
- Project: day12-v1
- Service: day12-v1
- Environment: production
- Latest successful deployment ID: `017dcb10-e4a2-49f9-a07e-54ad327641e0`

## Test Commands

### Health Check
```bash
curl -s https://day12-v1-production.up.railway.app/health
```

### Readiness Check
```bash
curl -s https://day12-v1-production.up.railway.app/ready
```

### API Test (authentication required)
```bash
curl -i -X POST https://day12-v1-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: HTTP 401
```

### API Test (with API key)
```bash
curl -i -X POST https://day12-v1-production.up.railway.app/ask \
  -H "X-API-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: HTTP 200 with answer payload
```

### Rate Limit Test (10 req/min)
```bash
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://day12-v1-production.up.railway.app/ask \
    -H "X-API-Key: my-secret-key" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"ratetest","question":"ping"}'
done
# Expected: first 10 requests = 200, then 429
```

## Verified Public Results
Validation run time (UTC): 2026-04-17T05:49

- `GET /health` -> 200
- `GET /ready` -> 200
- `POST /ask` without `X-API-Key` -> 401
- `POST /ask` with `X-API-Key` -> 200
- Burst test (12 requests) -> requests 1-10: 200, requests 11-12: 429

Example observed body for authenticated request:
```json
{
  "user_id": "test2",
  "question": "Hello",
  "answer": "Your question was received by the cloud-deployed agent.",
  "model": "gpt-4o-mini",
  "usage": {
    "requests_remaining": 9,
    "monthly_spend_usd": 0.00001,
    "monthly_budget_usd": 10.0
  },
  "timestamp": "2026-04-17T05:49:30.782002+00:00"
}
```

## Environment Variables Set
- PORT (provided automatically by Railway)
- REDIS_URL
- AGENT_API_KEY
- LOG_LEVEL
- ENVIRONMENT
- RATE_LIMIT_PER_MINUTE
- MONTHLY_BUDGET_USD

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
