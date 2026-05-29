import logging
from backend.core.database import (
    update_comment_score,
    is_ai_comment,
    get_all_ai_comments_for_pr
)

logger = logging.getLogger(__name__)

# Keywords used to detect positive or negative feedback from developer replies
POSITIVE_KEYWORDS = [
    "lgtm", "good bot", "👍", "+1", "great", "correct", "helpful",
    "thanks", "thank you", "useful", "nice catch", "good catch",
    "agree", "makes sense", "good point", "well spotted"
]
NEGATIVE_KEYWORDS = [
    "bad bot", "👎", "-1", "wrong", "incorrect", "fix this",
    "not helpful", "irrelevant", "false positive", "disagree",
    "nope", "doesn't apply", "not relevant", "bad suggestion"
]


def handle_reaction_event(payload: dict):
    """
    Processes a GitHub reaction event (thumbs up/down on comments).
    GitHub 'reaction' events have a 'comment' object and an 'action'.
    """
    action = payload.get("action")  # 'created' or 'deleted'
    comment = payload.get("comment", {})
    reaction = payload.get("reaction", {})

    if not comment or not reaction:
        return

    comment_id = comment.get("id")
    content = reaction.get("content")  # 'plus_one', 'minus_one', etc.

    delta = 0
    if content == "plus_one":
        delta = 1 if action == "created" else -1
    elif content == "minus_one":
        delta = -1 if action == "created" else 1

    if delta != 0:
        logger.info(f"Processing reaction '{content}' ({action}) for comment {comment_id}. Delta: {delta}")
        update_comment_score(comment_id, delta)


