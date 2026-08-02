from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str = ""
    model: str = "llama-3.3-70b-versatile"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    collection: str = "governance_kb"
    database_url: str = ""
    min_confidence: float = 0.6
    retention_days: int = 365

    class Config:
        env_file = ".env"


settings = Settings()