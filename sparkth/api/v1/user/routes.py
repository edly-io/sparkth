"""The authenticated caller's own profile: ``GET`` and ``PATCH /user/me``.

Both endpoints serve the caller and nobody else. Neither takes a user id, so a
request can only ever read or write its own row.

``is_admin`` is not a stored column: it is derived per response from whether the
user holds the ``admin`` role at the global scope, and filled in during
serialization rather than read off the model.

``PATCH`` carries the preferred language. ``language`` is required in the body
because ``None`` is a meaningful value rather than a missing one — an explicit
``null`` clears a previous choice, so the platform default applies again, while
omitting the field is a 422.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.user.schemas import User as UserSchema
from sparkth.api.v1.user.schemas import UserLanguageUpdate
from sparkth.core.models.user import User
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import has_role
from sparkth.lib.permissions.scopes import GLOBAL

router = APIRouter()


async def _to_schema(user: User, session: AsyncSession) -> UserSchema:
    """Serialize a user, filling in the ``is_admin`` flag the model does not store.

    "global" is the root scope; admin-ness is membership of the admin role there.
    """
    is_admin = await has_role(user, "admin", GLOBAL, None, session)
    return UserSchema.model_validate(user).model_copy(update={"is_admin": is_admin})


@router.get("/me", response_model=UserSchema)
async def get_user(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserSchema:
    """Fetch the current authenticated user from the JWT token.

    ``is_admin`` is derived from whether the user holds the global ``admin`` role;
    it is not a stored column. ``language`` is the raw stored preference — ``None``
    when the user never chose one.
    """
    return await _to_schema(current_user, session)


@router.patch("/me", response_model=UserSchema)
async def update_user_language(
    update: UserLanguageUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserSchema:
    """Set or clear the current user's preferred language.

    The tag is validated against the supported-language allowlist by
    ``UserLanguageUpdate``, so an unsupported value is a 422 before reaching here.
    An explicit ``null`` clears the preference.
    """
    # Load the row this request intends to write instead of mutating the injected
    # principal. In production ``get_current_user`` resolves the same request-scoped
    # session, so this is a cheap identity-map hit — the re-fetch is a deliberate
    # guard, not an optimisation. Its job is to make a write against an instance that
    # is *not* attached to ``session`` fail loudly, rather than have ``commit()``
    # persist nothing and the endpoint still answer 200; that failure mode shows up
    # neither in the response nor in a test that asserts on it.
    user = await session.get(User, current_user.id)
    if user is None:
        # Unreachable while ``get_current_user`` is the only source of a principal —
        # it already answers 401 when the row is gone. ``HTTPException`` here mirrors
        # that dependency: an authenticated principal without a row is an
        # authentication-boundary condition, not a domain error to route through the
        # exception-handler registry.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.language = update.language
    # updated_at has a default_factory but no onupdate, so the bump is manual.
    user.update_timestamp()
    await session.commit()

    return await _to_schema(user, session)
