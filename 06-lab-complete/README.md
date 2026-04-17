# Lab 12 — Integrated Project Deployment

This folder now deploys the integrated project runtime using Flask + Gunicorn.

## Project Structure

```text
06-lab-complete/
├── app.py              # Flask entrypoint
├── src/                # Agent, tools, providers
├── templates/          # Web UI templates
├── static/             # CSS and JS assets
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .dockerignore
├── railway.toml
├── render.yaml
├── check_production_ready.py
└── backup_pre_project_integration_*/
```

## Endpoints

- `GET /` web interface
- `GET /health` health check
- `GET /ready` readiness check
- `POST /api/chat` full chat API
- `POST /ask` compatibility API for simple question payload

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
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","mode":"agent_v2"}'
```

### Option 2: Python

```bash
cd 06-lab-complete
python -m pip install -r requirements.txt
python app.py
```

## Deploy

### Railway

`railway.toml` is ready. Set these variables in Railway/Render:

- `PORT`
- `AGENT_API_KEY` (optional, for `/ask`)
- `OPENAI_API_KEY` (required if using OpenAI provider)
- `GEMINI_API_KEY` (optional)
- `DEFAULT_PROVIDER`
- `DEFAULT_MODEL`
- `LOG_LEVEL`

### Render

`render.yaml` uses service name `day12-v2` to avoid overwriting existing service.

## Production Readiness Check

```bash
python check_production_ready.py
```
