# tests/test_conversation.py

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_multi_turn_conversation():
    """
    Simulate a real multi-turn conversation.
    Each message builds on the previous one.
    """
    session_id = "test-session-001"

    turns = [
        "List my most recent inbox emails",
        "Who sent me emails about jobs?",
        "What was the subject of the LinkedIn email?",
    ]

    for i, question in enumerate(turns):
        print(f"\n{'='*60}")
        print(f"Turn {i+1}: {question}")
        print(f"{'='*60}")

        response = client.post("/chat/conversation", json={
            "question": question,
            "session_id": session_id,
        })

        assert response.status_code == 200
        data = response.json()

        print(f"Answer: {data['answer'][:300]}")

        if data["tools_used"]:
            print(f"Tool  : {data['tools_used'][0]['tool']}")

        print(f"History turns so far: {len(data['history'])}")


if __name__ == "__main__":
    test_multi_turn_conversation()
    print("\n\nConversation tests complete!")