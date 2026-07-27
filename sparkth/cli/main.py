import typer

from sparkth.cli import analytics, groups, roles, users
from sparkth.lib.log import configure_logging

app = typer.Typer(help="Root command for all CLI tools")

app.add_typer(users.app, name="users")
app.add_typer(roles.app, name="roles")
app.add_typer(groups.app, name="groups")
app.add_typer(analytics.app, name="analytics")


def main() -> None:
    configure_logging()
    app()


if __name__ == "__main__":
    main()
