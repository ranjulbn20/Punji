from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
import json


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    database_url: str
    redis_url: str

    anthropic_api_key: str
    google_ai_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    news_api_key: str

    jwt_secret: str
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30
    google_client_id: str
    google_client_secret: str

    gcp_project_id: str = "punji-prod"
    gcp_region: str = "asia-south1"

    environment: str = "development"
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000"]

    enable_news_monitoring: bool = True
    enable_goals: bool = True
    enable_broker_connect: bool = False

    rbi_repo_rate: float = 6.5  # Updated manually when RBI changes rate

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v



settings = Settings()
