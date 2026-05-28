import logging
import os
import json
from backend.core.github_client import get_installation_client
from backend.services.pr_history_scraper import PRHistoryScraper

logger = logging.getLogger(__name__)

def is_dataset_empty() -> bool:
    """Check if the training dataset is essentially empty."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.normpath(os.path.join(base_dir, "../../database/training_data.json"))
    
    if not os.path.exists(data_file_path):
        return True
    try:
        with open(data_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return len(data) == 0
    except json.JSONDecodeError:
        return True

def process_pull_request(repo_full_name: str, pr_number: int, installation_id: int):
    """
    Background task to process the pull request.
    This fetches the PR diff and simulates preparing it for the Phase 2 AI Analysis.
    """
    logger.info(f"Starting processing for {repo_full_name} PR #{pr_number}")
    try:
        # Phase 2 addition: Check if we need to bootstrap historical data
        if is_dataset_empty():
            logger.info("Training dataset is empty. Triggering historical PR scraping for initial context.")
            scraper = PRHistoryScraper(installation_id=installation_id)
            scraper.process_pr_history(repo_full_name, limit=10)
        
        # 1. Get authenticated client for this GitHub App installation
        gh = get_installation_client(installation_id)
        
        # 2. Fetch the repository and pull request
        repo = gh.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # 3. Fetch the files modified in the PR (The Diff)
        diff_files = pr.get_files()
        
        logger.info(f"Fetched PR #{pr_number}. Total files changed: {diff_files.totalCount}")
        
        for file in diff_files:
            logger.info(f"File modified: {file.filename} (+{file.additions} | -{file.deletions} lines)")
            if file.patch:
                logger.debug(f"Diff patch for {file.filename}:\n{file.patch}")
                
        # (Future Step: Phase 3 AI Analysis happens here)
        logger.info(f"Successfully processed diffs for PR #{pr_number}. Starting AI review...")
        
        # Phase 3 addition: Import the AI reviewer and post comments
        import sys
        
        # Ensure we can import from ai_engine
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if base_dir not in sys.path:
            sys.path.append(base_dir)
            
        from ai_engine.reviewer import generate_review
        from backend.core.github_client import post_pr_comment
        from backend.core.database import save_ai_comment
        
        comments_posted = 0
        for file in diff_files:
            if not file.patch:
                continue
                
            # Only review meaningful code files (skip large generated files, package-lock, etc.)
            if file.filename.endswith(('.lock', '.json', '.md', '.png', '.jpg')):
                continue
                
            logger.info(f"Generating AI review for {file.filename}...")
            
            # Send the PR chunk to the LLM
            # In a real scenario, we might break large patches into smaller chunks
            review_result = generate_review(file.patch)
            
            comment_text = review_result.get("review_comment", "")
            suggested_fix = review_result.get("suggested_fix", "")
            
            if comment_text and comment_text != "No comment provided.":
                # Construct the final comment body
                full_comment = f"### AI Review for `{file.filename}`\n\n{comment_text}\n"
                
                if suggested_fix:
                    full_comment += f"\n**Suggested Fix following Team Patterns:**\n```python\n{suggested_fix}\n```"
                
                # Post the comment to the PR
                comment_id = post_pr_comment(repo_full_name, pr_number, installation_id, full_comment)
                if comment_id:
                    # NEW: Track the comment in our local database for scoring
                    save_ai_comment(
                        github_comment_id=comment_id,
                        repo_full_name=repo_full_name,
                        pr_number=pr_number,
                        file_path=file.filename,
                        code_snippet=file.patch,
                        comment_text=comment_text,
                        suggested_fix=suggested_fix
                    )
                    comments_posted += 1
        
        logger.info(f"AI review complete. Posted {comments_posted} comments for PR #{pr_number}.")

    except Exception as e:
        logger.error(f"Error processing PR #{pr_number} in {repo_full_name}: {e}")
