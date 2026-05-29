import os
import json
import uuid
import sys

# Ensure we can import from vector_store
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from vector_store.chroma_client import add_embedding


def main():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "Error: sentence-transformers is not installed. Please run `pip install sentence-transformers chromadb`"
        )
        sys.exit(1)

    # Load the training data
    data_path = os.path.join(
        os.path.dirname(__file__), "database", "training_data.json"
    )
    if not os.path.exists(data_path):
        print(f"Error: Could not find training data at {data_path}")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {data_path} is not valid JSON")
            sys.exit(1)

    if not data:
        print("No data found in training_data.json.")
        return

    # Initialize the sentence transformer model
    print("Loading sentence-transformers model 'all-MiniLM-L6-v2'...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"Found {len(data)} review examples. Generating embeddings...")

    success_count = 0
    for item in data:
        problematic_code = item.get("problematic_code")
        review_comment = item.get("review_comment", "")
        fixed_code = item.get("fixed_code", "")

        if not problematic_code:
            continue

        # Generate embedding for the problematic code
        embedding = model.encode(problematic_code).tolist()

        # Prepare metadata mapping.
        # ChromaDB requires metadata values to be strings, ints, floats, or bools.
        metadata = {
            "problematic_code": problematic_code,
            "review_comment": review_comment if review_comment is not None else "",
            "fixed_code": fixed_code if fixed_code is not None else "",
        }

        # Using a UUID for unique ID
        item_id = str(uuid.uuid4())

        # Add to ChromaDB
        add_embedding(id=item_id, embedding=embedding, metadata=metadata)
        success_count += 1
        print(f"[{success_count}/{len(data)}] Processed item {item_id}")

    print(
        f"\nSuccess! {success_count} embeddings and metadata have been stored in ChromaDB."
    )


if __name__ == "__main__":
    main()
