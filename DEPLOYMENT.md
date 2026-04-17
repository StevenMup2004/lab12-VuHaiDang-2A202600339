# Deployment Information

## Public URL
https://day12-v2-production.up.railway.app

## Platform
Railway

## Deployment Metadata
- Project: day12-v1
- Service: day12-v2
- Environment: production
- Latest successful deployment ID: 1373ea71-951c-4103-87a1-7d61d4980426
- Status: SUCCESS
- Verified date: 2026-04-17

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
  -d '{"user_id":"doc-test","question":"Hello"}'
```

### API Test (with API key)
```bash
curl -i -X POST https://day12-v2-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"doc-test-ok","question":"Give one short travel tip for Da Lat."}'
```

### Rate Limit Test (12 requests)
```bash
for i in {1..12}; do
  curl -s -o /dev/null -w "Req${i}=%{http_code}\n" \
    -X POST https://day12-v2-production.up.railway.app/ask \
    -H "X-API-Key: YOUR_AGENT_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"ratetest-doc-final","question":"Rate test"}'
done
```

## Observed Output (Actual)

### Health
```text
Status=200
Body={"status":"ok"}
```

### Ready
```text
Status=200
Body={"status":"ready"}
```

### Ask (no API key)
```text
Status=401
Body=
```

### Ask (with API key)
```json
{
  "answer": "When visiting Da Lat, don't miss the chance to explore the vibrant local markets, like Da Lat Market, for fresh produce, unique souvenirs, and delicious street food. It's a great way to immerse yourself in the local culture.",
  "metrics": {
    "completion_tokens": 63,
    "latency_ms": 1244,
    "prompt_tokens": 954,
    "steps_count": 1,
    "total_tokens": 1017
  },
  "mode": "agent_v2",
  "user_id": "doc-test-ok"
}
```

### Rate Limit (12 requests)
```text
RateLimitUser=ratetest-doc-final-1885561842
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
Req11=200
Req12=200
```

Note: In this verification run, all 12 requests returned 200 (no 429 observed).

## Environment Variables Set (Key Names)
- AGENT_API_KEY
- DEFAULT_MODEL
- DEFAULT_PROVIDER
- ENVIRONMENT
- FLASK_DEBUG
- LOG_LEVEL
- MONTHLY_BUDGET_USD
- OPENAI_API_KEY
- RATE_LIMIT_PER_MINUTE
- REDIS_URL
- PORT (provided by Railway at runtime)

## Screenshots
- [Deployment dashboard](screenshots/06-lab-complete/dashboard.png)
- [Service running](screenshots/06-lab-complete/running.png)
- [Test results](screenshots/06-lab-complete/test.png)