def _detect_sentiment_with_llm(comment_body: str) -> int:
    """
    Uses the local Ollama LLM to classify developer feedback sentiment
    when keyword detection falls back to neutral.
    Returns +1 for positive, -1 for negative, 0 for neutral.
    """
    from backend.core.config import settings
    import requests
    import json

    prompt = f"""You are an assistant that classifies developer feedback comments on AI review suggestions.
Classify the following feedback as either:
- "positive" (agreement, thank you, good catch, helpful suggestion, correct fix)
- "negative" (disagreement, wrong logic, bad suggestion, incorrect fix, not helpful, ignore this suggestion)
- "neutral" (unrelated questions, discussion, comments not expressing explicit approval/disapproval)

Respond with exactly a single JSON object containing a key "sentiment" with the value "positive", "negative", or "neutral". Do not write any other text or markdown blocks.

Feedback: "{comment_body}"
"""
    
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(settings.OLLAMA_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        result_data = response.json()
        reply_text = result_data.get("response", "").strip()

        # Parse JSON
        parsed = json.loads(reply_text)
        sentiment = parsed.get("sentiment", "neutral").lower()
        if sentiment == "positive":
            logger.info(f"LLM-Assisted Sentiment: Positive feedback detected for comment '{comment_body[:40]}...'")
            return 1
        elif sentiment == "negative":
            logger.info(f"LLM-Assisted Sentiment: Negative feedback detected for comment '{comment_body[:40]}...'")
            return -1
    except Exception as e:
        logger.warning(f"Failed to perform LLM sentiment fallback classification: {e}")

    return 0


def _detect_sentiment(comment_body: str) -> int:
    """
    Analyzes comment text for positive or negative feedback keywords.
    Falls back to LLM-assisted classification if keyword mapping is neutral.
    Returns +1 for positive, -1 for negative, 0 for neutral.
    """
    body_lower = comment_body.lower().strip()

    if any(keyword in body_lower for keyword in NEGATIVE_KEYWORDS):
        return -1
    elif any(keyword in body_lower for keyword in POSITIVE_KEYWORDS):
        return 1
        
    return _detect_sentiment_with_llm(comment_body)


def _find_target_ai_comment(comment_body: str, repo_full_name: str, pr_number: int) -> dict:
    """
    Maps a developer's reply to the specific AI comment it refers to.
    
    Strategy (in priority order):
    1. If the reply quotes a filename from an AI comment, match that specific comment.
    2. Otherwise, default to the most recent AI comment on the PR.
    """
    # Get all AI comments for this PR
    ai_comments = get_all_ai_comments_for_pr(repo_full_name, pr_number)

    if not ai_comments:
        return None

    # Strategy 1: Check if the reply mentions a specific file that an AI comment reviewed
    body_lower = comment_body.lower()
    for ai_comment in ai_comments:
        file_path = ai_comment.get("file_path", "")
        if file_path:
            # Check if the reply mentions the filename (e.g., "main.py" or "backend/main.py")
            filename = file_path.split("/")[-1].lower()
            if filename in body_lower or file_path.lower() in body_lower:
                logger.info(f"Matched feedback to AI comment on file '{file_path}' via filename mention.")
                return ai_comment

    # Strategy 2: Fall back to the most recent AI comment on this PR
    logger.info(f"No specific file match found. Defaulting to most recent AI comment on PR #{pr_number}.")
    return ai_comments[0]  # Already sorted by created_at DESC


def handle_comment_feedback(payload: dict):
    """
    Analyzes a new issue_comment to determine if it's developer feedback for an AI review.
    
    Workflow:
    1. Extracts PR number and repo from the payload.
    2. Checks the comment isn't from the AI itself (avoids self-scoring).
    3. Detects sentiment (positive/negative) from keywords.
    4. Maps the reply to the specific AI comment using file mentions or recency.
    5. Updates the matched AI comment's score in the database.
    """
    action = payload.get("action")
    if action != "created":
        return

    comment = payload.get("comment", {})
    issue = payload.get("issue", {})
    repo = payload.get("repository", {})

    comment_body = comment.get("body", "").strip()
    comment_id = comment.get("id")
    repo_full_name = repo.get("full_name", "")
    pr_number = issue.get("number")

    # Validate required fields
    if not comment_body or not repo_full_name or not pr_number:
        logger.debug("Missing required fields in issue_comment payload. Skipping.")
        return

    # Ensure this is a PR comment (issues also trigger issue_comment events)
    pull_request = issue.get("pull_request")
    if not pull_request:
        logger.debug("Comment is on an issue, not a PR. Skipping.")
        return

    # Don't score our own comments
    if is_ai_comment(comment_id):
        logger.debug(f"Comment {comment_id} is from the AI itself. Skipping.")
        return

    # Detect sentiment from the reply text
    delta = _detect_sentiment(comment_body)
    if delta == 0:
        logger.debug(f"No feedback sentiment detected in comment: '{comment_body[:80]}...'")
        return

    # Find the target AI comment to attribute the feedback to
    target = _find_target_ai_comment(comment_body, repo_full_name, pr_number)

    if target:
        ai_comment_id = target["github_comment_id"]
        logger.info(
            f"Feedback mapped: delta={delta:+d} for AI comment {ai_comment_id} "
            f"(file: {target.get('file_path', 'N/A')}) on {repo_full_name} PR #{pr_number}. "
            f"Trigger: '{comment_body[:60]}...'"
        )
        update_comment_score(ai_comment_id, delta)
    else:
        logger.info(f"No AI comments found for {repo_full_name} PR #{pr_number}. Feedback ignored.")


def handle_review_comment_feedback(payload: dict):
    """
    Analyzes a new pull_request_review_comment to determine if it's developer feedback for an AI review.
    Handles nested threads using `in_reply_to_id` directly, and falls back to heuristics if needed.
    """
    action = payload.get("action")
    if action != "created":
        return

    comment = payload.get("comment", {})
    pull_request = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    comment_body = comment.get("body", "").strip()
    comment_id = comment.get("id")
    in_reply_to_id = comment.get("in_reply_to_id")
    repo_full_name = repo.get("full_name", "")
    pr_number = pull_request.get("number")

    # Validate required fields
    if not comment_body or not repo_full_name or not pr_number:
        logger.debug("Missing required fields in pull_request_review_comment payload. Skipping.")
        return

    # Don't score our own comments
    if is_ai_comment(comment_id):
        logger.debug(f"Comment {comment_id} is from the AI itself. Skipping.")
        return

    # Detect sentiment from the reply text
    delta = _detect_sentiment(comment_body)
    if delta == 0:
        logger.debug(f"No feedback sentiment detected in comment: '{comment_body[:80]}...'")
        return

    # Determine which AI comment to map the feedback to
    target_ai_comment_id = None

    if in_reply_to_id:
        # Strategy 1: Threaded reply. If the parent comment is our AI comment, map to it directly
        if is_ai_comment(in_reply_to_id):
            target_ai_comment_id = in_reply_to_id
            logger.info(f"Direct thread match found. Mapping feedback to parent AI comment {in_reply_to_id}.")

    if not target_ai_comment_id:
        # Strategy 2: Fall back to heuristics if not in a thread or parent not found in DB
        target = _find_target_ai_comment(comment_body, repo_full_name, pr_number)
        if target:
            target_ai_comment_id = target["github_comment_id"]
            logger.info(f"Fallback matched feedback to AI comment {target_ai_comment_id} using heuristics.")

    if target_ai_comment_id:
        logger.info(
            f"Feedback mapped: delta={delta:+d} for AI comment {target_ai_comment_id} "
            f"on {repo_full_name} PR #{pr_number}. "
            f"Trigger: '{comment_body[:60]}...'"
        )
        update_comment_score(target_ai_comment_id, delta)
    else:
        logger.info(f"No target AI comment found for {repo_full_name} PR #{pr_number}. Feedback ignored.")

