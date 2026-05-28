import json
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DatasetBuilder:
    def __init__(self, data_file_path: str = "../../database/training_data.json"):
        # Ensure path is relative to the backend/services/ directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_file_path = os.path.normpath(os.path.join(base_dir, data_file_path))
        
        # Initialize file if it doesn't exist
        if not os.path.exists(self.data_file_path):
            os.makedirs(os.path.dirname(self.data_file_path), exist_ok=True)
            self._save_data([])

    def _load_data(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.data_file_path):
            return []
        try:
            with open(self.data_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def _save_data(self, data: List[Dict[str, Any]]):
        with open(self.data_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _fetch_file_at_commit(self, repo, file_path: str, commit_sha: str) -> str:
        """
        Fetches the content of a file from GitHub at a specific commit SHA.
        Returns the decoded file content as a string, or None on failure.
        """
        try:
            contents = repo.get_contents(file_path, ref=commit_sha)
            return contents.decoded_content.decode('utf-8')
        except Exception as e:
            logger.warning(f"Could not fetch '{file_path}' at commit {commit_sha[:7]}: {e}")
            return None

    def _extract_fixed_code(self, repo, comment) -> str:
        """
        Extracts the fixed version of code by comparing file content at two commits:
        - original_commit_id: the commit where the review comment was placed (before fix)
        - commit_id: the latest commit on the PR (after the developer addressed the review)

        If the commits differ, fetches the file at commit_id and extracts a focused
        window of lines around the commented line as the "fixed" code.
        """
        original_sha = getattr(comment, 'original_commit_id', None)
        latest_sha = getattr(comment, 'commit_id', None)
        file_path = getattr(comment, 'path', None)

        if not latest_sha or not file_path:
            return ""

        # If both commits are the same, no fix has been pushed yet
        if original_sha and original_sha == latest_sha:
            return ""

        try:
            # Fetch the file at the latest commit (after fix)
            fixed_content = self._fetch_file_at_commit(repo, file_path, latest_sha)
            if not fixed_content:
                return ""

            lines = fixed_content.split('\n')

            # Try to extract a focused window around the commented line
            target_line = getattr(comment, 'line', None) or getattr(comment, 'original_line', None)

            if target_line and target_line > 0:
                window = 10  # lines above and below the target
                start = max(0, target_line - window - 1)
                end = min(len(lines), target_line + window)
                return '\n'.join(lines[start:end])

            # Fallback: return full file if it's small enough
            if len(fixed_content) <= 3000:
                return fixed_content

            # For large files, truncate to keep dataset manageable
            return fixed_content[:3000] + "\n# ... (truncated)"

        except Exception as e:
            logger.warning(f"Error extracting fixed code for {file_path}: {e}")
            return ""

    def extract_from_comment(self, repo_name: str, pr_number: int, comment: Any, repo=None) -> Dict[str, Any]:
        """
        Extracts the problematic code and fixed code from a GitHub PullRequestReviewComment.
        Uses the diff_hunk as the problematic code context.
        If a repo object is provided, fetches the actual fixed code from the later commit.
        """
        problematic_code = comment.diff_hunk if comment.diff_hunk else ""

        # Extract fixed code via GitHub API if repo object is available
        fixed_code = ""
        if repo:
            fixed_code = self._extract_fixed_code(repo, comment)
            if fixed_code:
                logger.debug(f"Successfully extracted fixed code for {comment.path}")

        example = {
            "repo": repo_name,
            "pr_number": pr_number,
            "file": comment.path,
            "language": comment.path.split('.')[-1] if '.' in comment.path else "unknown",
            "problematic_code": problematic_code,
            "review_comment": comment.body,
            "fixed_code": fixed_code,
            "commit_before": comment.original_commit_id,
            "commit_after": comment.commit_id
        }
        return example

    def build_and_store(self, repo_name: str, pr_number: int, comments: List[Any], repo=None):
        """
        Builds dataset examples from PR comments and stores them in the JSON file.
        If repo (PyGithub Repository object) is provided, extracts actual fixed code via GitHub API.
        """
        data = self._load_data()
        new_records = 0
        
        LOW_VALUE_COMMENTS = ["nit", "lgtm", "typo", "thanks", "nice"]
        
        for comment in comments:
            review_comment = comment.body.strip()
            
            # We skip short or low-value comments to keep data clean
            if len(review_comment) < 15:
                continue
                
            comment_text = review_comment.lower()
            if comment_text in LOW_VALUE_COMMENTS:
                continue

            record = self.extract_from_comment(repo_name, pr_number, comment, repo=repo)
            
            # Simple deduplication check based on PR and comment original line
            is_duplicate = any(
                r.get('pr_number') == record['pr_number'] and r.get('file') == record['file'] and r.get('review_comment') == record['review_comment']
                for r in data
            )

            if not is_duplicate:
                data.append(record)
                new_records += 1

        if new_records > 0:
            self._save_data(data)
            logger.info(f"Added {new_records} new examples to training data from PR #{pr_number}")
