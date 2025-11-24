from typing import Optional

import typer
from sqlmodel import Session, select

from app.core.db import get_engine
from app.core.security import get_password_hash
from app.models.user import User

app = typer.Typer(help="User management commands")


def get_db_session():
    engine = get_engine()
    with Session(engine) as session:
        yield session


@app.command()
def create_user(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    email: str = typer.Option(..., "--email", "-e", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, confirmation_prompt=True),
    name: Optional[str] = typer.Option(None, "--name", "-n"),
    superuser: bool = typer.Option(False, "--superuser", "--admin", is_flag=True),
):
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
            is_superuser=superuser,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        role = "Superuser" if superuser else "Regular user"
        typer.secho(f"{role} created successfully!", fg=typer.colors.GREEN)
        typer.echo(f"ID: {user.id}")
        typer.echo(f"UUID: {user.uuid}")
        typer.echo(f"Username: {user.username}")
        typer.echo(f"Email: {user.email}")


@app.command()
def reset_password(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    new_password: Optional[str] = typer.Option(
        None,
        "--new-password",
        "-p",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    ),
):
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
