# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Hardcoded secrets trong code (OPENAI_API_KEY, DATABASE_URL) trong bản develop.
2. In lộ secret ra log (print ra API key).
3. Không có config management tập trung (biến cấu hình đặt trực tiếp trong app).
4. Debug/reload bật cứng (không an toàn cho production).
5. Port bị hardcode (8000), không lấy từ biến môi trường PORT.
6. Host đặt localhost nên không phù hợp khi chạy trong container/cloud.
7. Không có endpoint health check để platform theo dõi tình trạng ứng dụng.
8. Không có cơ chế graceful shutdown rõ ràng cho vòng đời ứng dụng.
9. Logging bằng print() thay vì structured logging.

### Exercise 1.2: Run basic version
- Đã chạy bản develop bằng app.py.
- Ứng dụng khởi động ở localhost:8000 và endpoint chính hoạt động.
- Kết luận: chạy được trên máy local nhưng chưa production-ready do nhiều anti-pattern về cấu hình, bảo mật, quan sát hệ thống và vận hành.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Hardcode trực tiếp trong app.py | Tách riêng config.py, đọc từ environment variables | Dễ đổi theo môi trường dev/staging/prod, không sửa code khi deploy |
| Secrets | API key viết cứng trong mã nguồn | Lấy từ OPENAI_API_KEY / AGENT_API_KEY trong env | Tránh lộ key khi push code, đáp ứng bảo mật cơ bản |
| Host & Port | localhost:8000 cố định | Host/Port lấy từ HOST và PORT | Tương thích container/cloud (Railway/Render/Cloud Run inject PORT) |
| Logging | print() thủ công, có thể lộ dữ liệu nhạy cảm | Structured JSON logging qua logging module | Dễ monitor, search, phân tích log, giảm rủi ro lộ secret |
| Health Check | Không có | Có /health và /ready | Orchestrator/load balancer biết khi nào app sống và sẵn sàng nhận traffic |
| Lifecycle | Không quản lý startup/shutdown rõ ràng | Dùng lifespan startup/shutdown + readiness flag | Ổn định hơn khi deploy, giảm lỗi lúc khởi động/tắt dịch vụ |
| Graceful Shutdown | Tắt đột ngột | Có xử lý SIGTERM và shutdown tuần tự | Giảm mất request/in-flight work khi scale down hoặc redeploy |
| CORS | Không cấu hình rõ | CORS đọc từ ALLOWED_ORIGINS | Kiểm soát truy cập từ frontend đúng môi trường |
| Dependency setup | Chưa tối ưu cho cấu hình env | Có .env.example + python-dotenv | Chuẩn hóa cách cấu hình, giúp onboarding và deploy nhất quán |

### Extra discussion notes (from Part 1)
1. Nếu push code có API key hardcoded lên GitHub public: key có thể bị bot quét, bị lạm dụng gây mất tiền và rủi ro bảo mật.
2. Stateless quan trọng khi scale vì mọi instance đều có thể xử lý request như nhau, dễ scale ngang và thay thế instance lỗi.
3. Dev/prod parity nghĩa là môi trường dev phải giống production càng nhiều càng tốt (config, dependencies, cách chạy) để giảm lỗi "works on my machine".

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image:
	- Develop Dockerfile: python:3.11
	- Production Dockerfile: python:3.11-slim (multi-stage: builder + runtime)
2. Working directory:
	- Cả hai Dockerfile đều dùng WORKDIR /app
3. Tại sao COPY requirements.txt trước?
	- Để tận dụng Docker layer cache. Khi code thay đổi nhưng dependencies không đổi thì Docker không cần cài lại toàn bộ packages, build nhanh hơn.
4. CMD vs ENTRYPOINT khác nhau thế nào?
	- CMD: command mặc định, có thể override khi docker run.
	- ENTRYPOINT: command chính cố định của container, tham số thêm từ docker run sẽ append vào sau.
5. Multi-stage build giúp gì cho production?
	- Tách stage build và stage runtime, chỉ copy phần cần thiết để chạy app, giảm kích thước image và giảm bề mặt tấn công.
6. Vì sao nên chạy non-root user trong container?
	- Giảm rủi ro bảo mật nếu container bị khai thác, hạn chế quyền truy cập hệ thống.

### Exercise 2.3: Image size comparison
- Develop: 1.66 GB (day12-agent-develop-real:latest)
- Production: 236 MB (day12-agent-production-real:latest)
- Difference: khoảng 86.12% nhỏ hơn

Ghi chú đo lường:
- Số liệu lấy từ output docker images sau khi build lại 2 image thực tế trên máy local.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://day12-v1-production.up.railway.app
- Screenshot: [03-cloud-deployment/railway/railway.png](03-cloud-deployment/railway/railway.png)

Kết quả kiểm tra nhanh:
- `GET /health` trả về HTTP 200
- Response mẫu: {"status":"ok", ...}

## Part 4: API Security

### Exercise 4.1-4.3: Test results

Exercise 4.1 (API key auth - develop):

```bash
POST /ask?question=hello (không có X-API-Key)
-> 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

POST /ask?question=hello (X-API-Key: wrong-key)
-> 403 Forbidden
{"detail":"Invalid API key."}

POST /ask?question=hello (X-API-Key: my-secret-key)
-> 200 OK
{"question":"hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Exercise 4.2 (JWT auth - production):

```bash
POST /auth/token (student/wrong)
-> 401 Unauthorized
{"detail":"Invalid credentials"}

POST /auth/token (teacher/teach456)
-> 200 OK
{"token_type":"bearer", "expires_in_minutes":60, ...}

