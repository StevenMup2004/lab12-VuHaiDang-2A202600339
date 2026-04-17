# Deployment Information

## Public URL
https://day12-v2-production.up.railway.app

## Platform
Railway

## Deployment Metadata
- Project: day12-v1
- Service: day12-v2
- Environment: production
- Latest successful deployment ID: de8e7f79-28aa-4873-9ed8-777ae342cac3
- Status: SUCCESS
- Verified date: 2026-04-17

## Checklist Fit (Required by Delivery Checklist)

- Public URL is accessible: PASS
- Health check returns 200: PASS
- Auth required on /ask (no API key -> 401): PASS
- /ask with API key returns 200: PASS
- Source layout app/main.py + config/auth/rate_limiter/cost_guard present: PASS
- Screenshot files present in screenshots/ folder: PASS
- Rate limiting should eventually return 429: PASS
- Redis stateless in production: PASS

Notes:
- Current health output reports `environment=production` and `redis_connected=true`.
- Current extended rate test returns `429` with `retry_after_seconds` and `Retry-After` header.
- Production service is connected to Railway Redis via internal `REDIS_URL`.

## Test Commands

### Health Check
```bash
curl -i https://day12-v2-production.up.railway.app/health
```

### Readiness Check
```bash
curl -i https://day12-v2-production.up.railway.app/ready
```

### API Test (without API key)
```bash
curl -i -X POST https://day12-v2-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"doc-final","question":"Hello"}'
```

### API Test (with API key)
```bash
curl -i -X POST https://day12-v2-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"doc-final-auth","question":"Give one short travel tip for Da Lat.","mode":"chatbot"}'
```

### Rate Limit Test (20 requests)
```bash
for i in {1..20}; do
  curl -s -o /dev/null -w "Req${i}=%{http_code}\n" \
    -X POST https://day12-v2-production.up.railway.app/ask \
    -H "X-API-Key: YOUR_AGENT_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"ratetest-doc-final","question":"Ping","mode":"chatbot"}'
done
```

## Observed Output (Actual)

### Health
```text
Status=200
Body={"environment":"production","redis_connected":true,"shutting_down":false,"status":"ok"}
```

### Ready
```text
Status=200
Body={"status":"ready"}
```

### Ask (no API key)
```text
Status=401
Body={"detail":"Unauthorized"}
```

### Ask (with API key)
```json
{
  "answer": "Hello! How can I assist you with your travel plans today?",
  "metrics": {
    "completion_tokens": 13,
    "latency_ms": 895,
    "prompt_tokens": 106,
    "steps_count": 0,
    "total_tokens": 119
  },
  "mode": "chatbot",
  "usage": {
    "monthly_budget_usd": 10.0,
    "monthly_spend_usd": 1.3e-05,
    "requests_remaining": 9
  },
  "user_id": "ok-user"
}
```

### Rate Limit (20 requests)
```text
RateLimitUser=rate-user
Req1=200
Req2=200
Req3=200
Req4=200
Req5=200
Req6=200
Req7=200
Req8=200
Req9=200
Req10=200
Req11=429 RetryAfter=46 Body={"detail":{"error":"Rate limit exceeded","limit":10,"retry_after_seconds":46,"window_seconds":60}}
```

Note: 429 is observed at request 11, and response includes `retry_after_seconds`; `Retry-After` header matches this value.

## Environment Variables Set (Key Names)
- PORT (provided by Railway at runtime)
- REDIS_URL
- AGENT_API_KEY
- LOG_LEVEL

Additional configured keys:
- DEFAULT_MODEL
- DEFAULT_PROVIDER
- ENVIRONMENT
- FLASK_DEBUG
- MONTHLY_BUDGET_USD
- OPENAI_API_KEY
- RATE_LIMIT_PER_MINUTE

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
