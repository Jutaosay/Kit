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
        "[bold red]检测到当前不在虚拟环境中运行。[/bold red]\n\n"
        "为避免污染系统 Python，请先执行：\n"
        "[cyan]python -m venv .venv[/cyan]\n"
        "[cyan].\\.venv\\Scripts\\activate.bat[/cyan]\n"
        "[cyan]pip install -r requirements.txt[/cyan]\n\n"
        "然后再运行：\n"
        "[cyan]python kit.py[/cyan]"
    )
    console.print(Panel.fit(msg, title="Kit 环境检查", border_style="red"))
    raise SystemExit(1)


def run_monitor() -> int:
    monitor_dir = ROOT / "Monitor"
    app = monitor_dir / "monitor.py"

    if not app.exists():
        console.print(f"[red]未找到 Monitor 入口文件：{app}[/red]")
        return 1

    console.print(Panel.fit("启动 Monitor 模块...", title="Kit", border_style="green"))
    return subprocess.call([sys.executable, str(app)], cwd=str(monitor_dir))




def run_autodark() -> int:
    autodark = ROOT / "Autodark" / "autodark.py"
    if not autodark.exists():
        console.print(f"[red]未找到 Autodark 入口文件：{autodark}[/red]")
        return 1

    console.print(Panel.fit("启动 Autodark 模块...", title="Kit", border_style="blue"))
    console.print("[cyan]提示：在 Windows 上可执行 light/dark/toggle，当前先查看状态。[/cyan]")
    return subprocess.call([sys.executable, str(autodark), "status"], cwd=str(ROOT))

def menu() -> str:
    table = Table(title="Kit 模块菜单")
    table.add_column("选项", style="cyan", no_wrap=True)
    table.add_column("模块", style="magenta")
    table.add_row("1", "Monitor")
    table.add_row("2", "Autodark（Windows 主题）")
    table.add_row("q", "退出")
    console.print(table)
    return console.input("[bold]> 请输入选项：[/bold]").strip().lower()


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
            console.print("[yellow]无效选项，请重试。[/yellow]")
            continue
        code = action()
        if choice == "q":
            return code
        if code != 0:
            console.print(f"[red]模块退出码：{code}[/red]")


if __name__ == "__main__":
    raise SystemExit(main())
