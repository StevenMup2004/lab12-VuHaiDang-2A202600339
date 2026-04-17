"""
Flask Web Application for Travel Planning Agent.
Provides a beautiful chat UI to interact with both the Chatbot and ReAct Agent.
"""

import os
import sys
import json
import time
import re
import signal
import hashlib
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv

try:
    import redis  # pyright: ignore[reportMissingImports]
except ImportError:
    redis = None

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from src.core.openai_provider import OpenAIProvider
from src.agent.agent import ReActAgent
from src.tools.tool_registry import get_tools
from src.telemetry.logger import logger

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# Initialize provider and tools
provider = None
tools = None
agent_v1 = None
agent_v2 = None


def _read_int_env(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        logger.info(f"Invalid {name}={raw!r}. Falling back to {default}.")
        value = default
    return max(value, minimum)


def _read_float_env(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        logger.info(f"Invalid {name}={raw!r}. Falling back to {default}.")
        value = default
    return max(value, minimum)


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
RATE_LIMIT_PER_MINUTE = _read_int_env("RATE_LIMIT_PER_MINUTE", 10, 1)
MONTHLY_BUDGET_USD = _read_float_env("MONTHLY_BUDGET_USD", 10.0, 0.01)

# Lightweight token cost model for budget guard.
INPUT_COST_PER_1K = 0.00015
OUTPUT_COST_PER_1K = 0.00060


class RateLimitExceeded(Exception):
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        super().__init__("Rate limit exceeded")


class BudgetExceeded(Exception):
    def __init__(self, used_usd: float, budget_usd: float, month: str):
        self.used_usd = used_usd
        self.budget_usd = budget_usd
        self.month = month
        super().__init__("Monthly budget exceeded")


class RateLimiter:
    """Sliding-window rate limiter with Redis backend and in-memory fallback."""

    def __init__(self, limit_per_minute: int = 10, window_seconds: int = 60):
        self.limit_per_minute = limit_per_minute
        self.window_seconds = window_seconds
        self._redis = None
        self._memory_windows: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def set_redis_client(self, redis_client):
        self._redis = redis_client

    def check(self, identity: str) -> dict:
        now = time.time()

        if self._redis is not None:
            key = f"rl:{identity}"
            token = f"{int(now * 1000)}-{uuid.uuid4().hex}"
            window_start = now - self.window_seconds
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {token: now})
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds + 5)
            _, _, request_count, _ = pipe.execute()
        else:
            with self._lock:
                window = self._memory_windows[identity]
                while window and window[0] < now - self.window_seconds:
                    window.popleft()
                window.append(now)
                request_count = len(window)

        if request_count > self.limit_per_minute:
            raise RateLimitExceeded(self.limit_per_minute, self.window_seconds)

        return {
            "limit": self.limit_per_minute,
            "remaining": max(self.limit_per_minute - request_count, 0),
        }


