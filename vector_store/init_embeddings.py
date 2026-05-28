import argparse
from embedder import main as run_main

def main():
    parser = argparse.ArgumentParser(description="Initialize embeddings for training data.")
    parser.add_argument("--force", action="store_true", help="Reprocess all data even if embeddings exist.")
    args = parser.parse_args()
    # Currently, embedder.main always processes all data; the flag is reserved for future use.
    run_main()

if __name__ == "__main__":
    main()
