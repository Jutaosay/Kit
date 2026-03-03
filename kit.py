from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).resolve().parent
console = Console()


@dataclass
class ModuleResult:
    name: str
    code: int


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


def _run_python_entry(entry: Path, cwd: Path, args: list[str] | None = None) -> int:
    cmd = [sys.executable, str(entry)]
    if args:
        cmd.extend(args)
    return subprocess.call(cmd, cwd=str(cwd))


def run_monitor() -> ModuleResult:
    monitor_dir = ROOT / "Monitor"
    entry = monitor_dir / "monitor.py"

    if not entry.exists():
        console.print(f"[red]Monitor entry file not found: {entry}[/red]")
        return ModuleResult("Monitor", 1)

    code = _run_python_entry(entry=entry, cwd=monitor_dir)
    return ModuleResult("Monitor", code)


def _autodark_action_menu() -> str:
    table = Table(title="Autodark Actions")
    table.add_column("Option", style="cyan", no_wrap=True)
    table.add_column("Command", style="magenta")
    table.add_row("1", "status")
    table.add_row("2", "auto-preview")
    table.add_row("3", "light")
    table.add_row("4", "dark")
    table.add_row("5", "toggle")
    table.add_row("6", "auto-cst (UTC+8 fixed schedule)")
    table.add_row("b", "back")
    console.print(table)
    return console.input("[bold]> Select action:[/bold] ").strip().lower()


def run_autodark() -> ModuleResult:
    entry = ROOT / "Autodark" / "autodark.py"
    if not entry.exists():
        console.print(f"[red]Autodark entry file not found: {entry}[/red]")
        return ModuleResult("Autodark", 1)

    mapping = {
        "1": "status",
        "2": "auto-preview",
        "3": "light",
        "4": "dark",
        "5": "toggle",
        "6": "auto-cst",
    }

    while True:
        console.clear()
        console.print(Panel.fit("Autodark Controls", title="Kit", border_style="blue"))
        choice = _autodark_action_menu()

        if choice == "b":
            return ModuleResult("Autodark", 0)

        cmd = mapping.get(choice)
        if not cmd:
            console.print("[yellow]Invalid action.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        code = _run_python_entry(entry=entry, cwd=ROOT, args=[cmd])
        if code != 0:
            console.print(f"[red]Autodark exited with code {code}[/red]")
        else:
            console.print("[green]Autodark action completed.[/green]")

        next_choice = console.input("[bold][r]erun action menu / [m]ain menu / [q]uit:[/bold] ").strip().lower()
        if next_choice == "q":
            return ModuleResult("Autodark", 0)
        if next_choice == "m":
            return ModuleResult("Autodark", code)


def run_cleaner() -> ModuleResult:
    entry = ROOT / "Cleaner" / "cleaner.py"
    if not entry.exists():
        console.print(f"[red]Cleaner entry file not found: {entry}[/red]")
        return ModuleResult("Cleaner", 1)

    code = _run_python_entry(entry=entry, cwd=ROOT)
    return ModuleResult("Cleaner", code)


def _render_main_menu(last_result: ModuleResult | None = None) -> str:
    console.clear()
    console.print(Panel.fit("Kit Launcher", title="Kit", border_style="green"))

    if last_result is not None:
        style = "green" if last_result.code == 0 else "red"
        console.print(
            f"[{style}]Last run:[/{style}] {last_result.name} exited with code {last_result.code}"
        )

    table = Table(title="Kit Modules")
    table.add_column("Option", style="cyan", no_wrap=True)
    table.add_column("Module", style="magenta")
    table.add_row("1", "Monitor")
    table.add_row("2", "Autodark (Windows Theme)")
    table.add_row("3", "Cleaner (Cache/Residue Scanner)")
    table.add_row("q", "Quit")
    console.print(table)
    return console.input("[bold]> Select:[/bold] ").strip().lower()


def _post_module_prompt(result: ModuleResult) -> str:
    if result.code == 0:
        console.print(f"[green]{result.name} completed successfully.[/green]")
    else:
        console.print(f"[red]{result.name} exited with code {result.code}.[/red]")

    return console.input("[bold][r]erun / [m]ain menu / [q]uit:[/bold] ").strip().lower()


def main() -> int:
    ensure_venv_or_exit()

    actions: dict[str, tuple[str, Callable[[], ModuleResult]]] = {
        "1": ("Monitor", run_monitor),
        "2": ("Autodark", run_autodark),
        "3": ("Cleaner", run_cleaner),
    }

    last_result: ModuleResult | None = None

    while True:
        choice = _render_main_menu(last_result=last_result)

        if choice == "q":
            return 0

        action_entry = actions.get(choice)
        if action_entry is None:
            console.print("[yellow]Invalid option. Please try again.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        _, action = action_entry
        result = action()
        last_result = result

        followup = _post_module_prompt(result)
        if followup == "q":
            return 0
        if followup == "r":
            # rerun same module once immediately; then continue normal loop
            rerun_result = action()
            last_result = rerun_result
            followup2 = _post_module_prompt(rerun_result)
            if followup2 == "q":
                return 0


if __name__ == "__main__":
    raise SystemExit(main())