class CostGuard:
    """Monthly budget guard with Redis-backed usage storage."""

    def __init__(self, monthly_budget_usd: float = 10.0):
        self.monthly_budget_usd = monthly_budget_usd
        self._redis = None
        self._memory_usage: dict[str, float] = defaultdict(float)
        self._lock = Lock()

    def set_redis_client(self, redis_client):
        self._redis = redis_client

    @staticmethod
    def estimate_cost(input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1000) * INPUT_COST_PER_1K
        output_cost = (output_tokens / 1000) * OUTPUT_COST_PER_1K
        return round(input_cost + output_cost, 6)

    @staticmethod
    def _month_prefix() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @staticmethod
    def _seconds_until_next_month() -> int:
        now = datetime.now(timezone.utc)
        next_month = (
            now.replace(day=28, hour=0, minute=0, second=0, microsecond=0)
            + timedelta(days=4)
        ).replace(day=1)
        return int((next_month - now).total_seconds()) + 86400

    def _usage_key(self, user_id: str) -> str:
        return f"budget:{self._month_prefix()}:{user_id}"

    def get_usage(self, user_id: str) -> float:
        key = self._usage_key(user_id)
        if self._redis is not None:
            val = self._redis.get(key)
            return round(float(val) if val else 0.0, 6)

        with self._lock:
            return round(self._memory_usage[key], 6)

    def check_budget(self, user_id: str, estimated_cost: float):
        used = self.get_usage(user_id)
        if used + estimated_cost > self.monthly_budget_usd:
            raise BudgetExceeded(
                used_usd=used,
                budget_usd=self.monthly_budget_usd,
                month=self._month_prefix(),
            )

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> float:
        cost = self.estimate_cost(input_tokens, output_tokens)
        key = self._usage_key(user_id)

        if self._redis is not None:
            total = self._redis.incrbyfloat(key, cost)
            self._redis.expire(key, self._seconds_until_next_month())
            return round(float(total), 6)

        with self._lock:
            self._memory_usage[key] += cost
            return round(self._memory_usage[key], 6)


