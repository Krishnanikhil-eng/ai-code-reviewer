from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # GitHub App configuration
    GITHUB_APP_IDENTIFIER: str = ""
    GITHUB_PRIVATE_KEY_PATH: str = "./github-private-key.pem"
    GITHUB_WEBHOOK_SECRET: str = "your_webhook_secret_here"
    
    # Allows falling back to a dummy setup for local testing if needed
    DEBUG: bool = True
    
    # AI Engine settings
    OLLAMA_API_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "llama3"

    # Configurable branding constants
    DASHBOARD_PLATFORM_NAME: str = "Antigravity AI"
    DASHBOARD_PLATFORM_SUBTITLE: str = "Review Analytics Platform"
    DASHBOARD_LOGO_ICON_CLASS: str = "fa-solid fa-brain"
    DASHBOARD_LOGIN_LOGO_ICON_CLASS: str = "fa-solid fa-robot"
    DASHBOARD_BROWSER_TITLE: str = "Enterprise AI Reviewer Dashboard"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'

settings = Settings()
