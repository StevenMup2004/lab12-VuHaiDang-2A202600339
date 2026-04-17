# Deployment Information

## Public URL
https://day12-v2-production.up.railway.app

## Platform
Railway

## Deployment Metadata
- Project: day12-v1
- Service: day12-v2
- Environment: production
- Latest successful deployment ID: d08ceaf0-4541-4cd8-bf86-8e7cc54a88c8
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
  -d '{"user_id":"doc-final","question":"Hello"}'
```

### API Test (with API key)
```bash
curl -i -X POST https://day12-v2-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"doc-final-auth","question":"Give one short travel tip for Da Lat.","mode":"chatbot"}'
```

### Rate Limit Test (12 requests)
```bash
for i in {1..12}; do
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
Body={"environment":"development","redis_connected":false,"shutting_down":false,"status":"ok"}
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
  "answer": "When traveling to Da Lat, make sure to pack layered clothing. The weather can be quite variable, with cool mornings and evenings but warmer afternoons, so dressing in layers will keep you comfortable throughout the day.",
  "metrics": {
    "completion_tokens": 41,
    "latency_ms": 1145,
    "prompt_tokens": 114,
    "steps_count": 0,
    "total_tokens": 155
  },
  "mode": "chatbot",
  "usage": {
    "monthly_budget_usd": 10.0,
    "monthly_spend_usd": 0.000046,
    "requests_remaining": 9
  },
  "user_id": "doc-final-auth"
}
```

### Rate Limit (12 requests)
```text
RateLimitUser=ratetest-doc-final-158376357
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
