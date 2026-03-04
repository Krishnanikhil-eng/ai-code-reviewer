# Team-Aware AI Code Reviewer

## Phase 1: Foundation and GitHub Integration

This implements the FastAPI-based webhook listener configured to receive, verify, and parse GitHub Pull Request events as a GitHub App.

### Structure
* `backend/`: FastAPI Webhook listener and core logic.
* `ai_engine/`: (Phase 2) Will hold Vector searches, LLM configuration, and prompts.
* `vector_store/`: (Phase 2) ChromaDB / Qdrant configurations.
* `database/`: (Phase 2) Postgres/SQLite settings for review scoring.
* `docker/`: (Phase 2) Deployment templates.

### 1. Installing Dependencies

Make sure you have Python 3.10+ installed.

```bash
# In the root repository
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration Setup

Copy `.env.example` into `.env`:
```bash
cp backend/.env.example backend/.env
```
Fill out `.env` with actual data when preparing for production.

### 3. Running the FastAPI Server Locally

Run the FastApi application inside the backend context:
```bash
cd backend
python main.py
```
This runs the Uvicorn server locally on `http://localhost:8000`.

### 4. Configuring GitHub Webhooks

To test locally, your local server needs an internet-facing URL.
Recommend using `ngrok` or `localtunnel`:

```bash
ngrok http 8000
```
*Note down the forwarding URL provided by ngrok (e.g., `https://f123-your-ngrok.ngrok-free.app`).*

#### In your GitHub Repository:
1. Go to your GitHub Repo -> **Settings** -> **Webhooks**.
2. Click **Add webhook**.
3. **Payload URL:** Set `https://<YOUR_NGROK_URL>/webhook`
4. **Content type:** Select `application/json`
5. **Secret:** Set to the value of `GITHUB_WEBHOOK_SECRET` in your `.env` file.
6. **Which events would you like to trigger this webhook?:** Select "Let me select individual events" and check **Pull requests**. Check off "Pushes".
7. Make sure it's active.

> For a full secure setup, create a GitHub App in your developer settings, generate a private key (`.pem`), note the App ID, and update `.env` accordingly. Set webhooks via the App configuration instead.
