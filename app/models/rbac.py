from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from .base import TimestampedModel


class RoleName(str, Enum):
    SUPERUSER = "superuser"
    ADMIN = "admin"
    MEMBER = "member"


class UserRole(TimestampedModel, table=True):
    __tablename__ = "user_role"
    __table_args__ = (UniqueConstraint("user_id", "role"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str = Field(max_length=20, index=True)


class Permission(TimestampedModel, table=True):
    __tablename__ = "permission"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    description: str = Field(max_length=255)


class RolePermission(TimestampedModel, table=True):
    __tablename__ = "role_permission"
    __table_args__ = (UniqueConstraint("role", "permission_id"),)

    id: int | None = Field(default=None, primary_key=True)
    role: str = Field(max_length=20, index=True)
    permission_id: int = Field(foreign_key="permission.id", index=True)
