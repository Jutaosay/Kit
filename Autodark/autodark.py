from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import sys
from dataclasses import dataclass

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import winreg

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
APP_KEY = "AppsUseLightTheme"
SYS_KEY = "SystemUsesLightTheme"


@dataclass
class TimeInfo:
    now: dt.datetime
    tz_name: str
    utc_offset_hours: float


def get_local_time_info() -> TimeInfo:
    now = dt.datetime.now().astimezone()
    offset = now.utcoffset() or dt.timedelta(0)
    return TimeInfo(
        now=now,
        tz_name=now.tzname() or "Unknown",
        utc_offset_hours=offset.total_seconds() / 3600,
    )


def _open_personalize_key(write: bool = False):
    access = winreg.KEY_READ
    if write:
        access = winreg.KEY_READ | winreg.KEY_SET_VALUE
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, access)


def read_theme_state() -> dict:
    if not IS_WINDOWS:
        return {"error": "Non-Windows environment. Theme registry is unavailable."}

    with _open_personalize_key(write=False) as key:
        app_val, _ = winreg.QueryValueEx(key, APP_KEY)
        sys_val, _ = winreg.QueryValueEx(key, SYS_KEY)

    return {
        "apps": "light" if int(app_val) == 1 else "dark",
        "system": "light" if int(sys_val) == 1 else "dark",
        "raw": {APP_KEY: int(app_val), SYS_KEY: int(sys_val)},
    }


def _broadcast_theme_change() -> None:
    # Notify Windows that theme settings changed for faster UI refresh.
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "ImmersiveColorSet",
        SMTO_ABORTIFHUNG,
        2000,
        None,
    )


def set_theme(mode: str, apply_apps: bool = True, apply_system: bool = True) -> None:
    if not IS_WINDOWS:
        raise RuntimeError("Non-Windows environment. Unable to write theme registry.")

    if mode not in {"light", "dark"}:
        raise ValueError("mode must be 'light' or 'dark'")

    value = 1 if mode == "light" else 0
    with _open_personalize_key(write=True) as key:
        if apply_apps:
            winreg.SetValueEx(key, APP_KEY, 0, winreg.REG_DWORD, value)
        if apply_system:
            winreg.SetValueEx(key, SYS_KEY, 0, winreg.REG_DWORD, value)

    _broadcast_theme_change()


def recommended_mode_by_time(now: dt.datetime, dark_start: int = 19, light_start: int = 7) -> str:
    hour = now.hour
    if dark_start <= hour or hour < light_start:
        return "dark"
    return "light"


def cmd_status() -> int:
    t = get_local_time_info()
    print(f"Local time : {t.now.strftime('%Y-%m-%d %H:%M:%S %z')}")
    print(f"Timezone   : {t.tz_name} (UTC{t.utc_offset_hours:+.1f})")

    state = read_theme_state()
    if "error" in state:
        print(f"Theme      : {state['error']}")
        return 1

    print(f"Theme(app) : {state['apps']}")
    print(f"Theme(sys) : {state['system']}")
    print(f"Recommend  : {recommended_mode_by_time(t.now)}")
    return 0


def cmd_set(mode: str) -> int:
    t = get_local_time_info()
    print(f"Local time : {t.now.strftime('%Y-%m-%d %H:%M:%S %z')}")
    print(f"Timezone   : {t.tz_name} (UTC{t.utc_offset_hours:+.1f})")
    set_theme(mode)
    print(f"Theme set  : {mode}")
    return 0


def cmd_toggle() -> int:
    state = read_theme_state()
    if "error" in state:
        print(state["error"])
        return 1

    target = "dark" if state["apps"] == "light" else "light"
    return cmd_set(target)


def cmd_auto_preview() -> int:
    t = get_local_time_info()
    mode = recommended_mode_by_time(t.now)
    print(f"Local time : {t.now.strftime('%Y-%m-%d %H:%M:%S %z')}")
    print(f"Timezone   : {t.tz_name} (UTC{t.utc_offset_hours:+.1f})")
    print(f"Auto mode  : {mode}")
    print("(Preview only. No registry changes.)")
    return 0




def cmd_auto_apply(dark_start: int, light_start: int, expected_utc_offset: float = 8.0, force: bool = False) -> int:
    t = get_local_time_info()
    mode = recommended_mode_by_time(t.now, dark_start=dark_start, light_start=light_start)

    print(f"Local time : {t.now.strftime('%Y-%m-%d %H:%M:%S %z')}")
    print(f"Timezone   : {t.tz_name} (UTC{t.utc_offset_hours:+.1f})")
    print(f"Auto mode  : {mode} (dark_start={dark_start}, light_start={light_start})")

    if abs(t.utc_offset_hours - expected_utc_offset) > 0.01:
        print(
            f"Warning    : current UTC offset is {t.utc_offset_hours:+.1f}, "
            f"expected UTC{expected_utc_offset:+.1f}."
        )

    state = read_theme_state()
    if "error" in state:
        print(state["error"])
        return 1

    current = state["apps"]
    print(f"Current    : {current}")

    if (not force) and current == mode:
        print("Action     : no change needed")
        return 0

    set_theme(mode)
    print(f"Action     : theme switched to {mode}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Autodark: Windows theme switcher foundation")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show local time/timezone and current theme state")
    sub.add_parser("light", help="Switch to light theme")
    sub.add_parser("dark", help="Switch to dark theme")
    sub.add_parser("toggle", help="Toggle light/dark theme")
    sub.add_parser("auto-preview", help="Preview auto mode by current local time")

    auto_parser = sub.add_parser("auto", help="Apply auto mode by local time")
    auto_parser.add_argument("--dark-start", type=int, default=19, help="Dark mode start hour (0-23)")
    auto_parser.add_argument("--light-start", type=int, default=7, help="Light mode start hour (0-23)")
    auto_parser.add_argument(
        "--expected-utc-offset",
        type=float,
        default=8.0,
        help="Expected local UTC offset, default UTC+8",
    )
    auto_parser.add_argument("--force", action="store_true", help="Force apply even if mode is already correct")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.cmd == "status":
            return cmd_status()
        if args.cmd == "light":
            return cmd_set("light")
        if args.cmd == "dark":
            return cmd_set("dark")
        if args.cmd == "toggle":
            return cmd_toggle()
        if args.cmd == "auto-preview":
            return cmd_auto_preview()
        if args.cmd == "auto":
            return cmd_auto_apply(
                dark_start=args.dark_start,
                light_start=args.light_start,
                expected_utc_offset=args.expected_utc_offset,
                force=args.force,
            )
        parser.print_help()
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
