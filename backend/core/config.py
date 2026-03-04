from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # GitHub App configuration
    GITHUB_APP_IDENTIFIER: str = ""
    GITHUB_PRIVATE_KEY_PATH: str = "./github-private-key.pem"
    GITHUB_WEBHOOK_SECRET: str = "your_webhook_secret_here"
    
    # Allows falling back to a dummy setup for local testing if needed
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
