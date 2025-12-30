"""
OAuth 2.0 endpoints for client registration and authorization flow.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.api.v1.auth import get_current_user
from app.core import oauth as oauth_utils
from app.core.db import get_session
from app.models.oauth import OAuthAccessToken, OAuthAuthorizationCode, OAuthClient
from app.models.user import User
from app.schemas.oauth import (
    OAuthClientCreate,
    OAuthClientListResponse,
    OAuthClientResponse,
    OAuthRevokeRequest,
    OAuthTokenRequest,
    OAuthTokenResponse,
)

router = APIRouter()


@router.post("/clients", response_model=OAuthClientResponse, status_code=status.HTTP_201_CREATED)
def create_oauth_client(
    client_data: OAuthClientCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """
    Register a new OAuth client application.
    
    Returns the client_id and client_secret. Save the client_secret securely as it won't be shown again.
    """
    client_id = oauth_utils.generate_client_id()
    client_secret = oauth_utils.generate_client_secret()
    client_secret_hash = oauth_utils.hash_client_secret(client_secret)

    oauth_client = OAuthClient(
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        client_name=client_data.client_name,
        redirect_uris=client_data.redirect_uris,
        user_id=current_user.id,
    )

    session.add(oauth_client)
    session.commit()
    session.refresh(oauth_client)

    return {
        "id": oauth_client.id,
        "client_id": oauth_client.client_id,
        "client_name": oauth_client.client_name,
        "redirect_uris": oauth_client.redirect_uris,
        "user_id": oauth_client.user_id,
        "is_active": oauth_client.is_active,
        "created_at": oauth_client.created_at,
        "client_secret": client_secret,  # Only returned on creation
    }


@router.get("/clients", response_model=list[OAuthClientListResponse])
def list_oauth_clients(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[OAuthClient]:
    """List all OAuth clients for the current user."""
    statement = select(OAuthClient).where(OAuthClient.user_id == current_user.id)
    clients = session.exec(statement).all()
    return list(clients)


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_oauth_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete an OAuth client (deactivate)."""
    statement = select(OAuthClient).where(
        OAuthClient.client_id == client_id, OAuthClient.user_id == current_user.id
    )
    client = session.exec(statement).first()

    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OAuth client not found")

    client.is_active = False
    session.add(client)
    session.commit()


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(default=""),
    state: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """
    OAuth authorization endpoint.
    
    User is redirected here from the OAuth client. After authentication, 
    an authorization code is generated and the user is redirected back to the client.
    """
    # Validate response_type
    if response_type != "code":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid response_type. Must be 'code'")

    # Validate client
    client_statement = select(OAuthClient).where(OAuthClient.client_id == client_id, OAuthClient.is_active == True)
    client = session.exec(client_statement).first()

    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid client_id")

    # Validate redirect_uri
    if redirect_uri not in client.redirect_uris:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid redirect_uri")

    # Generate authorization code
    code = oauth_utils.generate_authorization_code()
    expires_at = oauth_utils.get_authorization_code_expiry()

    auth_code = OAuthAuthorizationCode(
        code=code,
        client_id=client_id,
        user_id=current_user.id,
        redirect_uri=redirect_uri,
        scope=scope,
        expires_at=expires_at,
    )

    session.add(auth_code)
    session.commit()

    # Build redirect URL with code and state
    redirect_url = f"{redirect_uri}?code={code}"
    if state:
        redirect_url += f"&state={state}"

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.post("/token", response_model=OAuthTokenResponse)
def token(
    token_request: OAuthTokenRequest,
    session: Session = Depends(get_session),
) -> dict:
    """
    OAuth token endpoint.
    
    Exchange authorization code for access token, or refresh an existing token.
    """
    # Validate client credentials
    client_statement = select(OAuthClient).where(
        OAuthClient.client_id == token_request.client_id, OAuthClient.is_active == True
    )
    client = session.exec(client_statement).first()

    if not client or not oauth_utils.verify_client_secret(token_request.client_secret, client.client_secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_request.grant_type == "authorization_code":
        return _handle_authorization_code_grant(token_request, client, session)
    elif token_request.grant_type == "refresh_token":
        return _handle_refresh_token_grant(token_request, client, session)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported grant_type")


def _handle_authorization_code_grant(
    token_request: OAuthTokenRequest, client: OAuthClient, session: Session
) -> dict:
    """Handle authorization_code grant type."""
    if not token_request.code or not token_request.redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code or redirect_uri for authorization_code grant"
        )

    # Validate authorization code
    code_statement = select(OAuthAuthorizationCode).where(
        OAuthAuthorizationCode.code == token_request.code,
        OAuthAuthorizationCode.client_id == client.client_id,
        OAuthAuthorizationCode.is_used == False,
    )
    auth_code = session.exec(code_statement).first()

    if not auth_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired authorization code")

    if auth_code.is_expired():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code has expired")

    if auth_code.redirect_uri != token_request.redirect_uri:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Redirect URI mismatch")

    # Mark code as used
    auth_code.is_used = True
    session.add(auth_code)

    # Generate access token and refresh token
    access_token = oauth_utils.generate_access_token()
    refresh_token = oauth_utils.generate_refresh_token()
    access_token_expires_at = oauth_utils.get_access_token_expiry()
    refresh_token_expires_at = oauth_utils.get_refresh_token_expiry()

    token_record = OAuthAccessToken(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client.client_id,
        user_id=auth_code.user_id,
        scope=auth_code.scope,
        expires_at=access_token_expires_at,
        refresh_token_expires_at=refresh_token_expires_at,
    )

    session.add(token_record)
    session.commit()

    expires_in = int((access_token_expires_at - datetime.now(timezone.utc)).total_seconds())

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "refresh_token": refresh_token,
        "scope": auth_code.scope,
    }


