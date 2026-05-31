# tests/test_agent.py

from app.agents.memory_agent import memory_agent


def test_agent_with_questions():
    questions = [
        "What is the latest update from Lenovo?",
        "Show me recent emails from Reddit",
        "List my most recent inbox emails",
    ]

    for question in questions:
        print(f"\n{'='*60}")
        print(f"Question : {question}")
        print(f"{'='*60}")

        result = memory_agent.run(question)

        if result.get("tools_used"):
            for t in result["tools_used"]:
                print(f"Tool used : {t['tool']}")
                print(f"Params    : {t['params']}")
                print(f"Result    : {t['result_summary']}")

        print(f"\nAnswer:\n{result['answer']}")


if __name__ == "__main__":
    test_agent_with_questions()
    print("\n\nAgent tests complete!")