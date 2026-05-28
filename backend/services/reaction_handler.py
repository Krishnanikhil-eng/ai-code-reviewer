import logging
from backend.core.database import update_comment_score

logger = logging.getLogger(__name__)

def handle_reaction_event(payload: dict):
    """
    Processes a reaction event (if supported) or a comment-based feedback.
    GitHub 'reaction' events have a 'comment' object and an 'action'.
    """
    action = payload.get("action") # 'created' or 'deleted'
    comment = payload.get("comment", {})
    reaction = payload.get("reaction", {})
    
    if not comment or not reaction:
        return
        
    comment_id = comment.get("id")
    content = reaction.get("content") # 'plus_one', 'minus_one', etc.
    
    delta = 0
    if content == "plus_one":
        delta = 1 if action == "created" else -1
    elif content == "minus_one":
        delta = -1 if action == "created" else 1
        
    if delta != 0:
        logger.info(f"Processing reaction '{content}' ({action}) for comment {comment_id}. Delta: {delta}")
        update_comment_score(comment_id, delta)

def handle_comment_feedback(payload: dict):
    """
    Analyzes a new comment body to see if it's feedback for an AI review.
    Since we store AI reviews in the same issue/PR, a developer might reply.
    """
    action = payload.get("action")
    if action != "created":
        return
        
    comment_body = payload.get("comment", {}).get("body", "").lower()
    # In a real scenario, we'd check if this comment is a reply to an AI comment ID.
    # For now, we search for keywords in the same PR context.
    
    # Simple keyword-based scoring from replies
    delta = 0
    if any(word in comment_body for word in ["lgtm", "good bot", "👍", "great", "correct"]):
        delta = 1
    elif any(word in comment_body for word in ["bad bot", "👎", "wrong", "incorrect", "fix this"]):
        delta = -1
        
    if delta != 0:
        # Note: This is simplified. Ideally we'd map this reply to the specific AI comment.
        # For Phase 4, we'll log it.
        logger.info(f"Detected potential feedback in comment: '{comment_body}'. Simulated delta: {delta}")
        # To truly update the score, we'd need to know WHICH AI comment this refers to.
        # This requires looking up the last AI comment in this PR.
        pass