def _handle_refresh_token_grant(token_request: OAuthTokenRequest, client: OAuthClient, session: Session) -> dict:
    """Handle refresh_token grant type."""
    if not token_request.refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh_token")

    # Validate refresh token
    token_statement = select(OAuthAccessToken).where(
        OAuthAccessToken.refresh_token == token_request.refresh_token,
        OAuthAccessToken.client_id == client.client_id,
        OAuthAccessToken.is_revoked == False,
    )
    old_token = session.exec(token_statement).first()

    if not old_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token")

    if old_token.is_refresh_token_expired():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token has expired")

    # Revoke old token
    old_token.is_revoked = True
    session.add(old_token)

    # Generate new access token and refresh token
    access_token = oauth_utils.generate_access_token()
    refresh_token = oauth_utils.generate_refresh_token()
    access_token_expires_at = oauth_utils.get_access_token_expiry()
    refresh_token_expires_at = oauth_utils.get_refresh_token_expiry()

    new_token = OAuthAccessToken(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client.client_id,
        user_id=old_token.user_id,
        scope=old_token.scope,
        expires_at=access_token_expires_at,
        refresh_token_expires_at=refresh_token_expires_at,
    )

    session.add(new_token)
    session.commit()

    expires_in = int((access_token_expires_at - datetime.now(timezone.utc)).total_seconds())

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "refresh_token": refresh_token,
        "scope": old_token.scope,
    }


@router.post("/revoke", status_code=status.HTTP_200_OK)
def revoke_token(
    revoke_request: OAuthRevokeRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """
    Revoke an access token or refresh token.
    """
    # Validate client credentials
    client_statement = select(OAuthClient).where(
        OAuthClient.client_id == revoke_request.client_id, OAuthClient.is_active == True
    )
    client = session.exec(client_statement).first()

    if not client or not oauth_utils.verify_client_secret(revoke_request.client_secret, client.client_secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Find and revoke token
    if revoke_request.token_type_hint == "refresh_token":
        token_statement = select(OAuthAccessToken).where(
            OAuthAccessToken.refresh_token == revoke_request.token, OAuthAccessToken.client_id == client.client_id
        )
    else:
        # Default to access_token
        token_statement = select(OAuthAccessToken).where(
            OAuthAccessToken.access_token == revoke_request.token, OAuthAccessToken.client_id == client.client_id
        )

    token_record = session.exec(token_statement).first()

    if token_record:
        token_record.is_revoked = True
        session.add(token_record)
        session.commit()

    # Return success even if token not found (per OAuth 2.0 spec)
    return {"message": "Token revoked successfully"}
