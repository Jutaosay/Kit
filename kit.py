from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parent
console = Console()


@dataclass
class ModuleResult:
    name: str
    code: int


@dataclass
class AppState:
    selected_module: str = "monitor"
    last_result: ModuleResult | None = None
    last_run_at: str | None = None


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


def _run_monitor(args: list[str], label: str) -> ModuleResult:
    monitor_dir = ROOT / "Monitor"
    entry = monitor_dir / "monitor.py"
    if not entry.exists():
        console.print(f"[red]Monitor entry file not found: {entry}[/red]")
        return ModuleResult(label, 1)

    console.clear()
    console.print(Panel.fit(f"Running: {label}", title="Monitor", border_style="green"))
    code = _run_python_entry(entry=entry, cwd=monitor_dir, args=args)
    return ModuleResult(label, code)


def _run_autodark(cmd: str, label: str) -> ModuleResult:
    entry = ROOT / "Autodark" / "autodark.py"
    if not entry.exists():
        console.print(f"[red]Autodark entry file not found: {entry}[/red]")
        return ModuleResult(label, 1)

    console.clear()
    console.print(Panel.fit(f"Running: {label}", title="Autodark", border_style="blue"))
    code = _run_python_entry(entry=entry, cwd=ROOT, args=[cmd])
    return ModuleResult(label, code)


def _main_menu_panel(state: AppState) -> Panel:
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Key", width=6)
    table.add_column("Module")

    modules = [("1", "monitor", "Monitor"), ("2", "autodark", "Autodark")]
    for key, module_id, label in modules:
        selected = "◉" if state.selected_module == module_id else "○"
        style = "bold green" if state.selected_module == module_id else "white"
        table.add_row(key, f"[{style}]{selected} {label}[/{style}]")

    hint = Text("Select module: 1/2", style="dim")
    return Panel(table, title="Main Directory", subtitle=hint, border_style="green")


def _status_panel(state: AppState) -> Panel:
    t = Table(show_header=False, box=None, pad_edge=False)
    t.add_column("k", style="cyan", width=16)
    t.add_column("v", style="white")

    t.add_row("Selected", state.selected_module)
    if state.last_result is None:
        t.add_row("Last Run", "(none)")
        t.add_row("Exit Code", "-")
    else:
        code_style = "green" if state.last_result.code == 0 else "red"
        t.add_row("Last Run", state.last_result.name)
        t.add_row("Exit Code", f"[{code_style}]{state.last_result.code}[/{code_style}]")
        t.add_row("When", state.last_run_at or "-")

    t.add_row("Python", Path(sys.executable).name)
    t.add_row("Venv", "yes" if in_venv() else "no")

    return Panel(t, title="Run Status", border_style="magenta")


def _submenu_actions(state: AppState) -> list[tuple[str, str, Callable[[], ModuleResult]]]:
    if state.selected_module == "monitor":
        return [
            ("1", "Run once (INFO logs)", lambda: _run_monitor(["--log-level", "INFO"], "Monitor once")),
            ("2", "Show system info", lambda: _run_monitor(["--info"], "Monitor info")),
            ("3", "Continuous mode (1h)", lambda: _run_monitor(["-c", "3600", "--log-level", "INFO"], "Monitor continuous")),
        ]

    return [
        ("1", "Inspect: status (time + theme state)", lambda: _run_autodark("status", "Autodark status")),
        ("2", "Inspect: auto-preview (no write)", lambda: _run_autodark("auto-preview", "Autodark auto-preview")),
        ("3", "Apply: auto-cst (recommended)", lambda: _run_autodark("auto-cst", "Autodark auto-cst")),
        ("4", "Apply: toggle", lambda: _run_autodark("toggle", "Autodark toggle")),
        ("5", "Apply: light", lambda: _run_autodark("light", "Autodark light")),
        ("6", "Apply: dark", lambda: _run_autodark("dark", "Autodark dark")),
    ]


def _submenu_panel(state: AppState) -> Panel:
    actions = _submenu_actions(state)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Key", style="cyan", width=6)
    table.add_column("Type", style="magenta", width=10)
    table.add_column("Action", style="white")

    for key, label, _ in actions:
        action_type = "Inspect" if "Inspect:" in label else "Apply"
        clean_label = label.replace("Inspect: ", "").replace("Apply: ", "")
        table.add_row(key, action_type, clean_label)

    if state.selected_module == "autodark":
        tips = (
            "Tips: start with status/auto-preview, then apply auto-cst. "
            "light/dark are manual overrides."
        )
    else:
        tips = "Tips: use s1 for normal run, s2 for diagnostics, s3 for long-running monitor."

    footer = Text("Input: 1/2 switch module | s<key> run action | q quit", style="dim")
    return Panel(
        table,
        title=f"Sub Menu · {state.selected_module}",
        subtitle=Text(tips, style="dim") + Text("\n") + footer,
        border_style="blue",
    )


def _render_ui(state: AppState) -> None:
    console.clear()

    layout = Layout()
    layout.split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=3),
    )

    layout["left"].split_column(
        Layout(name="main", ratio=3),
        Layout(name="status", ratio=2),
    )

    layout["main"].update(_main_menu_panel(state))
    layout["status"].update(_status_panel(state))
    layout["right"].update(_submenu_panel(state))

    console.print(layout)


def _apply_action(state: AppState, token: str) -> bool:
    token = token.strip().lower()
    if token == "1":
        state.selected_module = "monitor"
        return True
    if token == "2":
        state.selected_module = "autodark"
        return True

    if token.startswith("s") and len(token) >= 2:
        key = token[1:]
        actions = {k: runner for k, _, runner in _submenu_actions(state)}
        runner = actions.get(key)
        if runner is None:
            console.print(f"[yellow]Unknown sub action: {key}[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            return True

        result = runner()
        state.last_result = result
        state.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result.code == 0:
            console.print(f"[green]{result.name} completed successfully.[/green]")
        else:
            console.print(f"[red]{result.name} exited with code {result.code}.[/red]")

        console.input("[dim]Press Enter to return to dashboard...[/dim]")
        return True

    if token == "q":
        return False

    console.print("[yellow]Invalid input. Use 1/2, s<key>, or q.[/yellow]")
    console.input("[dim]Press Enter to continue...[/dim]")
    return True


def main() -> int:
    ensure_venv_or_exit()

    state = AppState()
    running = True

    while running:
        _render_ui(state)
        cmd = console.input("[bold cyan]> Command:[/bold cyan] ")
        running = _apply_action(state, cmd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
