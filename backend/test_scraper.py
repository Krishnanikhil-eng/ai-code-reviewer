import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Ensure 'backend' is in Python's module path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.pr_history_scraper import PRHistoryScraper

# Set up simple logging for the script
logging.basicConfig(level=logging.INFO, format='%(message)s')

def run_test():
    """
    Tests the PR History Scraper against a public repository.
    """
    # Load environment variables, extracting a token if defined (helpful to avoid rate limits).
    # Ensure the .env file located in the project root directory is loaded correctly.
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    
    github_token = os.getenv("GITHUB_TOKEN") 

    if github_token:
        print("Authenticated: True")
    else:
        print("Authenticated: False")
        
    # Switch to a repo known to have high review discussion density
    repo_name = "tiangolo/fastapi"
    limit = 50 # Increase to 50 to guarantee we hit PRs with comments

    scraper = PRHistoryScraper(token=github_token)

    print(f"Fetching merged PRs for {repo_name}...")
    print("Extracting review comments...")
    scraper.process_pr_history(repo_name, limit=limit)
    
    print("Dataset generation complete.")
    
    dataset_path = Path(__file__).resolve().parent.parent / "database" / "training_data.json"

    if dataset_path.exists():
        size = dataset_path.stat().st_size
        print("Dataset saved to database/training_data.json")
        print(f"Output JSON size: {size} bytes")
    else:
        print("Failed to find training_data.json output.")

if __name__ == "__main__":
    run_test()
