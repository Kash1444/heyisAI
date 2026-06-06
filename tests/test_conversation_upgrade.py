# tests/test_conversation_upgrade.py

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SESSION = "test-memory-001"


def ask(question: str) -> dict:
    res = client.post("/chat", json={
        "message": question,
        "session_id": SESSION,
    })
    return res.json()


def test_memory_conversation():
    print("\n" + "="*60)
    print("TEST: Multi-turn conversation with memory")
    print("="*60)

    # Turn 1 — new question, should search Gmail
    print("\nTurn 1: New question")
    r1 = ask("What was my last Amazon order?")
    print(f"Answer   : {r1['answer'][:200]}")
    print(f"Sources  : {len(r1['sources'])} emails")

    # Turn 2 — follow-up, should use memory NOT Gmail
    print("\nTurn 2: Follow-up (should use memory)")
    r2 = ask("Summarize it")
    print(f"Answer   : {r2['answer'][:200]}")
    print(f"Sources  : {len(r2['sources'])} emails")

    # Turn 3 — another follow-up
    print("\nTurn 3: Another follow-up (should use memory)")
    r3 = ask("Who sent it?")
    print(f"Answer   : {r3['answer'][:200]}")

    # Turn 4 — new topic, should search Gmail fresh
    print("\nTurn 4: New topic (should search Gmail fresh)")
    r4 = ask("Show me emails from LinkedIn")
    print(f"Answer   : {r4['answer'][:200]}")
    print(f"Sources  : {len(r4['sources'])} emails")


if __name__ == "__main__":
    test_memory_conversation()
    print("\n\nConversational memory test complete!")