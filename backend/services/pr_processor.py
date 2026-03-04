import logging
from core.github_client import get_installation_client

logger = logging.getLogger(__name__)

def process_pull_request(repo_full_name: str, pr_number: int, installation_id: int):
    """
    Background task to process the pull request.
    This fetches the PR diff and simulates preparing it for the Phase 2 AI Analysis.
    """
    logger.info(f"Starting processing for {repo_full_name} PR #{pr_number}")
    try:
        # 1. Get authenticated client for this GitHub App installation
        gh = get_installation_client(installation_id)
        
        # 2. Fetch the repository and pull request
        repo = gh.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # 3. Fetch the files modified in the PR (The Diff)
        # Using PyGithub's get_files() to get metadata and patch contents
        diff_files = pr.get_files()
        
        logger.info(f"Fetched PR #{pr_number}. Total files changed: {diff_files.totalCount}")
        
        for file in diff_files:
            logger.info(f"File modified: {file.filename} (+{file.additions} | -{file.deletions} lines)")
            
            # file.patch contains the unified diff corresponding to this specific file
            if file.patch:
                logger.debug(f"Diff patch for {file.filename}:\n{file.patch}")
                
        # (Future Step: Phase 2 Data ingestion into AI Engine happens here)
        logger.info(f"Successfully processed diffs for PR #{pr_number}. Ready for AI processing.")

    except Exception as e:
        logger.error(f"Error processing PR #{pr_number} in {repo_full_name}: {e}")
