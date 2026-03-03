from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.table import Table

IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import winreg

console = Console()

UNINSTALL_REG_PATHS = [
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", 0),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0),
]

CACHE_NAME_PATTERNS = {
    "cache",
    "temp",
    "tmp",
    "logs",
    "log",
    "crashdumps",
    "shadercache",
    "code cache",
}

GAME_HINTS = {
    "steam",
    "epic games",
    "riot games",
    "battle.net",
    "ubisoft",
    "game",
    "games",
    "genshin",
    "minecraft",
}

GAME_ASSET_EXTS = {".pak", ".ucas", ".utoc", ".vpk", ".rpf"}


@dataclass
class InstalledApp:
    name: str
    install_location: str | None
    publisher: str | None
    uninstall_string: str | None
    display_icon: str | None


@dataclass
class Finding:
    category: str
    path: str
    size_mb: float
    reason: str
    score: int
    risk_level: str
    last_modified_days: int
    game_like: bool = False


@dataclass
class ScanResult:
    roots: list[str]
    installed_count: int
    installed_signature_count: int
    portable_count: int
    findings: list[Finding]


def normalize_name(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def get_windows_root_env() -> list[Path]:
    keys = ["APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"]
    roots: list[Path] = []
    for k in keys:
        v = os.environ.get(k)
        if v:
            p = Path(v)
            if p.exists() and p not in roots:
                roots.append(p)
    return roots


def iter_child_dirs(root: Path, max_depth: int = 1) -> Iterable[Path]:
    if max_depth < 0 or not root.exists():
        return

    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    p = Path(entry.path)
                    yield p
                    if depth < max_depth:
                        stack.append((p, depth + 1))
        except (PermissionError, FileNotFoundError, OSError):
            continue


def folder_size_bytes(path: Path, file_limit: int = 200_000) -> int:
    total = 0
    seen = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    if e.is_symlink():
                        continue
                    if e.is_file(follow_symlinks=False):
                        try:
                            total += e.stat(follow_symlinks=False).st_size
                        except OSError:
                            pass
                        seen += 1
                        if seen >= file_limit:
                            return total
                    elif e.is_dir(follow_symlinks=False):
                        stack.append(Path(e.path))
        except (PermissionError, FileNotFoundError, OSError):
            continue
    return total


def folder_age_days(path: Path) -> int:
    try:
        st = path.stat()
        age_seconds = max(0.0, datetime.now().timestamp() - st.st_mtime)
        return int(age_seconds // 86400)
    except OSError:
        return 9999


def is_game_like(path: Path) -> bool:
    lower = str(path).lower()
    if any(h in lower for h in GAME_HINTS):
        return True

    # quick file extension probe
    try:
        checked = 0
        for p in path.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in GAME_ASSET_EXTS:
                return True
            checked += 1
            if checked >= 2000:
                break
    except (PermissionError, OSError):
        pass

    return False


def read_installed_apps() -> list[InstalledApp]:
    if not IS_WINDOWS:
        return []

    hive_map = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    apps: list[InstalledApp] = []

    for hive_name, reg_path, _ in UNINSTALL_REG_PATHS:
        hive = hive_map[hive_name]
        try:
            with winreg.OpenKey(hive, reg_path, 0, winreg.KEY_READ) as base:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(base, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(base, sub, 0, winreg.KEY_READ) as sk:
                            name = _read_reg_value(sk, "DisplayName")
                            if not name:
                                continue
                            apps.append(
                                InstalledApp(
                                    name=name,
                                    install_location=_read_reg_value(sk, "InstallLocation"),
                                    publisher=_read_reg_value(sk, "Publisher"),
                                    uninstall_string=_read_reg_value(sk, "UninstallString"),
                                    display_icon=_read_reg_value(sk, "DisplayIcon"),
                                )
                            )
                    except OSError:
                        continue
        except OSError:
            continue

    return apps


def _read_reg_value(key, value_name: str) -> str | None:
    try:
        v, _ = winreg.QueryValueEx(key, value_name)
        if isinstance(v, str):
            return v.strip() or None
        return str(v)
    except OSError:
        return None


def _path_stem_from_maybe_quoted(raw: str | None) -> str | None:
    if not raw:
        return None

    s = raw.strip()

    # Prefer explicitly quoted executable/path segment.
    m = re.search(r'"([^\"]+)"', s)
    if m:
        s = m.group(1)

    # Handle common command-line forms where args follow executable.
    lower = s.lower()
    for suffix in [".exe", ".msi", ".bat", ".cmd", ".ps1"]:
        idx = lower.find(suffix)
        if idx != -1:
            s = s[: idx + len(suffix)]
            break

    stem = Path(s).stem
    return stem or None


def build_installed_signatures(installed_apps: list[InstalledApp]) -> set[str]:
    sigs: set[str] = set()
    for app in installed_apps:
        for raw in [app.name, app.publisher, app.install_location, app.uninstall_string, app.display_icon]:
            if not raw:
                continue
            n = normalize_name(raw)
            if len(n) >= 4:
                sigs.add(n)

        for raw in [app.install_location, app.uninstall_string, app.display_icon]:
            stem = _path_stem_from_maybe_quoted(raw)
            if stem:
                n = normalize_name(stem)
                if len(n) >= 4:
                    sigs.add(n)

    return sigs


def scan_portable_names(portable_roots: list[Path], max_depth: int = 2) -> set[str]:
    names: set[str] = set()
    for root in portable_roots:
        if not root.exists():
            continue
        names.add(normalize_name(root.name))
        for d in iter_child_dirs(root, max_depth=max_depth):
            base = normalize_name(d.name)
            if base:
                names.add(base)
            try:
                for e in os.scandir(d):
                    if e.is_file() and e.name.lower().endswith(".exe"):
                        names.add(normalize_name(Path(e.name).stem))
            except (PermissionError, FileNotFoundError, OSError):
                continue
    return {n for n in names if n and len(n) >= 4}


def score_finding(
    *,
    category: str,
    path: Path,
    size_mb: float,
    game_like: bool,
    last_modified_days: int,
) -> tuple[int, str]:
    score = 0

    if size_mb >= 10_240:
        score += 35
    elif size_mb >= 5120:
        score += 28
    elif size_mb >= 2048:
        score += 22
    elif size_mb >= 1024:
        score += 16
    elif size_mb >= 500:
        score += 10
    elif size_mb >= 100:
        score += 6

    score += {
        "possible_uninstall_residue": 25,
        "cache_or_temp": 15,
        "large_directory": 12,
    }.get(category, 8)

    lower_path = str(path).lower()
    if any(k in lower_path for k in ["appdata", "programdata", "program files"]):
        score += 12
    if any(k in lower_path for k in ["cache", "temp", "log"]):
        score += 8

    if game_like:
        score -= 15

    if last_modified_days <= 7:
        score -= 12
    elif last_modified_days <= 30:
        score -= 6
    elif last_modified_days >= 180:
        score += 8

    score = max(0, min(100, score))

    if score >= 70:
        risk = "High"
    elif score >= 40:
        risk = "Medium"
    else:
        risk = "Low"

    return score, risk


def scan_cleaner(
    roots: list[Path],
    installed_apps: list[InstalledApp],
    portable_names: set[str],
    min_large_mb: int = 1024,
) -> ScanResult:
    installed_signatures = build_installed_signatures(installed_apps)
    findings: list[Finding] = []

    for root in roots:
        # scan one and two level directories for residues and cache
        for d in iter_child_dirs(root, max_depth=2):
            name_norm = normalize_name(d.name)
            d_lower = d.name.lower().strip()

            # skip known protected/system-ish dirs quickly
            if d_lower in {"windows", "system32", "winsxs", "driverstore"}:
                continue

            size_b = folder_size_bytes(d)
            size_mb = size_b / 1024 / 1024
            game_like = is_game_like(d)
            age_days = folder_age_days(d)

            if d_lower in CACHE_NAME_PATTERNS and size_mb >= 50:
                score, risk = score_finding(
                    category="cache_or_temp",
                    path=d,
                    size_mb=size_mb,
                    game_like=game_like,
                    last_modified_days=age_days,
                )
                findings.append(
                    Finding(
                        category="cache_or_temp",
                        path=str(d),
                        size_mb=round(size_mb, 1),
                        reason="Large cache/temp/log directory",
                        score=score,
                        risk_level=risk,
                        last_modified_days=age_days,
                        game_like=game_like,
                    )
                )

            if (
                name_norm
                and name_norm not in installed_signatures
                and name_norm not in portable_names
            ):
                in_appdata_or_pf = any(
                    k in str(d).lower() for k in ["appdata", "program files", "programdata"]
                )
                if in_appdata_or_pf and size_mb >= 30:
                    score, risk = score_finding(
                        category="possible_uninstall_residue",
                        path=d,
                        size_mb=size_mb,
                        game_like=game_like,
                        last_modified_days=age_days,
                    )
                    findings.append(
                        Finding(
                            category="possible_uninstall_residue",
                            path=str(d),
                            size_mb=round(size_mb, 1),
                            reason="Directory name not matched by installed/portable signatures",
                            score=score,
                            risk_level=risk,
                            last_modified_days=age_days,
                            game_like=game_like,
                        )
                    )

            if size_mb >= min_large_mb:
                score, risk = score_finding(
                    category="large_directory",
                    path=d,
                    size_mb=size_mb,
                    game_like=game_like,
                    last_modified_days=age_days,
                )
                findings.append(
                    Finding(
                        category="large_directory",
                        path=str(d),
                        size_mb=round(size_mb, 1),
                        reason=f"Directory exceeds {min_large_mb} MB threshold",
                        score=score,
                        risk_level=risk,
                        last_modified_days=age_days,
                        game_like=game_like,
                    )
                )

    # de-duplicate by (category, path)
    uniq = {(f.category, f.path): f for f in findings}
    final_findings = sorted(uniq.values(), key=lambda x: (x.score, x.size_mb), reverse=True)

    return ScanResult(
        roots=[str(r) for r in roots],
        installed_count=len(installed_apps),
        installed_signature_count=len(installed_signatures),
        portable_count=len(portable_names),
        findings=final_findings,
    )


def _finding_key(f: Finding) -> str:
    return f"{f.category}::{f.path}"


def _snapshot_from_result(result: ScanResult) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": [asdict(f) for f in result.findings],
    }


def load_snapshot(snapshot_path: Path) -> dict:
    if not snapshot_path.exists():
        return {"generated_at": None, "findings": []}
    try:
        with snapshot_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"generated_at": None, "findings": []}
        findings = data.get("findings")
        if not isinstance(findings, list):
            findings = []
        return {"generated_at": data.get("generated_at"), "findings": findings}
    except (json.JSONDecodeError, OSError):
        return {"generated_at": None, "findings": []}


def save_snapshot(snapshot_path: Path, result: ScanResult) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _snapshot_from_result(result)
    with snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_snapshot_diff(
    previous_snapshot: dict,
    current_result: ScanResult,
    *,
    size_delta_threshold_mb: float = 50.0,
    top_n: int = 15,
) -> dict:
    prev_findings = previous_snapshot.get("findings", []) if isinstance(previous_snapshot, dict) else []

    prev_map: dict[str, dict] = {}
    for f in prev_findings:
        if not isinstance(f, dict):
            continue
        category = f.get("category")
        path = f.get("path")
        if not isinstance(category, str) or not isinstance(path, str):
            continue
        prev_map[f"{category}::{path}"] = f

    curr_map = {_finding_key(f): f for f in current_result.findings}

    added_keys = [k for k in curr_map if k not in prev_map]
    removed_keys = [k for k in prev_map if k not in curr_map]

    changed_all = []
    for key, curr in curr_map.items():
        prev = prev_map.get(key)
        if not prev:
            continue
        prev_size = float(prev.get("size_mb", 0.0))
        delta = round(curr.size_mb - prev_size, 1)
        if abs(delta) >= size_delta_threshold_mb:
            changed_all.append(
                {
                    "category": curr.category,
                    "path": curr.path,
                    "prev_size_mb": round(prev_size, 1),
                    "curr_size_mb": curr.size_mb,
                    "delta_mb": delta,
                    "risk_level": curr.risk_level,
                    "score": curr.score,
                }
            )

    added = [asdict(curr_map[k]) for k in added_keys]
    removed = [prev_map[k] for k in removed_keys]

    added_top = sorted(added, key=lambda x: (x.get("score", 0), x.get("size_mb", 0)), reverse=True)[:top_n]
    removed_top = sorted(removed, key=lambda x: x.get("size_mb", 0), reverse=True)[:top_n]
    changed_top = sorted(changed_all, key=lambda x: abs(x["delta_mb"]), reverse=True)[:top_n]

    return {
        "previous_generated_at": previous_snapshot.get("generated_at") if isinstance(previous_snapshot, dict) else None,
        "added_count": len(added_keys),
        "removed_count": len(removed_keys),
        "changed_count": len(changed_all),
        "added_top": added_top,
        "removed_top": removed_top,
        "changed_top": changed_top,
    }


def print_result(res: ScanResult, top_n: int = 50, snapshot_diff: dict | None = None) -> None:
    console.print(f"[bold]Scan roots:[/bold] {', '.join(res.roots)}")
    console.print(
        f"[bold]Installed apps:[/bold] {res.installed_count}  |  "
        f"[bold]Installed signatures:[/bold] {res.installed_signature_count}  |  "
        f"[bold]Portable signatures:[/bold] {res.portable_count}"
    )

    table = Table(title=f"Cleaner Findings (Top {min(top_n, len(res.findings))})")
    table.add_column("Risk", style="red")
    table.add_column("Score", style="magenta", justify="right")
    table.add_column("Category", style="cyan")
    table.add_column("Size(MB)", style="magenta", justify="right")
    table.add_column("Age(d)", style="yellow", justify="right")
    table.add_column("Game-like", style="yellow")
    table.add_column("Path", style="green")
    table.add_column("Reason", style="white")

    for f in res.findings[:top_n]:
        table.add_row(
            f.risk_level,
            str(f.score),
            f.category,
            f"{f.size_mb:.1f}",
            str(f.last_modified_days),
            "yes" if f.game_like else "no",
            f.path,
            f.reason,
        )

    console.print(table)

    if snapshot_diff:
        console.print(
            "[bold]Snapshot diff:[/bold] "
            f"+{snapshot_diff.get('added_count', 0)} / "
            f"-{snapshot_diff.get('removed_count', 0)} / "
            f"Δ{snapshot_diff.get('changed_count', 0)}"
        )

    console.print("[bold green]Note:[/bold green] list-only mode. No deletion is performed.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cleaner: list removable cache/residue candidates on Windows")
    p.add_argument("--json", action="store_true", help="Output JSON instead of rich table")
    p.add_argument("--top", type=int, default=50, help="Top findings to display")
    p.add_argument("--min-large-mb", type=int, default=1024, help="Large directory threshold in MB")
    p.add_argument(
        "--portable-root",
        action="append",
        default=[],
        help="Portable app root path (repeatable), used to exclude active portable apps",
    )
    p.add_argument(
        "--snapshot-path",
        default="cleaner_snapshot.json",
        help="Snapshot JSON path for incremental diff (default: cleaner_snapshot.json)",
    )
    p.add_argument("--no-snapshot", action="store_true", help="Disable snapshot read/write and diff output")
    p.add_argument(
        "--size-delta-threshold-mb",
        type=float,
        default=50.0,
        help="Minimum size delta to count as changed in snapshot diff (default: 50MB)",
    )
    p.add_argument(
        "--diff-top",
        type=int,
        default=15,
        help="Top changed/added/removed entries to keep in diff output (default: 15)",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()

    if not IS_WINDOWS:
        console.print("[red]Cleaner is Windows-focused. Current environment is non-Windows.[/red]")
        return 1

    roots = get_windows_root_env()
    portable_roots = [Path(p) for p in args.portable_root]

    # optional common portable hints
    default_portable_hints = [
        Path.home() / "Repo" / "Applications",
        Path.home() / "PortableApps",
        Path("D:/PortableApps"),
    ]
    for hint in default_portable_hints:
        if hint.exists() and hint not in portable_roots:
            portable_roots.append(hint)

    installed = read_installed_apps()
    portable_names = scan_portable_names(portable_roots)

    result = scan_cleaner(
        roots=roots,
        installed_apps=installed,
        portable_names=portable_names,
        min_large_mb=args.min_large_mb,
    )

    snapshot_diff = None
    if not args.no_snapshot:
        snapshot_path = Path(args.snapshot_path)
        previous = load_snapshot(snapshot_path)
        snapshot_diff = build_snapshot_diff(
            previous,
            result,
            size_delta_threshold_mb=args.size_delta_threshold_mb,
            top_n=args.diff_top,
        )
        save_snapshot(snapshot_path, result)

    if args.json:
        payload = {
            "roots": result.roots,
            "installed_count": result.installed_count,
            "installed_signature_count": result.installed_signature_count,
            "portable_count": result.portable_count,
            "findings": [asdict(f) for f in result.findings],
            "snapshot_diff": snapshot_diff,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print_result(result, top_n=args.top, snapshot_diff=snapshot_diff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
