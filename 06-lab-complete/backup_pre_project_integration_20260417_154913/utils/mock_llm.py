"""Mock LLM helpers for local and cloud demos."""
import random
import time


MOCK_RESPONSES = {
    "default": [
        "This is a mock AI response from the production-ready Day 12 app.",
        "Agent is healthy and responding correctly (mock response).",
        "Your question was received by the cloud-deployed agent.",
    ],
    "docker": ["Docker packages the app so it runs consistently everywhere."],
    "deploy": ["Deployment moves your app from local machine to cloud service."],
    "health": ["All systems operational. Service is healthy."],
}


def ask(question: str, delay: float = 0.1) -> str:
    """Return a deterministic-feeling mock response with small latency."""
    time.sleep(delay + random.uniform(0, 0.05))

    q = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in q:
            return random.choice(responses)

    return random.choice(MOCK_RESPONSES["default"])


def ask_stream(question: str):
    """Yield a token-like stream for streaming demos."""
    response = ask(question)
    for token in response.split():
        time.sleep(0.05)
        yield token + " "
