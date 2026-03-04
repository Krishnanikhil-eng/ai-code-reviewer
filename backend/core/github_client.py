import os
import logging
from github import Github, Auth
from core.config import settings

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
