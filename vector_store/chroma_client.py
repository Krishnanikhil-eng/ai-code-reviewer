import os
import chromadb

# Initialize the persistent client
_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
client = chromadb.PersistentClient(path=_db_path)


def ensure_collection():
    """Create or retrieve the 'code_reviews' collection.
    This helper ensures idempotent collection creation and can be used
    by other modules to obtain a consistent collection instance.
    """
    return client.get_or_create_collection(name="code_reviews")


def add_embedding(id: str, embedding: list[float], metadata: dict):
    """Add a single embedding and its associated metadata to the collection."""
    collection = ensure_collection()
    collection.add(ids=[id], embeddings=[embedding], metadatas=[metadata])


def query_similar(embedding: list[float], n_results: int = 3):
    """Query the collection for the most similar embeddings."""
    collection = ensure_collection()
    results = collection.query(query_embeddings=[embedding], n_results=n_results)
    return results


def upsert_embedding(id: str, embedding: list[float], metadata: dict):
    """Upsert an embedding and its associated metadata to the collection."""
    collection = ensure_collection()
    collection.upsert(ids=[id], embeddings=[embedding], metadatas=[metadata])
