from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import has_role
from sparkth.lib.permissions.scopes import GLOBAL
from sparkth.schemas import User as UserSchema
from sparkth.schemas import UserLanguageUpdate

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
    # ``current_user`` is safe to mutate directly: FastAPI resolves and caches
    # ``Depends(get_async_session)`` once per request, and ``get_current_user`` takes
    # that same dependency to look the row up, so ``current_user`` is already attached
    # to ``session`` below rather than to some other, detached session.
    current_user.language = update.language
    await session.commit()

    return await _to_schema(current_user, session)
