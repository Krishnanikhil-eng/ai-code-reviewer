# 🚀 Running the Team-Aware AI Code Reviewer

This guide provides step-by-step instructions to get the AI Code Reviewer up and running on your local machine or in a containerized environment.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
* **Python 3.10+** (if running locally)
* **Docker & Docker Compose** (if running via Docker)
* **ngrok** (for local webhook testing)
* **Ollama** (if running locally without Docker)

---

## 🛠️ Configuration

1. **Environment Variables**:
   Copy the example environment file. The location depends on how you run the app:
   
   *   **For Docker**: Place `.env` in the **root** directory.
   *   **For Local**: Place `.env` in the **root** OR the **backend** directory (standard is root if running from root).

   ```bash
   # Create from root
   cp backend/.env.example .env
   ```

   Edit `.env` and fill in:
   - `GITHUB_APP_IDENTIFIER`: Your GitHub App ID.
   - `GITHUB_PRIVATE_KEY_PATH`: Path to your `.pem` file.
   - `GITHUB_WEBHOOK_SECRET`: The secret you set in GitHub webhooks.

---

## 🐳 Method 1: Running with Docker (Recommended)

This is the easiest way to run the entire stack, including the AI engine (Ollama).

1. **Start the containers**:
   ```bash
   docker-compose up -d
   ```

2. **Pull the AI Model**:
   If this is your first time, you need to pull the Llama3 model inside the Ollama container:
   ```bash
   docker exec -it ai-reviewer-ollama ollama pull llama3
   ```

3. **Verify**:
   The backend will be available at `http://localhost:8000`.

---

## 🐍 Method 2: Running Locally (Manual)

If you prefer to run the components manually on your host machine.

### 1. Setup Virtual Environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Initialize Vector Database
Seed the ChromaDB with training examples:
```bash
python embedder.py
```

### 3. Start Ollama
Ensure Ollama is running on your machine and you have the model:
```bash
ollama serve
ollama pull llama3
```

### 4. Run FastAPI Backend
```bash
cd backend
python main.py
```

---

## 🔗 Connecting to GitHub

To receive webhooks from GitHub to your local machine, use **ngrok**.

1. **Expose port 8000**:
   ```bash
   ngrok http 8000
   ```

2. **Update GitHub Webhook**:
   - Copy the `https://...` URL from ngrok.
   - Go to your GitHub App/Repo settings -> **Webhooks**.
   - Set **Payload URL** to `https://<YOUR_NGROK_URL>/webhook`.
   - Set **Content type** to `application/json`.

---

## 🔍 Troubleshooting

- **Signature Verification Failed**: If testing locally, set `DEBUG=True` in your `.env` to bypass signature checks.
- **Ollama Connection Error**: Ensure `OLLAMA_API_URL` in `.env` matches your setup (use `http://ollama:11434` for Docker, `http://localhost:11434` for local).
- **Missing Dependencies**: Run `pip install -r requirements.txt` again.
