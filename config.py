"""
Configuration loader for environment variables with validation.
"""
import os
from typing import List
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Application settings loaded from environment variables."""
    
    # PostgreSQL Configuration
    postgres_host: str = os.getenv("POSTGRES_HOST", "10.150.59.246")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_database: str = os.getenv("POSTGRES_DATABASE", "contractual-rules")
    postgres_user: str = os.getenv("POSTGRES_USER", "")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "")
    
    # SQL Server Configuration
    sqlserver_driver: str = os.getenv("SQLSERVER_DRIVER", "{ODBC Driver 17 for SQL Server}")
    sqlserver_server: str = os.getenv("SQLSERVER_SERVER", "")
    sqlserver_database: str = os.getenv("SQLSERVER_DATABASE", "qualidade")
    sqlserver_uid: str = os.getenv("SQLSERVER_UID", "")
    sqlserver_password: str = os.getenv("SQLSERVER_PASSWORD", "")
    
    # Security
    api_key: str = os.getenv("API_KEY", "")
    allowed_origins: List[str] = os.getenv(
        "ALLOWED_ORIGINS", 
        "http://localhost:8000"
    ).split(",")
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __init__(self):
        """Validate required settings on initialization."""
        self._validate()
    
    def _validate(self):
        """Validate that required environment variables are set."""
        required_fields = {
            "POSTGRES_USER": self.postgres_user,
            "POSTGRES_PASSWORD": self.postgres_password,
            "SQLSERVER_UID": self.sqlserver_uid,
            "SQLSERVER_PASSWORD": self.sqlserver_password,
            "API_KEY": self.api_key,
        }
        
        missing = [k for k, v in required_fields.items() if not v]
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please copy .env.example to .env and fill in the values."
            )
        
        if len(self.api_key) < 20:
            raise ValueError("API_KEY must be at least 20 characters long for security.")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Create global settings instance
try:
    settings = get_settings()
except ValueError as e:
    import logging
    logging.error(f"Configuration error: {e}")
    raise
