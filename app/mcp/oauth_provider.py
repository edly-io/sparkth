"""
MCP OAuth Provider implementation for Sparkth - Fixed for MCP Inspector
"""

from datetime import datetime, timezone
from typing import Optional, override

from fastmcp.server.auth.auth import ClientRegistrationOptions, OAuthProvider
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from sqlmodel import select, Session
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse, HTMLResponse

from app.core import oauth as oauth_utils
from app.core.config import get_settings
from app.core.db import get_session
from app.core.logger import get_logger
from app.models.oauth import OAuthAccessToken, OAuthAuthorizationCode, OAuthClient
from app.models.user import User

logger = get_logger(__name__)
settings = get_settings()


class SparkthOAuthProvider(OAuthProvider):
    """
    OAuth Provider for Sparkth MCP server.

    Implements the FastMCP OAuthProvider interface using our existing
    database models for OAuth clients, tokens, and authorization codes.
    """

    def __init__(self) -> None:
        """Initialize the OAuth provider with dynamic client registration enabled."""
        from pydantic import HttpUrl

        base_url = HttpUrl("http://localhost:8009")

        super().__init__(
            base_url=str(base_url),
            service_documentation_url=f"{base_url}/docs",
            client_registration_options=ClientRegistrationOptions(
                enabled=True,  # Enable dynamic client registration
                valid_scopes=["mcp", "read", "write"],
                default_scopes=["mcp"],
            ),
            required_scopes=["mcp"],
        )
        self.base_url = base_url

    def _get_session(self) -> Session:
        """Get a database session."""
        return next(get_session())

    @override
    def get_oauth_metadata(self) -> dict:
        """
        Override to customize OAuth 2.1 Authorization Server Metadata.

        This controls what /.well-known/oauth-authorization-server returns.

        Reference: https://datatracker.ietf.org/doc/html/rfc8414
        """
        metadata = {
            # REQUIRED: The authorization server's issuer identifier
            "issuer": self.base_url,

            # REQUIRED: URL of the authorization endpoint
            "authorization_endpoint": f"{self.base_url}/oauth/authorize",

            # REQUIRED: URL of the token endpoint
            "token_endpoint": f"{self.base_url}/oauth/token",

            # RECOMMENDED: URL of the dynamic client registration endpoint
            "registration_endpoint": f"{self.base_url}/oauth/register",

            # OPTIONAL: URL of the token revocation endpoint
            "revocation_endpoint": f"{self.base_url}/oauth/revoke",

            # OPTIONAL: URL of the token introspection endpoint
            # "introspection_endpoint": f"{self.base_url}/oauth/introspect",

            # OPTIONAL: JSON array of grant types supported
            "grant_types_supported": [
                "authorization_code",
                "refresh_token"
            ],

            # OPTIONAL: JSON array of response types supported
            "response_types_supported": [
                "code"
            ],

            # OPTIONAL: JSON array of response modes supported
            "response_modes_supported": [
                "query",
                "fragment"
            ],

            # OPTIONAL: JSON array of the OAuth 2.0 scopes supported
            "scopes_supported": [
                "mcp",
                "read",
                "write"
            ],

            # OPTIONAL: JSON array of client authentication methods supported by token endpoint
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic",
                "none"  # For public clients (MCP Inspector)
            ],

            # OPTIONAL: JSON array of PKCE code challenge methods supported
            "code_challenge_methods_supported": [
                "S256",
                "plain"
            ],

            # OPTIONAL: Service documentation URL
            "service_documentation": f"{self.base_url}/docs",

            # OPTIONAL: Boolean indicating support for the "request" parameter
            "request_parameter_supported": False,

            # OPTIONAL: Boolean indicating support for the "request_uri" parameter
            "request_uri_parameter_supported": False,

            # OPTIONAL: Boolean indicating if the authorization server requires request objects
            "require_request_uri_registration": False,

            # OPTIONAL: URL for OP policy
            # "op_policy_uri": f"{self.base_url}/policy",

            # OPTIONAL: URL for OP terms of service
            # "op_tos_uri": f"{self.base_url}/terms",
        }

        logger.info("OAuth metadata requested")
        logger.debug(f"OAuth metadata: {metadata}")

        return metadata

    @override
    async def authorize(
        self,
        params: AuthorizationParams,
        client: OAuthClientInformationFull,
    ) -> str:
        """
        Handle authorization request.

        For MCP Inspector testing, we'll auto-approve with a test user.
        In production, this should show a real consent screen.
        """
        try:
            session = self._get_session()

            # For MCP Inspector testing: auto-approve with test user
            # TODO: Replace with real authentication in production
            test_user_id = await self._get_or_create_test_user(session)

            # Generate authorization code
            code = oauth_utils.generate_authorization_code()
            expires_at = oauth_utils.get_authorization_code_expiry()

            # Store authorization code
            auth_code = OAuthAuthorizationCode(
                code=code,
                client_id=client.client_id,
                user_id=test_user_id,
                redirect_uri=str(params.redirect_uri),
                scope=" ".join(params.scope) if params.scope else "mcp",
                expires_at=expires_at,
                code_challenge=params.code_challenge,
                code_challenge_method=params.code_challenge_method,
            )

            session.add(auth_code)
            session.commit()

            logger.info(f"Created authorization code for client {client.client_id}")

            # Construct redirect URI
            redirect_uri = construct_redirect_uri(
                redirect_uri=str(params.redirect_uri),
                code=code,
                state=params.state,
            )

            return redirect_uri

        except Exception as e:
            logger.error(f"Error in authorize: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Authorization failed")

    async def _get_or_create_test_user(self, session: Session) -> int:
        """
        Get or create a test user for MCP Inspector testing.

        TODO: Remove this in production and use real authentication.
        """
        # Try to find test user
        test_user = session.exec(
            select(User).where(User.email == "test@mcp-inspector.local")
        ).first()

        if test_user:
            return test_user.id

        # Create test user
        test_user = User(
            username="mcp_inspector_test",
            email="test@mcp-inspector.local",
            # Add other required fields based on your User model
        )
        session.add(test_user)
        session.commit()
        session.refresh(test_user)

        logger.info(f"Created test user for MCP Inspector: {test_user.id}")
        return test_user.id

    @override
    async def load_authorization_code(self, code: str) -> Optional[AuthorizationCode]:
        """Load authorization code from database."""
        try:
            session = self._get_session()

            auth_code = session.exec(
                select(OAuthAuthorizationCode).where(
                    OAuthAuthorizationCode.code == code,
                    OAuthAuthorizationCode.is_used == False,
                )
            ).first()

            if not auth_code:
                logger.warning(f"Authorization code not found: {code}")
                return None

            if auth_code.is_expired():
                logger.warning(f"Authorization code expired: {code}")
                return None

            return AuthorizationCode(
                code=auth_code.code,
                client_id=auth_code.client_id,
                redirect_uri=auth_code.redirect_uri,
                scope=auth_code.scope.split() if auth_code.scope else [],
                code_challenge=auth_code.code_challenge,
                code_challenge_method=auth_code.code_challenge_method,
            )

        except Exception as e:
            logger.error(f"Error loading authorization code: {e}", exc_info=True)
            return None

    @override
    async def exchange_authorization_code(
        self,
        code: str,
        client: OAuthClientInformationFull,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
    ) -> OAuthToken:
        """Exchange authorization code for tokens."""
        try:
            session = self._get_session()

            # Load and validate authorization code
            auth_code_record = session.exec(
                select(OAuthAuthorizationCode).where(
                    OAuthAuthorizationCode.code == code,
                    OAuthAuthorizationCode.client_id == client.client_id,
                    OAuthAuthorizationCode.is_used == False,
                )
            ).first()

            if not auth_code_record:
                logger.error(f"Invalid authorization code: {code}")
                raise HTTPException(status_code=400, detail="Invalid authorization code")

            if auth_code_record.is_expired():
                logger.error(f"Authorization code expired: {code}")
                raise HTTPException(status_code=400, detail="Authorization code expired")

            if auth_code_record.redirect_uri != redirect_uri:
                logger.error(
                    f"Redirect URI mismatch. Expected: {auth_code_record.redirect_uri}, "
                    f"Got: {redirect_uri}"
                )
                raise HTTPException(status_code=400, detail="Redirect URI mismatch")

            # Validate PKCE if used
            if auth_code_record.code_challenge:
                if not code_verifier:
                    logger.error("Code verifier required but not provided")
                    raise HTTPException(status_code=400, detail="Code verifier required")

                if not self._verify_pkce(
                    code_verifier,
                    auth_code_record.code_challenge,
                    auth_code_record.code_challenge_method or "S256"
                ):
                    logger.error("Invalid code verifier")
                    raise HTTPException(status_code=400, detail="Invalid code verifier")

            # Mark code as used
            auth_code_record.is_used = True
            session.add(auth_code_record)

            # Generate tokens
            access_token = oauth_utils.generate_access_token()
            refresh_token = oauth_utils.generate_refresh_token()
            access_expires_at = oauth_utils.get_access_token_expiry()
            refresh_expires_at = oauth_utils.get_refresh_token_expiry()

            # Store tokens
            token_record = OAuthAccessToken(
                access_token=access_token,
                refresh_token=refresh_token,
                client_id=client.client_id,
                user_id=auth_code_record.user_id,
                scope=auth_code_record.scope,
                expires_at=access_expires_at,
                refresh_token_expires_at=refresh_expires_at,
            )

            session.add(token_record)
            session.commit()

            expires_in = int((access_expires_at - datetime.now(timezone.utc)).total_seconds())

            logger.info(
                f"Successfully exchanged authorization code for tokens. "
                f"User: {auth_code_record.user_id}, Client: {client.client_id}"
            )

            return OAuthToken(
                access_token=access_token,
                token_type="Bearer",
                expires_in=expires_in,
                refresh_token=refresh_token,
                scope=auth_code_record.scope.split() if auth_code_record.scope else [],
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error exchanging authorization code: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Token exchange failed")

    # ... (keep all other methods the same: load_refresh_token, exchange_refresh_token,
    #      load_access_token, revoke_token, verify_token, _verify_pkce)

    @override
    async def load_refresh_token(self, token: str) -> Optional[RefreshToken]:
        """Load refresh token from database."""
        try:
            session = self._get_session()

            token_record = session.exec(
                select(OAuthAccessToken).where(
                    OAuthAccessToken.refresh_token == token,
                    OAuthAccessToken.is_revoked == False,
                )
            ).first()

            if not token_record or token_record.is_refresh_token_expired():
                return None

            return RefreshToken(
                token=token,
                client_id=token_record.client_id,
                scope=token_record.scope.split() if token_record.scope else [],
            )

        except Exception as e:
            logger.error(f"Error loading refresh token: {e}")
            return None

    @override
    async def exchange_refresh_token(
        self,
        refresh_token: str,
        client: OAuthClientInformationFull,
        scope: Optional[list[str]] = None,
    ) -> OAuthToken:
        """Exchange refresh token for new access token."""
        try:
            session = self._get_session()

            old_token = session.exec(
                select(OAuthAccessToken).where(
                    OAuthAccessToken.refresh_token == refresh_token,
                    OAuthAccessToken.client_id == client.client_id,
                    OAuthAccessToken.is_revoked == False,
                )
            ).first()

            if not old_token:
                raise HTTPException(status_code=400, detail="Invalid refresh token")

            if old_token.is_refresh_token_expired():
                raise HTTPException(status_code=400, detail="Refresh token expired")

            if scope:
                old_scopes = set(old_token.scope.split()) if old_token.scope else set()
                if not set(scope).issubset(old_scopes):
                    raise HTTPException(status_code=400, detail="Requested scope exceeds original")

            final_scope = " ".join(scope) if scope else old_token.scope

            old_token.is_revoked = True
            session.add(old_token)

            new_access_token = oauth_utils.generate_access_token()
            new_refresh_token = oauth_utils.generate_refresh_token()
            access_expires_at = oauth_utils.get_access_token_expiry()
            refresh_expires_at = oauth_utils.get_refresh_token_expiry()

            new_token = OAuthAccessToken(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                client_id=client.client_id,
                user_id=old_token.user_id,
                scope=final_scope,
                expires_at=access_expires_at,
                refresh_token_expires_at=refresh_expires_at,
            )

            session.add(new_token)
            session.commit()

            expires_in = int((access_expires_at - datetime.now(timezone.utc)).total_seconds())

            logger.info(f"Refreshed tokens for user {old_token.user_id}")

            return OAuthToken(
                access_token=new_access_token,
                token_type="Bearer",
                expires_in=expires_in,
                refresh_token=new_refresh_token,
                scope=final_scope.split() if final_scope else [],
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Token refresh failed")

    @override
    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        """Load and validate access token."""
        try:
            session = self._get_session()

            token_record = session.exec(
                select(OAuthAccessToken).where(
                    OAuthAccessToken.access_token == token,
                    OAuthAccessToken.is_revoked == False,
                )
            ).first()

            if not token_record or token_record.is_expired():
                return None

            user = session.exec(
                select(User).where(User.id == token_record.user_id)
            ).first()

            return AccessToken(
                token=token,
                client_id=token_record.client_id,
                scopes=token_record.scope.split() if token_record.scope else [],
            )

        except Exception as e:
            logger.error(f"Error loading access token: {e}")
            return None

    @override
    async def revoke_token(
        self,
        token: str,
        client: OAuthClientInformationFull,
        token_type_hint: Optional[str] = None,
    ) -> bool:
        """Revoke access or refresh token."""
        try:
            session = self._get_session()

            token_record = session.exec(
                select(OAuthAccessToken).where(
                    ((OAuthAccessToken.access_token == token) |
                     (OAuthAccessToken.refresh_token == token)),
                    OAuthAccessToken.client_id == client.client_id,
                )
            ).first()

            if token_record:
                token_record.is_revoked = True
                session.add(token_record)
                session.commit()
                logger.info(f"Revoked token for client {client.client_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error revoking token: {e}", exc_info=True)
            return False

    @override
    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Verify bearer token for incoming MCP requests."""
        return await self.load_access_token(token)

    def _verify_pkce(
        self,
        code_verifier: str,
        code_challenge: str,
        method: str
    ) -> bool:
        """Verify PKCE code challenge."""
        import hashlib
        import base64

        if method == "plain":
            return code_verifier == code_challenge
        elif method == "S256":
            digest = hashlib.sha256(code_verifier.encode()).digest()
            computed_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
            return computed_challenge == code_challenge

        return False
