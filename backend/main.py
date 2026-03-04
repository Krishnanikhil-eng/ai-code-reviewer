import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from core.security import verify_signature
from services.pr_processor import process_pull_request
from core.config import settings

# 1. Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 2. FastAPI instance
app = FastAPI(title="Team-Aware AI Code Reviewer Component", version="0.1.0")

@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Listens to GitHub webhook events, verifies the signature, and triggers 
    processing on 'pull_request' opened/synchronized actions.
    """
    signature = request.headers.get("x-hub-signature-256")
    event_type = request.headers.get("x-github-event")
    
    # Needs raw body exactly as received for valid HMAC SHA256 signature verification
    body = await request.body()
    
    # A. Verify Webhook Signature (Security)
    if not settings.DEBUG and not verify_signature(body, signature):
        logger.warning(f"Invalid webhook signature received.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    logger.debug(f"Received GitHub Webhook Event type: {event_type}")

    # B. We only care about Pull Request events
    if event_type == "pull_request":
        payload = await request.json()
        action = payload.get("action")
        repo_name = payload["repository"]["full_name"]
        
        # Log basic info
        logger.info(f"Received PR event: action={action} repository={repo_name}")
        
        # We process 'opened' (new PR) and 'synchronize' (new commits added)
        if action in ["opened", "synchronize"]:
            pr_number = payload["number"]
            # GitHub Apps get installation_id in payload, useful for auth later
            installation_id = payload.get("installation", {}).get("id")
            
            logger.info(f"Triggering background processing for PR #{pr_number}")
            
            # C. Trigger Background Task
            # FastAPI's background tasks run immediately after the webhook returns a 200 response
            if installation_id or settings.DEBUG:
                background_tasks.add_task(
                    process_pull_request, 
                    repo_full_name=repo_name, 
                    pr_number=pr_number, 
                    installation_id=installation_id
                )
            else:
                logger.warning("No installation ID found in payload.")
            
            return {"status": "accepted", "message": f"Processing PR #{pr_number} securely."}
            
    return {"status": "ignored", "message": f"Event '{event_type}' ignored, listening only for target events."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
