# tests/test_rag.py

#python -m tests.test_rag
#above cmd line ah use for this file only 

from app.services.rag_service import rag_service


def test_rag_with_real_question():
    """
    Test the full RAG pipeline end to end.
    Ask a real question and see what Gemini says.
    """
    questions = [
        "What emails did I receive recently?",
        "Any emails from financial services?",
        "What is the latest update from Airtel?",
        "what was my last order from Amazon?",
    ]

    for question in questions:
        print(f"\n{'='*60}")
        print(f"Question : {question}")
        print(f"{'='*60}")

        result = rag_service.answer(question)

        print(f"Has context      : {result['has_context']}")
        print(f"Chunks retrieved : {result['retrieved_count']}")
        print(f"\nAnswer:\n{result['answer']}")

        if result['sources']:
            print(f"\nSources used:")
            for src in result['sources']:
                print(
                    f"  - {src['subject'][:50]} "
                    f"(relevance: {src['relevance_score']})"
                )


def test_rag_no_context():
    """
    Test that we get a clarification question when
    no relevant emails exist.
    """
    print(f"\n{'='*60}")
    print("Testing clarification question (no context)...")
    print(f"{'='*60}")

    result = rag_service.answer(
        "What did my doctor say about my prescription last March?"
    )

    print(f"Has context : {result['has_context']}")
    print(f"Response    : {result['answer']}")


if __name__ == "__main__":
    test_rag_with_real_question()
    test_rag_no_context()
    print("\n\nRAG pipeline tests complete!")