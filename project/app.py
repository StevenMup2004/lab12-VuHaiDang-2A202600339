"""
Flask Web Application for Travel Planning Agent.
Provides a beautiful chat UI to interact with both the Chatbot and ReAct Agent.
"""

import os
import sys
import json
import time
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv

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


def init_systems():
    """Lazy initialization of LLM systems."""
    global provider, tools, agent_v1, agent_v2
    if provider is None:
        provider = OpenAIProvider(model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"))
        tools = get_tools()
        agent_v1 = ReActAgent(llm=provider, tools=tools, max_steps=10, version="v1")
        agent_v2 = ReActAgent(llm=provider, tools=tools, max_steps=10, version="v2")


@app.route('/')
def index():
    return render_template('index.html')


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
    
    system_prompt = """You are a travel planning assistant (Trợ lý Du lịch).
You help users plan trips including weather, hotels, and activities.
IMPORTANT: You do NOT have access to any tools, APIs, or real-time data.
You can only answer based on your general knowledge.
If asked about specific real-time information (current weather, hotel prices, availability),
you must clearly state that you don't have access to real-time data.
Answer in the same language as the user's query."""
    
    result = provider.generate(prompt=user_message, system_prompt=system_prompt)
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
    print("\n" + "=" * 60)
    print("🌍 Travel Planning Agent — Web UI")
    print("=" * 60)
    print("Open in browser: http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
