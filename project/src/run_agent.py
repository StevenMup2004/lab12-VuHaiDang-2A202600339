"""
Agent Runner: Interactive and batch test runner for the ReAct Agent.
Supports both v1 (basic) and v2 (improved) agent versions.
"""

import os
import sys
from dotenv import load_dotenv
from src.core.openai_provider import OpenAIProvider
from src.agent.agent import ReActAgent
from src.tools.tool_registry import get_tools
from src.telemetry.logger import logger


def create_agent(version: str = "v1") -> ReActAgent:
    """Create and return a ReAct agent with all tools registered."""
    load_dotenv()
    
    provider = OpenAIProvider(model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"))
    tools = get_tools()
    
    agent = ReActAgent(
        llm=provider,
        tools=tools,
        max_steps=10,
        version=version
    )
    
    return agent


def run_interactive(version: str = "v1"):
    """Run the agent in interactive mode — chat with it live."""
    agent = create_agent(version)
    
    print(f"\n{'='*60}")
    print(f"🤖 Travel Planning Agent ({version.upper()}) - Interactive Mode")
    print(f"{'='*60}")
    print(f"Model: {agent.llm.model_name}")
    print(f"Tools: {', '.join([t['name'] for t in agent.tools])}")
    print(f"Max Steps: {agent.max_steps}")
    print(f"{'='*60}")
    print("Type 'quit' to exit.\n")
    
    while True:
        user_input = input("\n🧑 You: ").strip()
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        if not user_input:
            continue
        
        print(f"\n🤖 Agent ({version}) is thinking...")
        answer = agent.run(user_input)
        
        print(f"\n{'='*60}")
        print(f"🎯 FINAL ANSWER:")
        print(f"{'='*60}")
        print(answer)
        print(f"{'='*60}")


def run_batch_tests(version: str = "v1"):
    """Run the agent against predefined test cases."""
    agent = create_agent(version)
    
    test_cases = [
        {
            "name": "Simple Weather Check",
            "input": "Thời tiết ở Đà Lạt cuối tuần này thế nào?",
            "expected": "Should call check_weather and return real forecast"
        },
        {
            "name": "Hotel Search",
            "input": "Tìm khách sạn ở Đà Lạt dưới 500k một đêm",
            "expected": "Should call search_hotels with max_price=500000"
        },
        {
            "name": "Multi-step with Branching (THE KEY TEST)",
            "input": (
                "Tôi định đi Đà Lạt vào cuối tuần này. Kiểm tra xem thời tiết thế nào nhé. "
                "Nếu trời không mưa, hãy tìm cho tôi một khách sạn dưới 500k và 2 địa điểm đi dạo ngoài trời. "
                "Nếu trời mưa, hãy gợi ý quán cafe đẹp."
            ),
            "expected": "Should: 1) check_weather → 2) branch based on result → 3) search_hotels + search_activities"
        },
        {
            "name": "Activity Suggestion",
            "input": "Trời đang mưa ở Hà Nội, gợi ý quán cafe đẹp cho tôi",
            "expected": "Should call search_activities with weather_condition='Rain'"
        }
    ]
    
    print(f"\n{'='*70}")
    print(f"🧪 REACT AGENT ({version.upper()}) TEST SUITE")
    print(f"{'='*70}")
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'━'*70}")
        print(f"📋 Test {i}/{len(test_cases)}: {test['name']}")
        print(f"📝 Input: {test['input'][:80]}...")
        print(f"🎯 Expected: {test['expected']}")
        print(f"{'━'*70}")
        
        try:
            answer = agent.run(test['input'])
            
            print(f"\n{'─'*50}")
            print(f"🎯 FINAL ANSWER:")
            print(f"{'─'*50}")
            print(answer[:800])
            
            results.append({
                "test": test['name'],
                "status": "success",
                "answer_preview": answer[:300]
            })
        except Exception as e:
            print(f"\n❌ Error: {e}")
            results.append({
                "test": test['name'],
                "status": "error",
                "error": str(e)
            })
        
        logger.log_event("AGENT_TEST", {
            "version": version,
            "test_name": test['name'],
            "result": results[-1]
        })
    
    print(f"\n{'='*70}")
    print(f"📊 AGENT ({version.upper()}) RESULTS: {sum(1 for r in results if r['status'] == 'success')}/{len(test_cases)} passed")
    print(f"{'='*70}")
    
    return results


if __name__ == "__main__":
    # Parse command line args
    version = "v1"
    mode = "interactive"
    
    for arg in sys.argv[1:]:
        if arg in ["--v1", "-v1"]:
            version = "v1"
        elif arg in ["--v2", "-v2"]:
            version = "v2"
        elif arg in ["--test", "-t"]:
            mode = "test"
        elif arg in ["--interactive", "-i"]:
            mode = "interactive"
    
    if mode == "test":
        run_batch_tests(version)
    else:
        run_interactive(version)
