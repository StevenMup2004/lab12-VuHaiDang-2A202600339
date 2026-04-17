# Lab 12 — Complete Production Agent

Final production-ready agent for Day 12 checklist.

## Project Structure

```text
06-lab-complete/
├── app/
│   ├── main.py         # FastAPI entrypoint
│   ├── config.py       # 12-factor configuration
│   ├── auth.py         # API key authentication
│   ├── rate_limiter.py # Redis-backed rate limiter
│   └── cost_guard.py   # Redis-backed monthly budget guard
├── utils/
│   └── mock_llm.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .dockerignore
├── railway.toml
├── render.yaml
└── check_production_ready.py
```

## Requirement Mapping

- API key auth: `X-API-Key`
- Rate limit: `RATE_LIMIT_PER_MINUTE=10` (default)
- Cost guard: `MONTHLY_BUDGET_USD=10.0` (default)
- Health/readiness: `GET /health`, `GET /ready`
- Graceful shutdown: SIGTERM + readiness off during shutdown
- Stateless design: rate/budget state stored in Redis
- No hardcoded secrets: all sensitive config from environment variables

## Run Locally

### Option 1: Docker Compose (recommended)

```bash
cd 06-lab-complete
docker compose up --build
```

Test:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: dev-key-change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

### Option 2: Python

```bash
cd 06-lab-complete
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Deploy

### Railway

`railway.toml` is ready. Set these variables in Railway:

- `PORT`
- `REDIS_URL`
- `AGENT_API_KEY`
- `OPENAI_API_KEY` (optional; app uses mock if empty)
- `RATE_LIMIT_PER_MINUTE`
- `MONTHLY_BUDGET_USD`
- `LOG_LEVEL`

### Render

`render.yaml` is ready with default values for budget and rate limit.

## Production Readiness Check

```bash
python check_production_ready.py
```
