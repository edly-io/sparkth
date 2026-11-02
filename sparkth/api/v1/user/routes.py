"""The authenticated caller's own profile: ``GET`` and ``PATCH /user/me``, and
``POST /user/me/password``.

Every endpoint serves the caller and nobody else. None takes a user id, so a
request can only ever read or write its own row.

``PATCH`` is a partial update of the name and the preferred language: a field left
out of the body keeps its stored value. For ``language`` an explicit ``null`` is
meaningful, clearing a previous choice so the platform default applies again.
Username and email cannot be changed here.

``POST /me/password`` changes the password after checking the current one; the
account service records it as ``auth.password_changed``.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.user.schemas import PasswordChange, UserUpdate
from sparkth.core.models.user import User
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.i18n import _
from sparkth.schemas import User as UserSchema
from sparkth.services.account import change_password

router = APIRouter()


async def _load_user_for_update(current_user: User, session: AsyncSession) -> User:
    """Load the current user from ``session`` so changes to it are saved on commit."""
    user = await session.get(User, current_user.id)
    if user is None:
        # get_current_user already rejects missing users, so this should not happen.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("User not found"))
    return user


@router.get("/me", response_model=UserSchema)
async def get_user(current_user: User = Depends(get_current_user)) -> UserSchema:
    """Fetch the current authenticated user from the JWT token.

    ``language`` is the raw stored preference — ``None`` when the user never chose one.
    """
    return UserSchema.model_validate(current_user)


@router.patch("/me", response_model=UserSchema)
async def update_user(
    update: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserSchema:
    """Update the current user's name and preferred language.

    Only the fields sent in the body are written. ``UserUpdate`` has already trimmed
    the name and checked the language against the supported-language allowlist, so
    bad input is a 422 before reaching here. An explicit ``null`` language clears the
    preference.
    """
    user = await _load_user_for_update(current_user, session)

    for field in update.model_fields_set:
        setattr(user, field, getattr(update, field))
    # updated_at has a default_factory but no onupdate, so the bump is manual.
    user.update_timestamp()
    await session.commit()

    return UserSchema.model_validate(user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_user_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Change the current user's password, given their current one.

    A weak new password is a 422 from ``PasswordChange``. A wrong current password
    is a 400, and an account with no password (Google only) a 409.
    """
    user = await _load_user_for_update(current_user, session)
    await change_password(session, user, body.current_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
