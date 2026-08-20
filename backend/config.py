"""Configuration settings for the application."""
import os
from typing import List


class Settings:
    """Application settings."""
    
    # API settings
    FREELANCER_API_BASE_URL: str = os.getenv(
        "FREELANCER_API_BASE_URL",
        "https://www.freelancer.com"
    )
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 50
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Application
    APP_NAME: str = "Freelancer Job Analyzer"
    APP_VERSION: str = "1.0.0"


settings = Settings()
