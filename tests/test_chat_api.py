# tests/test_chat_api.py

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_chat_stats():
    """Check vector DB stats via API."""
    print("\nTesting GET /chat/stats...")
    response = client.get("/chat/stats")

    assert response.status_code == 200
    data = response.json()

    print(f"Total chunks : {data['total_chunks']}")
    print(f"Is ready     : {data['is_ready']}")
    print(f"Message      : {data['message']}")


def test_chat_ask():
    """Ask a real question through the API."""
    print("\nTesting POST /chat/ask...")

    payload = {
        "question": "What is the latest update from Airtel?",
        "n_results": 5
    }

    response = client.post("/chat/ask", json=payload)

    assert response.status_code == 200
    data = response.json()

    print(f"Has context      : {data['has_context']}")
    print(f"Chunks retrieved : {data['retrieved_count']}")
    print(f"Sources count    : {len(data['sources'])}")
    print(f"\nAnswer:\n{data['answer']}")

    if data['sources']:
        print("\nSources:")
        for src in data['sources']:
            print(f"  - {src['subject'][:50]} ({src['relevance_score']})")


def test_chat_ask_validation():
    """Test that invalid requests are rejected properly."""
    print("\nTesting input validation...")

    # Too short question
    response = client.post("/chat/ask", json={"question": "hi"})
    assert response.status_code == 422  # Unprocessable Entity
    print(f"Short question rejected with: {response.status_code} ✓")

    # Missing question field
    response = client.post("/chat/ask", json={})
    assert response.status_code == 422
    print(f"Missing field rejected with: {response.status_code} ✓")


def test_docs_available():
    """Verify the auto-generated docs are accessible."""
    print("\nTesting /docs availability...")
    response = client.get("/docs")
    assert response.status_code == 200
    print("API docs available at /docs ✓")


if __name__ == "__main__":
    test_chat_stats()
    test_chat_ask()
    test_chat_ask_validation()
    test_docs_available()
    print("\n\nAll Chat API tests passed!")