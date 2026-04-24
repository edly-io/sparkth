from typing import cast

import typer
from sqlmodel import Session, select

from app.core.db import get_engine
from app.core.security import get_password_hash
from app.models.rbac import Permission, RoleName, RolePermission, UserRole
from app.models.user import User
from app.services.rbac import ADMIN_PERMISSIONS, DEFAULT_PERMISSIONS

app = typer.Typer(help="User management commands")

VALID_ROLES = [r.value for r in RoleName]


def _assign_role_sync(session: Session, user_id: int, role: RoleName) -> None:
    """Assign a role to a user (sync version for CLI). Idempotent."""
    existing = session.exec(select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role.value)).first()
    if not existing:
        user_role = UserRole(user_id=user_id, role=role.value)
        session.add(user_role)


@app.command()
def create_user(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    email: str = typer.Option(..., "--email", "-e", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, confirmation_prompt=True),
    name: str | None = typer.Option(None, "--name", "-n"),
    role: str = typer.Option("member", "--role", "-r", help=f"User role: {', '.join(VALID_ROLES)}"),
    superuser: bool = typer.Option(
        False, "--superuser", "--admin", is_flag=True, help="[deprecated] Use --role superuser"
    ),
) -> None:
    # --superuser/--admin flag overrides --role for backward compatibility
    if superuser:
        role = RoleName.SUPERUSER.value

    if role not in VALID_ROLES:
        typer.secho(f"Invalid role: {role}. Valid roles: {', '.join(VALID_ROLES)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    role_enum = RoleName(role)

    engine = get_engine()
    with Session(engine) as session:
        existing = session.exec(select(User).where((User.username == username) | (User.email == email))).first()
        if existing:
            typer.secho(
                f"User with username '{username}' or email '{email}' already exists!",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        hashed_password = get_password_hash(password)

        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            name=name or username,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        _assign_role_sync(session, cast(int, user.id), role_enum)
        session.commit()

        typer.secho(f"User created successfully with role '{role}'!", fg=typer.colors.GREEN)
        typer.echo(f"ID: {user.id}")
        typer.echo(f"UUID: {user.uuid}")
        typer.echo(f"Username: {user.username}")
        typer.echo(f"Email: {user.email}")
        typer.echo(f"Role: {role}")


@app.command()
def assign_role(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    role: str = typer.Option(..., "--role", "-r", help=f"Role to assign: {', '.join(VALID_ROLES)}"),
) -> None:
    """Assign a role to an existing user."""
    if role not in VALID_ROLES:
        typer.secho(f"Invalid role: {role}. Valid roles: {', '.join(VALID_ROLES)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    role_enum = RoleName(role)

    engine = get_engine()
    with Session(engine) as session:
        user = session.exec(select(User).where((User.username == identifier) | (User.email == identifier))).first()
        if not user:
            typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        _assign_role_sync(session, cast(int, user.id), role_enum)
        session.commit()

        typer.secho(f"Role '{role}' assigned to user '{user.username}'!", fg=typer.colors.GREEN)


@app.command()
def seed_rbac() -> None:
    """Seed default permissions and role-permission mappings."""
    engine = get_engine()
    with Session(engine) as session:
        created_perms = 0
        created_mappings = 0

        for perm_data in DEFAULT_PERMISSIONS:
            existing = session.exec(select(Permission).where(Permission.name == perm_data["name"])).first()
            if not existing:
                perm = Permission(name=perm_data["name"], description=perm_data["description"])
                session.add(perm)
                session.flush()
                created_perms += 1
                existing = perm

            if perm_data["name"] in ADMIN_PERMISSIONS:
                existing_id = cast(int, existing.id)
                rp_existing = session.exec(
                    select(RolePermission).where(
                        RolePermission.role == RoleName.ADMIN.value,
                        RolePermission.permission_id == existing_id,
                    )
                ).first()
                if not rp_existing:
                    rp = RolePermission(role=RoleName.ADMIN.value, permission_id=existing_id)
                    session.add(rp)
                    created_mappings += 1

        session.commit()

        typer.secho("RBAC seeding complete!", fg=typer.colors.GREEN)
        typer.echo(f"Permissions created: {created_perms}")
        typer.echo(f"Role-permission mappings created: {created_mappings}")


@app.command()
def reset_password(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    new_password: str = typer.Option(
        ...,
        "--new-password",
        "-p",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    ),
) -> None:
    engine = get_engine()
    with Session(engine) as session:
        user = session.exec(select(User).where((User.username == identifier) | (User.email == identifier))).first()

        if not user:
            typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        if user.is_deleted:
            typer.secho(
                "This user is soft-deleted. Restore first if needed.",
                fg=typer.colors.YELLOW,
            )

        hashed_password = get_password_hash(new_password)

        user.hashed_password = hashed_password
        user.update_timestamp()
        session.add(user)
        session.commit()

        typer.secho(
            f"Password reset successfully for user: {user.username}",
            fg=typer.colors.GREEN,
        )
