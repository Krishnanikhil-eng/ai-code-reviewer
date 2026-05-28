import os
import logging
from github import Github, Auth
from backend.core.config import settings

logger = logging.getLogger(__name__)

def get_installation_client(installation_id: int) -> Github:
    """
    Returns an authenticated Github client for a specific GitHub App installation.
    Example code to demonstrate GitHub App Authentication.
    """
    if not settings.GITHUB_PRIVATE_KEY_PATH or not os.path.exists(settings.GITHUB_PRIVATE_KEY_PATH):
        logger.warning(f"Private key not found at {settings.GITHUB_PRIVATE_KEY_PATH}.")
        logger.warning("Failing back to unauthenticated client (useful only for public repos and testing PRs without pushing comments).")
        return Github()
        
    try:
        with open(settings.GITHUB_PRIVATE_KEY_PATH, 'r') as file:
            private_key = file.read()
            
        # 1. Authenticate as the GitHub App using the PyGithub Auth logic
        app_auth = Auth.AppAuth(
            app_id=settings.GITHUB_APP_IDENTIFIER,
            private_key=private_key
        )
        
        # 2. To get access to a specific repository, we need an installation token
        auth = app_auth.get_installation_auth(installation_id)
        
        # 3. Return the fully authenticated client for this repository installation
        return Github(auth=auth)

    except Exception as e:
        logger.error(f"Failed to authenticate GitHub App with installation ID {installation_id}: {e}")
        return Github()

def post_pr_comment(repo_full_name: str, pr_number: int, installation_id: int, comment: str) -> int:
    """
    Posts a review comment to the specified Pull Request.
    Returns the GitHub comment ID if successful, None otherwise.
    """
    gh = get_installation_client(installation_id)
    if not gh:
        logger.error("Could not obtain GitHub client to post comment.")
        return None
        
    try:
        repo = gh.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        logger.info(f"Posting review comment to {repo_full_name} PR #{pr_number}")
        created_comment = pr.create_issue_comment(comment)
        return created_comment.id
    except Exception as e:
        logger.error(f"Failed to post comment to {repo_full_name} PR #{pr_number}: {e}")
        return None
