import asyncio
import json
import os
from pathlib import Path
import subprocess
from typing import Annotated

from rich import print
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
import typer

from app.core.config import settings

app = typer.Typer()


# ── Database utilities ───────────────────────────────────────────────────


async def clear_alembic_task():
    """Clear Alembic version history from the database."""
    print("[yellow]Clearing Alembic version history[/yellow]")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("[red]Error: DATABASE_URL environment variable is not set[/red]")
        raise typer.Exit(1)

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("DELETE FROM alembic_version"))
            await connection.commit()
            if result.rowcount > 0:
                print(
                    f"[green]Alembic version history cleared ({result.rowcount} rows)[/green]"
                )
            else:
                print("[cyan]Alembic version history is already empty[/cyan]")
    except SQLAlchemyError as e:
        print(f"[red]Error clearing Alembic version history:[/red] {str(e)}")
        if "alembic_version" in str(e):
            print("[cyan]alembic_version table does not exist; skipping clear[/cyan]")
        else:
            print(
                "[yellow]Skipping Alembic clear; leaving migration history unchanged[/yellow]"
            )
    except Exception as e:
        print(f"[red]Unexpected error while clearing Alembic history:[/red] {str(e)}")
        print(
            "[yellow]Skipping Alembic clear; leaving migration history unchanged[/yellow]"
        )
    finally:
        await engine.dispose()


async def create_extensions_task(extensions: list[str]) -> None:
    """Ensure that the given PostgreSQL extensions exist."""
    if not extensions:
        print("[cyan]No extensions specified; skipping extension creation[/cyan]")
        return

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("[red]Error: DATABASE_URL environment variable is not set[/red]")
        raise typer.Exit(1)

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.begin() as connection:
            for ext in extensions:
                ext_name = ext.strip()
                if not ext_name:
                    continue
                print(
                    f"[yellow]Ensuring PostgreSQL extension exists:[/yellow] {ext_name}"
                )
                await connection.execute(
                    text(f'CREATE EXTENSION IF NOT EXISTS "{ext_name}";')
                )
        print("[green]PostgreSQL extensions ensured successfully[/green]")
    except SQLAlchemyError as e:
        print(f"[red]Error ensuring PostgreSQL extensions:[/red] {str(e)}")
        raise
    finally:
        await engine.dispose()


# ── Commands ─────────────────────────────────────────────────────────────


@app.command()
def runserver():
    """Start the FastAPI development server with uvicorn."""
    try:
        server_command = (
            "uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
            if settings.DEBUG
            else "uvicorn app.main:app --host 0.0.0.0 --port 8000"
        )
        print(f"Running FastAPI server: {server_command}")
        subprocess.run(server_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error:[/red] {e}")
        raise


@app.command()
def makemigrations(comment: Annotated[str, typer.Argument()] = "auto"):
    """Create a new Alembic migration revision (autogenerate)."""
    try:
        revision_command = f'alembic revision --autogenerate -m "{comment}"'
        print(f"Running Alembic migrations: {revision_command}")
        subprocess.run(revision_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error:[/red] {e}")
        raise
    print("[green]Make migrations complete[/green]")


@app.command()
def migrate():
    """Run Alembic migrations to upgrade the database to head."""
    try:
        upgrade_command = "alembic upgrade head"
        print(f"Running Alembic upgrade: {upgrade_command}")
        subprocess.run(upgrade_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error:[/red] {e}")
        raise
    print("[green]Migration complete[/green]")


@app.command()
def showmigrations():
    """Show the current Alembic migration history."""
    try:
        history_command = "alembic history"
        print(f"Running Alembic history: {history_command}")
        subprocess.run(history_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error:[/red] {e}")
        raise
    print("[green]Show migrations complete[/green]")


@app.command()
def clearalembic():
    """Clear Alembic migration history (reset version table)."""
    asyncio.run(clear_alembic_task())


@app.command()
def createextensions(
    extensions: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "PostgreSQL extensions to ensure exist, e.g. "
                "'citext pgcrypto'. If omitted, nothing is done."
            ),
        ),
    ] = None,
):
    """Ensure one or more PostgreSQL extensions exist.

    Examples:
        python manage.py createextensions citext
        python manage.py createextensions citext pgcrypto
    """
    if not extensions:
        print("[cyan]No extensions specified; skipping extension creation[/cyan]")
        return
    asyncio.run(create_extensions_task(list(extensions)))


@app.command()
def generateopenapi():
    """Generate the OpenAPI schema JSON file."""
    from app.main import app

    openapi_path = Path("openapi.json")
    with openapi_path.open("w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, ensure_ascii=False, indent=2)
    print(f"[green]OpenAPI schema generated at {openapi_path.name}[/green]")


@app.command()
def worker():
    """Run the RabbitMQ message consumer (standalone)."""
    try:
        worker_command = "python -m app.infrastructure.messaging.main"
        print(f"Starting message consumer: {worker_command}")
        subprocess.run(worker_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error:[/red] {e}")
        raise


@app.command()
def scheduler():
    """Run the APScheduler background scheduler (standalone)."""
    try:
        scheduler_command = "python -m app.infrastructure.scheduler.main"
        print(f"Starting scheduler: {scheduler_command}")
        subprocess.run(scheduler_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[red]Error:[/red] {e}")
        raise


@app.command()
def precommit(
    fix: Annotated[
        bool,
        typer.Option("--fix", "-f", help="Auto-fix formatting and safe lint issues"),
    ] = False,
    skip_tests: Annotated[
        bool,
        typer.Option("--skip-tests", "-s", help="Skip the pytest step"),
    ] = False,
):
    """Run the full pre-commit check sequence.

    Steps: Black -> Ruff -> Pyright -> Import Linter -> Pytest.
    Stops on the first failure.

    Examples:
        python manage.py precommit
        python manage.py precommit --fix
        python manage.py precommit --skip-tests
    """
    steps: list[tuple[str, list[str]]] = []

    if fix:
        steps.append(("Format (Black)", ["black", "app/", "tests/"]))
        steps.append(
            ("Lint & fix (Ruff)", ["ruff", "check", "--fix", "app/", "tests/"])
        )
    else:
        steps.append(
            ("Check formatting (Black)", ["black", "--check", "app/", "tests/"])
        )
        steps.append(("Lint (Ruff)", ["ruff", "check", "app/", "tests/"]))

    steps.append(("Type check (Pyright)", ["pyright", "app/"]))
    steps.append(("Import contracts (lint-imports)", ["lint-imports"]))

    if not skip_tests:
        steps.append(("Test (Pytest)", ["pytest", "tests/", "-x", "-q", "--tb=short"]))

    for i, (label, cmd) in enumerate(steps, 1):
        print(f"\n[bold cyan][{i}/{len(steps)}] {label}[/bold cyan]")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"\n[red]✗ Step failed: {label}[/red]")
            raise typer.Exit(1)
        print(f"[green]✓ {label} passed[/green]")

    print("\n[bold green]All checks passed — safe to commit.[/bold green]")


@app.callback()
def main(ctx: typer.Context):
    print(f"Executing the command: {ctx.invoked_subcommand}")


if __name__ == "__main__":
    app()
