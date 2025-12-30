"""
MCP OAuth Authentication Middleware.

Validates OAuth access tokens for MCP server requests.
"""

from datetime import datetime, timezone
from typing import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.db import get_session
from app.core.logger import get_logger
from app.models.oauth import OAuthAccessToken
from app.models.user import User

logger = get_logger(__name__)


class MCPOAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate OAuth access tokens for MCP requests.
    
    Checks the Authorization header for a valid Bearer token and attaches 
    the authenticated user to the request state.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "unauthorized", "error_description": "Missing Authorization header"},
                headers={"WWW-Authenticate": 'Bearer realm="MCP API"'},
            )

        # Parse Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "invalid_request", "error_description": "Invalid Authorization header format"},
                headers={"WWW-Authenticate": 'Bearer realm="MCP API"'},
            )

        access_token = parts[1]

        # Validate token
        try:
            session = next(get_session())
            
            # Find token in database
            token_statement = select(OAuthAccessToken).where(
                OAuthAccessToken.access_token == access_token,
                OAuthAccessToken.is_revoked == False,
            )
            token_record = session.exec(token_statement).first()

            if not token_record:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "invalid_token", "error_description": "Access token not found or revoked"},
                    headers={"WWW-Authenticate": 'Bearer realm="MCP API", error="invalid_token"'},
                )

            # Check if token is expired
            if token_record.is_expired():
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "invalid_token", "error_description": "Access token has expired"},
                    headers={"WWW-Authenticate": 'Bearer realm="MCP API", error="invalid_token"'},
                )

            # Get user
            user_statement = select(User).where(User.id == token_record.user_id)
            user = session.exec(user_statement).first()

            if not user:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "invalid_token", "error_description": "User not found"},
                    headers={"WWW-Authenticate": 'Bearer realm="MCP API", error="invalid_token"'},
                )

            # Attach user and token info to request state
            request.state.user = user
            request.state.oauth_token = token_record
            request.state.oauth_scope = token_record.scope

            logger.info(f"Authenticated MCP request for user {user.id} ({user.username})")

        except Exception as e:
            logger.error(f"Error validating OAuth token: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "server_error", "error_description": "Internal server error"},
            )

        # Continue with the request
        response = await call_next(request)
        return response