POST /ask (không có Authorization)
-> 401 Unauthorized
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

POST /ask (Authorization: Bearer <admin_token>)
-> 200 OK
{"question":"Explain JWT","answer":"...","usage":{"requests_remaining":99,...}}
```

Exercise 4.3 (Rate limiting - production):

```bash
Rate test with student token (12 calls liên tiếp):
Request 1 => HTTP 200
Request 2 => HTTP 200
Request 3 => HTTP 200
Request 4 => HTTP 200
Request 5 => HTTP 200
Request 6 => HTTP 200
Request 7 => HTTP 200
Request 8 => HTTP 200
Request 9 => HTTP 200
Request 10 => HTTP 429
Request 11 => HTTP 429
Request 12 => HTTP 429

Body khi hit limit:
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":31}}
```

### Exercise 4.4: Cost guard implementation
- App dùng `CostGuard` để chặn request trước khi gọi LLM (`check_budget`) và ghi nhận chi phí sau khi có response (`record_usage`).
- Chi phí được tính theo input/output token với đơn giá tách riêng, lưu usage theo từng user.
- Có 2 lớp budget:
	- Per-user budget theo ngày (`daily_budget_usd`, mặc định $1/user/day).
	- Global budget theo ngày (`global_daily_budget_usd`, mặc định $10/day toàn hệ thống).
- Khi user vượt budget: trả về HTTP 402 với thông tin `used_usd`, `budget_usd`.
- Khi hệ thống vượt global budget: trả về HTTP 503 để bảo vệ tổng chi phí.
- Có ngưỡng cảnh báo `warn_at_pct` (mặc định 80%) để log warning sớm.
- Bản lab hiện dùng in-memory để demo; khi production thật nên chuyển state sang Redis/DB để scale nhiều instance và giữ dữ liệu qua restart.

Ghi chú sửa lỗi trong quá trình test:
- Đã sửa middleware security headers ở `04-api-gateway/production/app.py`: thay `response.headers.pop("server", None)` bằng xóa key an toàn (`if "server" in response.headers: del ...`) để tránh lỗi 500.

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes

Exercise 5.1 (Health + Readiness checks):
- Đã triển khai 2 endpoint trong bản develop:
	- `GET /health`: trả status, uptime, version, environment và checks (memory).
	- `GET /ready`: trả `ready=true` khi app sẵn sàng, ngược lại trả 503.
- Kết quả test thực tế:

```bash
GET /health -> 200 OK
{"status":"ok","uptime_seconds":12.4,"version":"1.0.0","environment":"development",...}

GET /ready -> 200 OK
{"ready":true,"in_flight_requests":1}

POST /ask?question=Long%20task -> 200 OK
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Exercise 5.2 (Graceful shutdown):
- Có triển khai signal handler (`SIGTERM`, `SIGINT`) và lifecycle shutdown trong bản develop.
- Cơ chế hiện tại:
	- Set trạng thái not-ready khi bắt đầu shutdown.
	- Chờ các in-flight requests hoàn tất (tối đa 30 giây).
	- Sau đó mới hoàn tất shutdown.
- Trong test local, server khởi động/tắt đúng; flow graceful được thể hiện qua logic lifecycle + timeout graceful shutdown của uvicorn.

Exercise 5.3 (Stateless design):
- Bản production dùng session storage abstraction:
	- Ưu tiên Redis (`REDIS_URL`) nếu kết nối được.
	- Fallback in-memory nếu Redis không có (chỉ phù hợp demo, không scale ngang).
- Session/history được lưu theo `session_id`, không gắn với process memory cố định của một request handler.
- Kết quả test thực tế:

```bash
GET /health -> {"status":"ok","instance_id":"instance-235eee","storage":"in-memory","redis_connected":"N/A"}
GET /ready -> {"ready":true,"instance":"instance-235eee"}

POST /chat turn 1 -> tạo session_id ea7fea28-...
POST /chat turn 2 với cùng session_id -> tiếp tục hội thoại
GET /chat/{session_id}/history -> count=4 messages (2 user + 2 assistant)
```

Exercise 5.4 (Load balancing with Nginx + scale agent):
- Đã chạy đúng lệnh yêu cầu:

```bash
docker compose up --scale agent=3 -d
```

- Kết quả thực tế: stack chạy thành công với 3 agent instances + Redis + Nginx.
- Kiểm tra nhanh qua Nginx (`GET /health` 10 lần) cho thấy request được phân phối round-robin giữa 3 instance khác nhau.
- Output chính:

```bash
Call 1 => instance-e229ed
Call 2 => instance-3e5f7e
Call 3 => instance-e702a3
...

docker compose ps:
production-agent-1  Up
production-agent-2  Up
production-agent-3  Up
production-nginx-1  Up (0.0.0.0:8080->80)
production-redis-1  Up (healthy)
```

Exercise 5.5 (Run stateless test script):
- Đã chạy `test_stateless.py` thành công với app local trên port 8080.
- Kết quả:
	- Script tạo session mới và gửi 5 requests liên tiếp.
	- History được giữ đầy đủ (`Total messages: 10`).
	- Requests được xử lý bởi nhiều instance khác nhau nhưng session vẫn liên tục.

```bash
Total requests: 5
Instances used: {'instance-e702a3', 'instance-3e5f7e', 'instance-e229ed'}
All requests served despite different instances!
Total messages: 10
```

Kết luận Part 5:
- 5.1 đến 5.5 đều chạy và có output thực tế.
- Multi-instance load balancing qua Nginx hoạt động đúng, session stateless được giữ ổn định qua Redis.
