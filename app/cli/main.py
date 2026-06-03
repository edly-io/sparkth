import typer

from app.lib.log import configure_logging

from . import users

app = typer.Typer(help="Root command for all CLI tools")

app.add_typer(users.app, name="users")


def main() -> None:
    configure_logging()
    app()


if __name__ == "__main__":
    main()
