import logging
from github import Github, PullRequest
from backend.services.dataset_builder import DatasetBuilder
from backend.core.github_client import get_installation_client

logger = logging.getLogger(__name__)

class PRHistoryScraper:
    def __init__(self, installation_id: int = None, token: str = None):
        """
        Initialize the scraper. 
        Can use an App installation ID, or a personal access token for testing.
        """
        if token:
            self.gh = Github(token)
        elif installation_id:
            self.gh = get_installation_client(installation_id)
        else:
            self.gh = Github() # Unauthenticated
            
        self.dataset_builder = DatasetBuilder()

    def fetch_merged_prs(self, repo_name: str, limit: int = 10):
        """Fetches the last N merged PRs from a repository."""
        logger.info(f"Fetching last {limit} merged PRs from {repo_name}...")
        repo = self.gh.get_repo(repo_name)
        
        # Get closed PRs sorted by creation date descending
        # We have to filter by 'merged' state explicitly because GitHub API 'state=closed' includes unmerged closed PRs.
        pulls = repo.get_pulls(state='closed', sort='created', direction='desc')
        
        merged_prs = []
        count = 0
        for pr in pulls:
            if pr.merged:
                merged_prs.append(pr)
                count += 1
            if count >= limit:
                break
                
        return merged_prs

    def get_pr_files(self, pr: PullRequest.PullRequest):
        """Retrieves changed files for a PR."""
        return list(pr.get_files())

    def get_review_comments(self, pr: PullRequest.PullRequest):
        """Retrieves review comments for a PR."""
        return list(pr.get_review_comments())

    def process_pr_history(self, repo_name: str, limit: int = 10):
        """
        Main pipeline: fetch merged PRs, get comments, and pass mapping to DatasetBuilder.
        Now also passes the repo object so DatasetBuilder can extract actual fixed code.
        """
        merged_prs = self.fetch_merged_prs(repo_name, limit)
        logger.info(f"Found {len(merged_prs)} merged PRs. Extracting reviews...")
        
        # Get the repo object once for efficient API usage in fixed_code extraction
        repo = self.gh.get_repo(repo_name)
        
        for pr in merged_prs:
            logger.debug(f"Processing PR #{pr.number}: {pr.title}")
            comments = self.get_review_comments(pr)
            
            if not comments:
                logger.debug(f"No review comments in PR #{pr.number}. Skipping.")
                continue
                
            logger.info(f"Found {len(comments)} review comments in PR #{pr.number}. Building dataset...")
            # Pass repo object so DatasetBuilder can fetch fixed code from commits
            self.dataset_builder.build_and_store(repo_name, pr.number, comments, repo=repo)
        
        logger.info("Historical PR processing complete.")

