# tests/test_ingestion.py

from app.services.embedding_service import embedding_service
from app.db.vector_store import vector_store
from app.services.ingestion_service import ingestion_service


def test_embedding_single():
    """Test that we can embed a single text."""
    print("\nTesting single embedding...")
    text = "I booked train tickets to Chennai last Monday"
    embedding = embedding_service.embed_text(text)

    assert len(embedding) == 384  # MiniLM produces 384 dims
    print(f"Embedding dimensions : {len(embedding)}")
    print(f"First 5 values       : {[round(x, 4) for x in embedding[:5]]}")


def test_chunking():
    """Test that long text gets chunked correctly."""
    print("\nTesting text chunking...")
    long_text = "This is a sentence. " * 200  # 4000 chars

    chunks = embedding_service.chunk_text(long_text, chunk_size=500)
    print(f"Original length : {len(long_text)} chars")
    print(f"Total chunks    : {len(chunks)}")
    print(f"Chunk 1 length  : {len(chunks[0])} chars")

    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)  # small buffer for word boundaries


def test_vector_store_stats():
    """Check current state of ChromaDB."""
    print("\nChecking ChromaDB stats...")
    stats = vector_store.get_collection_stats()
    print(f"Total chunks  : {stats['total_chunks']}")
    print(f"Collection    : {stats['collection_name']}")
    print(f"Persist dir   : {stats['persist_dir']}")


def test_ingest_small_batch():
    """
    Ingest 10 real emails into ChromaDB.
    This is the full pipeline test.
    """
    print("\nRunning full ingestion pipeline (10 emails)...")
    stats = ingestion_service.ingest_emails(max_emails=10)

    print(f"\nIngestion Results:")
    print(f"  Fetched   : {stats.total_fetched}")
    print(f"  Embedded  : {stats.total_embedded}")
    print(f"  Failed    : {stats.total_failed}")
    print(f"  Message   : {stats.message}")

    # Check ChromaDB after ingestion
    db_stats = vector_store.get_collection_stats()
    print(f"\nChromaDB after ingestion:")
    print(f"  Total chunks stored : {db_stats['total_chunks']}")


def test_semantic_search():
    """
    Test semantic search — the core of RAG.
    Search by meaning, not keywords.
    """
    print("\nTesting semantic search...")

    query = "order confirmation or purchase receipt"
    query_embedding = embedding_service.embed_text(query)

    results = vector_store.search(
        query_embedding=query_embedding,
        n_results=3
    )

    if not results:
        print("No results — make sure ingestion ran first")
        return

    print(f"\nQuery: '{query}'")
    print(f"Top {len(results)} results:\n")

    for i, result in enumerate(results):
        print(f"Result {i+1}:")
        print(f"  Subject  : {result['metadata'].get('subject', 'N/A')}")
        print(f"  Sender   : {result['metadata'].get('sender', 'N/A')}")
        print(f"  Distance : {round(result['distance'], 4)}")
        print(f"  Preview  : {result['text'][:100]}...")
        print()


if __name__ == "__main__":
    test_embedding_single()
    test_chunking()
    test_vector_store_stats()
    test_ingest_small_batch()
    test_semantic_search()
    print("\nAll ingestion tests complete!")