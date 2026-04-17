import os
import sys
import time
from dotenv import load_dotenv
from src.core.openai_provider import OpenAIProvider
from src.telemetry.logger import logger

def run_chatbot_baseline(user_input: str = None, interactive: bool = True) -> str:
    """
    Phase 2: Chatbot Baseline using OpenAI.
    A standard LLM call with no access to external tools or the ReAct loop.
    The chatbot can only use its training data — it CANNOT check real weather, 
    search real hotels, or do multi-step reasoning with tools.
    """
    load_dotenv()
    
    provider = OpenAIProvider(model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"))
    
    if interactive and user_input is None:
        print("🤖 Chatbot Baseline Initialized (OpenAI - No Tools)")
        print("=" * 60)
        print("This chatbot has NO access to tools. It can only use its")
        print("training data to answer questions.")
        print("=" * 60)
        user_input = input("\nUser Request: ")
    
    logger.log_event("CHATBOT_START", {
        "input": user_input, 
        "model": provider.model_name,
        "mode": "baseline_no_tools"
    })
    
    start_time = time.time()
    
    system_prompt = """You are a travel planning assistant (Trợ lý Du lịch).
You help users plan trips including weather, hotels, and activities.
IMPORTANT: You do NOT have access to any tools, APIs, or real-time data.
You can only answer based on your general knowledge.
If asked about specific real-time information (current weather, hotel prices, availability),
you must clearly state that you don't have access to real-time data.
Answer in the same language as the user's query."""
    
    print("\n⏳ Thinking...")
    result = provider.generate(
        prompt=user_input, 
        system_prompt=system_prompt
    )
    
    total_time = int((time.time() - start_time) * 1000)
    
    answer = result['content']
    usage = result.get('usage', {})
    
    logger.log_event("CHATBOT_END", {
        "status": "success",
        "latency_ms": total_time,
        "tokens": usage
    })
    
    if interactive:
        print(f"\n{'='*60}")
        print(f"💬 Chatbot Answer:")
        print(f"{'='*60}")
        print(answer)
        print(f"\n📊 Metrics: {total_time}ms | {usage.get('total_tokens', 'N/A')} tokens")
    
    return answer


def run_chatbot_tests():
    """Run chatbot against predefined test cases for Phase 2 evaluation."""
    load_dotenv()
    
    test_cases = [
        {
            "name": "Simple Query",
            "input": "Đà Lạt có gì đẹp?",
            "expected": "General knowledge answer about Da Lat attractions"
        },
        {
            "name": "Weather Query (needs real-time data)",
            "input": "Thời tiết Đà Lạt cuối tuần này thế nào?",
            "expected": "Should admit it cannot check real-time weather"
        },
        {
            "name": "Multi-step Query (THE KEY TEST)",
            "input": (
                "Tôi định đi Đà Lạt vào cuối tuần này. Kiểm tra xem thời tiết thế nào nhé. "
                "Nếu trời không mưa, hãy tìm cho tôi một khách sạn dưới 500k và 2 địa điểm đi dạo ngoài trời. "
                "Nếu trời mưa, hãy gợi ý quán cafe đẹp."
            ),
            "expected": "Cannot do multi-step reasoning without tools — will give generic advice"
        },
        {
            "name": "Budget Hotel Query",
            "input": "Tìm khách sạn ở Đà Lạt dưới 500k một đêm",
            "expected": "Cannot search real hotel data — will give generic recommendations"
        }
    ]
    
    print("\n" + "=" * 70)
    print("🧪 CHATBOT BASELINE TEST SUITE")
    print("=" * 70)
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'─'*70}")
        print(f"📋 Test {i}/{len(test_cases)}: {test['name']}")
        print(f"📝 Input: {test['input'][:80]}...")
        print(f"🎯 Expected: {test['expected']}")
        print(f"{'─'*70}")
        
        try:
            answer = run_chatbot_baseline(user_input=test['input'], interactive=False)
            print(f"\n💬 Chatbot Response:\n{answer[:500]}...")
            results.append({
                "test": test['name'],
                "status": "completed",
                "answer_preview": answer[:200]
            })
        except Exception as e:
            print(f"\n❌ Error: {e}")
            results.append({
                "test": test['name'],
                "status": "error",
                "error": str(e)
            })
        
        logger.log_event("CHATBOT_TEST", {
            "test_name": test['name'],
            "result": results[-1]
        })
    
    print(f"\n{'='*70}")
    print(f"📊 CHATBOT BASELINE RESULTS: {sum(1 for r in results if r['status'] == 'completed')}/{len(test_cases)} completed")
    print(f"{'='*70}")
    
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_chatbot_tests()
    else:
        run_chatbot_baseline()