import typer

from . import users

app = typer.Typer(help="Root command for all CLI tools")

app.add_typer(users.app, name="users")


def main():
    app()


if __name__ == "__main__":
    main()
