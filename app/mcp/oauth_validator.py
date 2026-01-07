"""
OAuth token validation for FastMCP.

Provides token validation callback for FastMCP's built-in OAuth support.
"""

from sqlmodel import select

from app.core.db import get_session
from app.core.logger import get_logger
from app.models.oauth import OAuthAccessToken
from app.models.user import User

logger = get_logger(__name__)


async def validate_oauth_token(token: str) -> dict | None:
    """
    Validate OAuth token and return user context.
    
    Called by FastMCP when a request includes an Authorization header.
    This function validates the token against your database and returns
    user information if valid.
    
    Args:
        token: The OAuth access token from the Authorization header
        
    Returns:
        dict with user info if valid, None if invalid/expired
        
    Example return value:
        {
            "user_id": 1,
            "username": "john_doe",
            "email": "john@example.com",
            "scope": "read write",
        }
    """
    try:
        session = next(get_session())
        
        # Find token in database
        token_statement = select(OAuthAccessToken).where(
            OAuthAccessToken.access_token == token,
            OAuthAccessToken.is_revoked == False,
        )
        token_record = session.exec(token_statement).first()
        
        if not token_record:
            logger.debug("Token not found or revoked")
            return None
        
        # Check if token is expired
        if token_record.is_expired():
            logger.debug("Token has expired")
            return None
        
        # Get user
        user_statement = select(User).where(User.id == token_record.user_id)
        user = session.exec(user_statement).first()
        
        if not user:
            logger.warning(f"User {token_record.user_id} not found for valid token")
            return None
        
        logger.info(f"Successfully validated token for user {user.username} (ID: {user.id})")
        
        return {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "scope": token_record.scope or "",
        }
        
    except Exception as e:
        logger.error(f"Error validating OAuth token: {e}", exc_info=True)
        return None
