"""
Security utilities: authentication, authorization, and validation.
"""
from fastapi import HTTPException, status, Depends, Header
from typing import Optional
import logging
from config import settings

logger = logging.getLogger(__name__)

class APIKeyAuth:
    """API Key authentication dependency."""
    
    def __init__(self, api_key_header: Optional[str] = Header(None)):
        self.api_key = api_key_header
    
    def validate(self) -> bool:
        """Validate API key."""
        if not self.api_key:
            logger.warning("Request without API key")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not self._is_valid_key(self.api_key):
            logger.warning("Invalid API key attempt")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Key",
            )
        
        return True
    
    def _is_valid_key(self, key: str) -> bool:
        """Check if the provided key matches the configured API key."""
        return key == settings.api_key

def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Dependency to verify API key in request headers."""
    auth = APIKeyAuth(x_api_key)
    auth.validate()
    return x_api_key

def sanitize_string(value: str, max_length: int = 500) -> str:
    """Sanitize string input to prevent injection attacks."""
    if not isinstance(value, str):
        raise ValueError("Expected string value")
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Truncate to max length
    if len(value) > max_length:
        logger.warning(f"String truncated from {len(value)} to {max_length} characters")
        value = value[:max_length]
    
    return value.strip()

def validate_protocolo(protocolo: str) -> str:
    """Validate protocolo parameter format."""
    protocolo = sanitize_string(protocolo, max_length=100)
    
    # Should contain only alphanumeric, hyphens, and underscores
    if not all(c.isalnum() or c in ['-', '_', '/'] for c in protocolo):
        raise ValueError("Protocolo contains invalid characters")
    
    return protocolo

def validate_scope(scope: str) -> str:
    """Validate scope parameter (table name)."""
    scope = sanitize_string(scope, max_length=200)
    
    # Allow only alphanumeric, dots, and underscores (for schema.table format)
    if not all(c.isalnum() or c in ['.', '_'] for c in scope):
        raise ValueError("Scope contains invalid characters")
    
    return scope

def validate_filter_list(filter_list: Optional[list]) -> Optional[list]:
    """Validate and sanitize filter list."""
    if filter_list is None:
        return None
    
    if not isinstance(filter_list, list):
        raise ValueError("Filter must be a list")
    
    if len(filter_list) > 100:
        raise ValueError("Filter list too long (max 100 items)")
    
    return [sanitize_string(item, max_length=200) for item in filter_list]

class RequestLogger:
    """Log API requests for security auditing."""
    
    @staticmethod
    def log_request(endpoint: str, api_key_partial: str, params: dict = None):
        """Log API request with partial API key for audit trail."""
        key_partial = api_key_partial[:10] + "..." if api_key_partial else "None"
        logger.info(f"API Request - Endpoint: {endpoint}, APIKey: {key_partial}, Params: {params or {}}")
    
    @staticmethod
    def log_error(endpoint: str, error: str, severity: str = "ERROR"):
        """Log security-related errors."""
        logger.log(
            level=logging.ERROR if severity == "ERROR" else logging.WARNING,
            msg=f"Security Event - Endpoint: {endpoint}, Error: {error}"
        )
