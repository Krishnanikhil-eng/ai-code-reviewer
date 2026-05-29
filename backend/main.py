import os
import logging
import io
import asyncio
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import List
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from backend.core.security import verify_signature
from backend.services.pr_processor import process_pull_request
from backend.core.config import settings

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
        logger.warning("Invalid webhook signature received.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    logger.debug(f"Received GitHub Webhook Event type: {event_type}")

    # B. Route events
    if event_type == "pull_request":
        payload = await request.json()
        action = payload.get("action")
        repo_name = payload["repository"]["full_name"]
        
        logger.info(f"Received PR event: action={action} repository={repo_name}")
        
        if action in ["opened", "synchronize"]:
            pr_number = payload["number"]
            installation_id = payload.get("installation", {}).get("id")
            
            logger.info(f"Triggering background processing for PR #{pr_number}")
            
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

    elif event_type == "reaction":
        # NEW Phase 4: Handle reactions to comments
        payload = await request.json()
        from backend.services.reaction_handler import handle_reaction_event
        background_tasks.add_task(handle_reaction_event, payload)
        # Real-time background retraining
        from retrain import run_retraining
        background_tasks.add_task(run_retraining)
        return {"status": "accepted", "message": "Reaction received."}

    elif event_type == "issue_comment":
        # Phase 4: Handle comment-based feedback on AI reviews
        payload = await request.json()
        from backend.services.reaction_handler import handle_reaction_event, handle_comment_feedback
        
        if "reaction" in payload:
            # Reactions on comments can sometimes trigger issue_comment events
            background_tasks.add_task(handle_reaction_event, payload)
        else:
            # New comment created — check if it's developer feedback on an AI review
            background_tasks.add_task(handle_comment_feedback, payload)
        # Real-time background retraining
        from retrain import run_retraining
        background_tasks.add_task(run_retraining)
        return {"status": "accepted", "message": "Comment activity recorded."}
            
    elif event_type == "pull_request_review_comment":
        # Phase 4: Handle replies inside review comment threads
        payload = await request.json()
        from backend.services.reaction_handler import handle_review_comment_feedback
        background_tasks.add_task(handle_review_comment_feedback, payload)
        # Real-time background retraining
        from retrain import run_retraining
        background_tasks.add_task(run_retraining)
        return {"status": "accepted", "message": "Review comment activity recorded."}

    return {"status": "ignored", "message": f"Event '{event_type}' ignored, listening only for target events."}


# -------------------------------------------------------------
# ENTERPRISE DASHBOARD API ENDPOINTS & WEBSOCKETS
# -------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/dashboard/stats")
def get_stats():
    from backend.core.database import get_connection
    try:
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM ai_comments").fetchone()[0]
            scored = conn.execute("SELECT COUNT(*) FROM ai_comments WHERE score != 0").fetchone()[0]
            positive = conn.execute("SELECT COUNT(*) FROM ai_comments WHERE score > 0").fetchone()[0]
            negative = conn.execute("SELECT COUNT(*) FROM ai_comments WHERE score < 0").fetchone()[0]
            repos = conn.execute("SELECT COUNT(DISTINCT repo_full_name) FROM ai_comments").fetchone()[0]
            
            engagement = round((scored / total) * 100, 2) if total > 0 else 0.0
            helpfulness = round((positive / scored) * 100, 2) if scored > 0 else 0.0
            false_positive = round((negative / scored) * 100, 2) if scored > 0 else 0.0
            
            return {
                "total_reviews": total,
                "scored_reviews": scored,
                "positive_reviews": positive,
                "negative_reviews": negative,
                "engagement_rate": engagement,
                "helpfulness_rate": helpfulness,
                "false_positive_rate": false_positive,
                "unique_repos": repos
            }
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/reviews")
def get_reviews(
    page: int = 1,
    size: int = 10,
    repo: str = None,
    pr: int = None,
    sentiment: str = None,
    search: str = None
):
    from backend.core.database import get_connection
    from datetime import datetime
    
    query = "SELECT id, github_comment_id, repo_full_name, pr_number, file_path, code_snippet, comment_text, suggested_fix, score, created_at FROM ai_comments WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM ai_comments WHERE 1=1"
    params = []
    
    if repo:
        query += " AND repo_full_name = ?"
        count_query += " AND repo_full_name = ?"
        params.append(repo)
    if pr:
        query += " AND pr_number = ?"
        count_query += " AND pr_number = ?"
        params.append(pr)
    if sentiment == "positive":
        query += " AND score > 0"
        count_query += " AND score > 0"
    elif sentiment == "negative":
        query += " AND score < 0"
        count_query += " AND score < 0"
    elif sentiment == "neutral":
        query += " AND score = 0"
        count_query += " AND score = 0"
        
    if search:
        query += " AND (code_snippet LIKE ? OR comment_text LIKE ? OR file_path LIKE ?)"
        count_query += " AND (code_snippet LIKE ? OR comment_text LIKE ? OR file_path LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
        
    query += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    
    try:
        with get_connection() as conn:
            count_params = params.copy()
            total_records = conn.execute(count_query, count_params).fetchone()[0]
            
            page_params = params + [size, (page - 1) * size]
            cursor = conn.execute(query, page_params)
            rows = cursor.fetchall()
            
            reviews = []
            for r in rows:
                created_at_str = r[9]
                score_val = float(r[8])
                
                try:
                    created_time = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                    age_days = (datetime.utcnow() - created_time).days
                    if age_days < 0:
                        age_days = 0
                except Exception:
                    age_days = 0
                    
                decayed_score = score_val * (0.98 ** age_days)
                
                reviews.append({
                    "id": r[0],
                    "github_comment_id": r[1],
                    "repo_full_name": r[2],
                    "pr_number": r[3],
                    "file_path": r[4],
                    "code_snippet": r[5],
                    "comment_text": r[6],
                    "suggested_fix": r[7],
                    "score": score_val,
                    "decayed_score": round(decayed_score, 2),
                    "age_days": age_days,
                    "created_at": created_at_str
                })
                
            return {
                "total": total_records,
                "page": page,
                "size": size,
                "reviews": reviews
            }
    except Exception as e:
        logger.error(f"Failed to fetch reviews: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/settings")
def get_settings(repo: str):
    from backend.core.database import get_repo_settings
    return get_repo_settings(repo)

@app.get("/api/dashboard/config")
def get_dashboard_config():
    return {
        "platform_name": settings.DASHBOARD_PLATFORM_NAME,
        "platform_subtitle": settings.DASHBOARD_PLATFORM_SUBTITLE,
        "logo_icon_class": settings.DASHBOARD_LOGO_ICON_CLASS,
        "login_logo_icon_class": settings.DASHBOARD_LOGIN_LOGO_ICON_CLASS,
        "browser_title": settings.DASHBOARD_BROWSER_TITLE
    }

@app.post("/api/dashboard/settings")
async def save_settings(request: Request):
    from backend.core.database import save_repo_settings, log_action
    data = await request.json()
    repo = data.get("repo_full_name")
    strictness = int(data.get("strictness", 3))
    review_mode = data.get("review_mode", "standard")
    custom_prompt = data.get("custom_prompt", "")
    retrieval_depth = int(data.get("retrieval_depth", 3))
    role = data.get("role", "Developer")
    
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can modify settings.")
        
    success = save_repo_settings(repo, strictness, review_mode, custom_prompt, retrieval_depth)
    if success:
        log_action(role, f"Updated settings for {repo}", f"mode={review_mode}, strictness={strictness}")
        await manager.broadcast({"event": "refresh"})
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings.")

@app.get("/api/dashboard/status")
async def get_status():
    from backend.core.database import get_connection, get_audit_logs
    from vector_store.chroma_client import ensure_collection
    
    status = {
        "database": "online",
        "chromadb": "online",
        "ollama": "online",
        "github_app": "configured",
        "database_latency_ms": 0,
        "chromadb_latency_ms": 0,
        "ollama_latency_ms": 0,
        "audit_logs": []
    }
    
    t0 = time.time()
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        status["database_latency_ms"] = round((time.time() - t0) * 1000, 2)
    except Exception:
        status["database"] = "offline"
        
    t0 = time.time()
    try:
        collection = ensure_collection()
        collection.count()
        status["chromadb_latency_ms"] = round((time.time() - t0) * 1000, 2)
    except Exception:
        status["chromadb"] = "offline"
        
    t0 = time.time()
    try:
        response = requests.get(settings.OLLAMA_API_URL.replace("/api/generate", ""), timeout=2)
        if response.status_code == 200 or response.status_code == 404:
            status["ollama"] = "online"
        else:
            status["ollama"] = "degraded"
        status["ollama_latency_ms"] = round((time.time() - t0) * 1000, 2)
    except Exception:
        status["ollama"] = "offline"
        
    status["audit_logs"] = get_audit_logs(limit=15)
    return status

async def retrain_stream(role: str):
    from backend.core.database import log_action
    from retrain import run_retraining
    log_action(role, "Triggered score-based retraining", "ChromaDB Upsert")
    
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    retrainer_logger = logging.getLogger("retrainer")
    retrainer_logger.addHandler(handler)
    
    try:
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        future = loop.run_in_executor(executor, run_retraining)
        
        last_pos = 0
        while not future.done():
            await asyncio.sleep(0.2)
            log_capture.seek(last_pos)
            new_logs = log_capture.read()
            if new_logs:
                last_pos = log_capture.tell()
                yield new_logs
                
        log_capture.seek(last_pos)
        final_logs = log_capture.read()
        if final_logs:
            yield final_logs
            
        result = future.result()
        if result:
            yield "\n[SUCCESS] Retraining complete."
            await manager.broadcast({"event": "refresh"})
        else:
            yield "\n[FAILED] Retraining pipeline failed."
    except Exception as e:
        yield f"\n[ERROR] Retraining encountered an issue: {e}"
    finally:
        retrainer_logger.removeHandler(handler)
        log_capture.close()

@app.get("/api/dashboard/retrain")
def trigger_retrain(role: str = "Developer"):
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can trigger retraining.")
    return StreamingResponse(retrain_stream(role), media_type="text/plain")

@app.get("/api/dashboard/memory")
def get_memory(search: str = None):
    from vector_store.chroma_client import ensure_collection
    try:
        collection = ensure_collection()
        results = collection.get()
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        
        memories = []
        for i in range(len(ids)):
            meta = metadatas[i]
            if search:
                text_pool = f"{meta.get('problematic_code', '')} {meta.get('review_comment', '')} {meta.get('fixed_code', '')}".lower()
                if search.lower() not in text_pool:
                    continue
                    
            memories.append({
                "id": ids[i],
                "problematic_code": meta.get("problematic_code", ""),
                "review_comment": meta.get("review_comment", ""),
                "fixed_code": meta.get("fixed_code", ""),
                "score": meta.get("score", 0.0),
                "source": meta.get("source", "baseline")
            })
        return memories
    except Exception as e:
        logger.error(f"Failed to fetch memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dashboard/memory/delete")
async def delete_memory(request: Request):
    from vector_store.chroma_client import ensure_collection
    from backend.core.database import log_action
    data = await request.json()
    memory_id = data.get("id")
    role = data.get("role", "Developer")
    
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can modify RAG memory.")
        
    try:
        collection = ensure_collection()
        collection.delete(ids=[memory_id])
        log_action(role, "Deleted vector memory entry", f"ID: {memory_id}")
        await manager.broadcast({"event": "refresh"})
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to delete vector memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dashboard/memory/boost")
async def boost_memory(request: Request):
    from vector_store.chroma_client import ensure_collection
    from backend.core.database import log_action
    data = await request.json()
    memory_id = data.get("id")
    boost_score = float(data.get("score", 5.0))
    role = data.get("role", "Developer")
    
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can boost vector memory.")
        
    try:
        collection = ensure_collection()
        existing = collection.get(ids=[memory_id])
        if not existing["ids"]:
            raise HTTPException(status_code=404, detail="Memory entry not found.")
            
        meta = existing["metadatas"][0]
        meta["score"] = boost_score
        
        embedding = existing["embeddings"][0] if (existing["embeddings"] and len(existing["embeddings"]) > 0) else None
        if not embedding:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embedding = model.encode(meta.get("problematic_code", "")).tolist()
            
        collection.upsert(ids=[memory_id], embeddings=[embedding], metadatas=[meta])
        log_action(role, "Boosted vector memory score", f"ID: {memory_id}, New Score: {boost_score:.2f}")
        await manager.broadcast({"event": "refresh"})
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to boost vector memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount static folder for dashboard hosting
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
