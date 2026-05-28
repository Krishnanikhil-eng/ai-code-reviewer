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
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'

settings = Settings()