def _api_key_bucket(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


_is_shutting_down = False
_redis_client = None
_last_redis_connect_attempt = 0.0
_rate_limiter = RateLimiter(limit_per_minute=RATE_LIMIT_PER_MINUTE)
_cost_guard = CostGuard(monthly_budget_usd=MONTHLY_BUDGET_USD)


def _connect_redis():
    global _redis_client, _last_redis_connect_attempt

    if _redis_client is not None:
        return _redis_client

    if redis is None or not REDIS_URL:
        return None

    now = time.time()
    if now - _last_redis_connect_attempt < 5:
        return None

    _last_redis_connect_attempt = now

    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        _redis_client = client
        logger.info("Redis connected for stateless rate-limit and budget guard")
    except Exception as exc:
        logger.info(f"Redis unavailable, using in-memory fallback: {str(exc)}")
        _redis_client = None

    return _redis_client


def _redis_ok() -> bool:
    client = _connect_redis()
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False


def _sync_state_backends():
    client = _connect_redis()
    _rate_limiter.set_redis_client(client)
    _cost_guard.set_redis_client(client)


def _handle_signal(signum, _frame):
    global _is_shutting_down
    _is_shutting_down = True
    logger.info(f"Received signal {signum}; entering graceful shutdown mode")


for _sig_name in ("SIGTERM", "SIGINT"):
    _sig = getattr(signal, _sig_name, None)
    if _sig is not None:
        signal.signal(_sig, _handle_signal)


_sync_state_backends()


def _simulated_answer(user_message: str) -> str:
    """Return a deterministic fallback answer when external LLM is unavailable."""
    return (
        "[SIMULATED] Live deploy is healthy. OPENAI_API_KEY is missing or invalid, "
        f"so this fallback response is used for question: {user_message[:160]}"
    )


def init_systems():
    """Lazy initialization of LLM systems."""
    global provider, tools, agent_v1, agent_v2
    if provider is None and agent_v1 is None and agent_v2 is None:
        tools = get_tools()
        try:
            provider = OpenAIProvider(model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"))
            agent_v1 = ReActAgent(llm=provider, tools=tools, max_steps=10, version="v1")
            agent_v2 = ReActAgent(llm=provider, tools=tools, max_steps=10, version="v2")
        except Exception as e:
            # Keep service responsive even without OPENAI_API_KEY.
            logger.error(f"LLM initialization failed, using simulated fallback: {str(e)}")
            provider = None
            agent_v1 = None
            agent_v2 = None


@app.route('/')
def index():
    return render_template('index.html')


@app.before_request
def reject_new_work_while_shutting_down():
    if _is_shutting_down and request.path != '/health':
        return jsonify({"detail": "Service is shutting down"}), 503
    return None


@app.route('/health', methods=['GET'])
def health():
    redis_connected = _redis_ok()
    status = "ok"
    if ENVIRONMENT == "production" and not redis_connected:
        status = "degraded"

    return jsonify({
        "status": status,
        "environment": ENVIRONMENT,
        "redis_connected": redis_connected,
        "shutting_down": _is_shutting_down,
    }), 200


@app.route('/ready', methods=['GET'])
def ready():
    if _is_shutting_down:
        return jsonify({"status": "not_ready", "reason": "shutting_down"}), 503
    if ENVIRONMENT == "production" and not _redis_ok():
        return jsonify({"status": "not_ready", "reason": "redis_unavailable"}), 503
    return jsonify({"status": "ready"}), 200


@app.route('/ask', methods=['POST'])
def ask():
    if _is_shutting_down:
        return jsonify({"detail": "Service is shutting down"}), 503

    _sync_state_backends()

    provided_key = request.headers.get("X-API-Key", "").strip()
    required_key = os.getenv("AGENT_API_KEY", "").strip()
    if required_key:
        if provided_key != required_key:
            return jsonify({"detail": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    question = str(data.get('question', '')).strip()
    user_id = str(data.get('user_id', 'anonymous')).strip()
    mode = str(data.get('mode', 'agent_v2')).strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    identity_key = provided_key or request.remote_addr or "anonymous"
    identity = f"{user_id}:{_api_key_bucket(identity_key)}"

    try:
        rate_info = _rate_limiter.check(identity)
    except RateLimitExceeded as exc:
        return (
            jsonify({
                "detail": {
                    "error": "Rate limit exceeded",
                    "limit": exc.limit,
                    "window_seconds": exc.window_seconds,
                }
            }),
            429,
            {"Retry-After": str(exc.window_seconds)},
        )

    input_tokens = max(len(question.split()) * 2, 1)
    estimated_output_tokens = max(20, min(300, input_tokens * 2))
    estimated_cost = _cost_guard.estimate_cost(input_tokens, estimated_output_tokens)

    try:
        _cost_guard.check_budget(user_id, estimated_cost)
    except BudgetExceeded as exc:
        return jsonify({
            "detail": {
                "error": "Monthly budget exceeded",
                "used_usd": exc.used_usd,
                "budget_usd": exc.budget_usd,
                "month": exc.month,
            }
        }), 402

    init_systems()

    try:
        if mode == 'chatbot':
            result = handle_chatbot(question).get_json() or {}
        elif mode == 'agent_v1':
            result = handle_agent(question, agent_v1, "v1").get_json() or {}
        else:
            result = handle_agent(question, agent_v2, "v2").get_json() or {}
    except Exception as e:
        logger.error(f"Error in /ask: {str(e)}")
        return jsonify({"error": str(e)}), 500

    answer_text = str(result.get("answer", ""))
    output_tokens = max(len(answer_text.split()) * 2, 1) if answer_text else 0
    monthly_spend_usd = _cost_guard.record_usage(user_id, input_tokens, output_tokens)

    return jsonify({
        "user_id": user_id,
        "mode": result.get("mode", mode),
        "answer": answer_text,
        "metrics": result.get("metrics", {}),
        "usage": {
            "requests_remaining": rate_info.get("remaining", 0),
            "monthly_spend_usd": monthly_spend_usd,
            "monthly_budget_usd": MONTHLY_BUDGET_USD,
        }
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages — route to chatbot or agent based on mode."""
    data = request.json
    user_message = data.get('message', '')
    mode = data.get('mode', 'agent_v2')  # chatbot | agent_v1 | agent_v2
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    init_systems()
    
    try:
        if mode == 'chatbot':
            return handle_chatbot(user_message)
        elif mode == 'agent_v1':
            return handle_agent(user_message, agent_v1, "v1")
        else:
            return handle_agent(user_message, agent_v2, "v2")
    except Exception as e:
        logger.error(f"Error in /api/chat: {str(e)}")
        return jsonify({"error": str(e)}), 500


def handle_chatbot(user_message: str):
    """Handle chatbot baseline request."""
    start_time = time.time()

    if provider is None:
        total_time = int((time.time() - start_time) * 1000)
        return jsonify({
            "mode": "chatbot",
            "answer": _simulated_answer(user_message),
            "steps": [],
            "metrics": {
                "latency_ms": total_time,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "steps_count": 0
            }
        })
    
    system_prompt = """You are a travel planning assistant (Trợ lý Du lịch).
You help users plan trips including weather, hotels, and activities.
IMPORTANT: You do NOT have access to any tools, APIs, or real-time data.
You can only answer based on your general knowledge.
If asked about specific real-time information (current weather, hotel prices, availability),
you must clearly state that you don't have access to real-time data.
Answer in the same language as the user's query."""
    
    try:
        result = provider.generate(prompt=user_message, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Chatbot LLM call failed, using simulated fallback: {str(e)}")
        total_time = int((time.time() - start_time) * 1000)
        return jsonify({
            "mode": "chatbot",
            "answer": _simulated_answer(user_message),
            "steps": [],
            "metrics": {
                "latency_ms": total_time,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "steps_count": 0
            }
        })

    total_time = int((time.time() - start_time) * 1000)
    
    return jsonify({
        "mode": "chatbot",
        "answer": result['content'],
        "steps": [],
        "metrics": {
            "latency_ms": total_time,
            "total_tokens": result.get('usage', {}).get('total_tokens', 0),
            "prompt_tokens": result.get('usage', {}).get('prompt_tokens', 0),
            "completion_tokens": result.get('usage', {}).get('completion_tokens', 0),
            "steps_count": 0
        }
    })


def handle_agent(user_message: str, agent: ReActAgent, version: str):
    """Handle agent request with step-by-step tracking."""
    start_time = time.time()
    steps_log = []

    if agent is None:
        total_time = int((time.time() - start_time) * 1000)
        return jsonify({
            "mode": f"agent_{version}",
            "answer": _simulated_answer(user_message),
            "steps": [
                {
                    "step": 1,
                    "type": "error",
                    "content": "LLM unavailable, simulated fallback used"
                }
            ],
            "metrics": {
                "latency_ms": total_time,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "steps_count": 1
            }
        })
    
    # We need to capture steps during the agent run
    # Override the agent's run to capture step details
    current_prompt = user_message
    conversation = ""
    steps = 0
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    final_answer = None
    
    while steps < agent.max_steps:
        steps += 1
        
        full_prompt = current_prompt
        if conversation:
            full_prompt = f"{current_prompt}\n\n{conversation}"
        
        try:
            result = agent.llm.generate(
                prompt=full_prompt,
                system_prompt=agent.get_system_prompt()
            )
        except Exception as e:
            steps_log.append({
                "step": steps,
                "type": "error",
                "content": f"LLM call failed: {str(e)}"
            })
            break
        
        llm_output = result["content"]
        usage = result.get("usage", {})
        latency = result.get("latency_ms", 0)
        
        total_tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_tokens["completion_tokens"] += usage.get("completion_tokens", 0)
        total_tokens["total_tokens"] += usage.get("total_tokens", 0)
        
        # Extract thought
        thought_match = re.search(r'Thought:\s*(.+?)(?:\n|Action:|Final Answer:)', llm_output, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else ""
        
        # Check for Final Answer
        fa = agent._extract_final_answer(llm_output)
        if fa:
            steps_log.append({
                "step": steps,
                "type": "thought",
                "content": thought,
                "latency_ms": latency
            })
            steps_log.append({
                "step": steps,
                "type": "final_answer",
                "content": fa
            })
            final_answer = fa
            break
        
        # Parse Action
        action = agent._parse_action(llm_output)
        
        if action is None:
            steps_log.append({
                "step": steps,
                "type": "thought",
                "content": thought or llm_output[:200],
                "latency_ms": latency
            })
            if version == "v2" and steps < agent.max_steps:
                conversation += f"\n{llm_output}\n\nSystem: You must provide an Action in JSON format or a Final Answer."
                steps_log.append({
                    "step": steps,
                    "type": "retry",
                    "content": "No valid Action found, retrying..."
                })
                continue
            else:
                final_answer = llm_output
                break
        
        # Execute tool
        tool_name = action.get("tool", "")
        tool_args = action.get("args", {})
        observation = agent._execute_tool(tool_name, tool_args)
        
        steps_log.append({
            "step": steps,
            "type": "thought",
            "content": thought,
            "latency_ms": latency
        })
        steps_log.append({
            "step": steps,
            "type": "action",
            "tool": tool_name,
            "args": tool_args,
            "content": f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)})"
        })
        steps_log.append({
            "step": steps,
            "type": "observation",
            "content": observation
        })
        
        conversation += f"\n{llm_output}\nObservation: {observation}\n"
    
    total_time = int((time.time() - start_time) * 1000)
    
    if final_answer is None:
        # Force a final answer
        try:
            final_prompt = f"{current_prompt}\n\n{conversation}\n\nProvide your Final Answer based on the information gathered."
            result = agent.llm.generate(prompt=final_prompt, system_prompt=agent.get_system_prompt())
            final_answer = agent._extract_final_answer(result["content"]) or result["content"]
        except:
            final_answer = "Agent could not complete the request."
    
    return jsonify({
        "mode": f"agent_{version}",
        "answer": final_answer,
        "steps": steps_log,
        "metrics": {
            "latency_ms": total_time,
            "total_tokens": total_tokens.get("total_tokens", 0),
            "prompt_tokens": total_tokens.get("prompt_tokens", 0),
            "completion_tokens": total_tokens.get("completion_tokens", 0),
            "steps_count": steps
        }
    })


@app.route('/api/test-cases', methods=['GET'])
def get_test_cases():
    """Return predefined test cases for quick testing."""
    today = datetime.now()
    next_sat = (today + timedelta(days=(5 - today.weekday()) % 7 or 7)).strftime("%Y-%m-%d")
    
    test_cases = [
        {
            "name": "🌤️ Simple Weather Check",
            "query": f"Thời tiết ở Đà Lạt ngày {next_sat} thế nào?",
            "type": "single_tool"
        },
        {
            "name": "🏨 Hotel Search",
            "query": "Tìm khách sạn ở Đà Lạt dưới 500k/đêm",
            "type": "single_tool"
        },
        {
            "name": "🌿 Multi-step Branching (KEY TEST)",
            "query": (
                "Tôi định đi Đà Lạt vào cuối tuần này. Kiểm tra xem thời tiết thế nào nhé. "
                "Nếu trời không mưa, hãy tìm cho tôi một khách sạn dưới 500k và 2 địa điểm đi dạo ngoài trời. "
                "Nếu trời mưa, hãy gợi ý quán cafe đẹp."
            ),
            "type": "multi_step"
        },
        {
            "name": "☕ Rainy Day Activities",
            "query": "Trời đang mưa ở Hà Nội, gợi ý cho tôi vài quán cafe đẹp",
            "type": "single_tool"
        },
        {
            "name": "🏖️ Nha Trang Trip",
            "query": f"Tôi muốn đi Nha Trang ngày {next_sat}. Kiểm tra thời tiết và tìm khách sạn dưới 1 triệu.",
            "type": "multi_step"
        }
    ]
    
    return jsonify(test_cases)


if __name__ == '__main__':
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")

    print("\n" + "=" * 60)
    print("🌍 Travel Planning Agent — Web UI")
    print("=" * 60)
    print(f"Open in browser: http://localhost:{port}")
    print("=" * 60 + "\n")
    app.run(debug=debug, host='0.0.0.0', port=port)
