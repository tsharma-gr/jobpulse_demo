from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "JobPulse AI"
    LOG_LEVEL: str = "INFO"
    
    # Concurrency & Browsers
    MAX_WORKERS: int = 4
    MAX_BROWSERS: int = 1
    MAX_CONTEXTS: int = 3
    
    # Search Limits
    SEARCH_TIMEOUT: int = 60
    RESULT_LIMIT: int = 100
    QUEUE_SIZE: int = 1000
    
    # Caching
    CACHE_EXPIRY_HOURS: int = 24
    
    # AI Config
    AI_MODEL: str = "deepseek-chat"
    AI_TIMEOUT: int = 30
    DEEPSEEK_API_KEY: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite:///./jobpulse_cache.db"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
