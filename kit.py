from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).resolve().parent
console = Console()


def in_venv() -> bool:
    return (
        os.environ.get("VIRTUAL_ENV") is not None
        or hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )


def ensure_venv_or_exit() -> None:
    if in_venv():
        return

    msg = (
        "[bold red]Virtual environment is required.[/bold red]\n\n"
        "To avoid polluting system Python, run:\n"
        "[cyan]python -m venv .venv[/cyan]\n"
        "[cyan].\\.venv\\Scripts\\activate.bat[/cyan]\n"
        "[cyan]pip install -r requirements.txt[/cyan]\n\n"
        "Then run:\n"
        "[cyan]python kit.py[/cyan]"
    )
    console.print(Panel.fit(msg, title="Kit Environment Check", border_style="red"))
    raise SystemExit(1)


def run_monitor() -> int:
    monitor_dir = ROOT / "Monitor"
    entry = monitor_dir / "monitor.py"

    if not entry.exists():
        console.print(f"[red]Monitor entry file not found: {entry}[/red]")
        return 1

    console.print(Panel.fit("Starting Monitor module...", title="Kit", border_style="green"))
    return subprocess.call([sys.executable, str(entry)], cwd=str(monitor_dir))


def run_autodark() -> int:
    entry = ROOT / "Autodark" / "autodark.py"
    if not entry.exists():
        console.print(f"[red]Autodark entry file not found: {entry}[/red]")
        return 1

    console.print(Panel.fit("Autodark Controls", title="Kit", border_style="blue"))
    table = Table(title="Autodark Actions")
    table.add_column("Option", style="cyan", no_wrap=True)
    table.add_column("Command", style="magenta")
    table.add_row("1", "status")
    table.add_row("2", "auto-preview")
    table.add_row("3", "light")
    table.add_row("4", "dark")
    table.add_row("5", "toggle")
    table.add_row("b", "back")
    console.print(table)

    choice = console.input("[bold]> Select action:[/bold] ").strip().lower()
    mapping = {
        "1": "status",
        "2": "auto-preview",
        "3": "light",
        "4": "dark",
        "5": "toggle",
    }
    if choice == "b":
        return 0
    cmd = mapping.get(choice)
    if not cmd:
        console.print("[yellow]Invalid action.[/yellow]")
        return 1

    return subprocess.call([sys.executable, str(entry), cmd], cwd=str(ROOT))


def menu() -> str:
    table = Table(title="Kit Modules")
    table.add_column("Option", style="cyan", no_wrap=True)
    table.add_column("Module", style="magenta")
    table.add_row("1", "Monitor")
    table.add_row("2", "Autodark (Windows Theme)")
    table.add_row("q", "Quit")
    console.print(table)
    return console.input("[bold]> Select:[/bold] ").strip().lower()


def main() -> int:
    ensure_venv_or_exit()

    actions: dict[str, Callable[[], int]] = {
        "1": run_monitor,
        "2": run_autodark,
        "q": lambda: 0,
    }

    while True:
        choice = menu()
        action = actions.get(choice)
        if action is None:
            console.print("[yellow]Invalid option. Please try again.[/yellow]")
            continue

        code = action()
        if choice == "q":
            return code
        if code != 0:
            console.print(f"[red]Module exit code: {code}[/red]")


if __name__ == "__main__":
    raise SystemExit(main())
