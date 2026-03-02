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
        return {"error": "当前不是 Windows 环境，无法读取主题注册表。"}

    with _open_personalize_key(write=False) as key:
        app_val, _ = winreg.QueryValueEx(key, APP_KEY)
        sys_val, _ = winreg.QueryValueEx(key, SYS_KEY)

    return {
        "apps": "light" if int(app_val) == 1 else "dark",
        "system": "light" if int(sys_val) == 1 else "dark",
        "raw": {APP_KEY: int(app_val), SYS_KEY: int(sys_val)},
    }


def _broadcast_theme_change() -> None:
    # 通知系统设置变更，尽量即时生效
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
        raise RuntimeError("当前不是 Windows 环境，无法写入主题注册表。")

    if mode not in {"light", "dark"}:
        raise ValueError("mode 仅支持 light/dark")

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
    # 以 app 主题为主判断
    target = "dark" if state["apps"] == "light" else "light"
    return cmd_set(target)


def cmd_auto_preview() -> int:
    t = get_local_time_info()
    mode = recommended_mode_by_time(t.now)
    print(f"Local time : {t.now.strftime('%Y-%m-%d %H:%M:%S %z')}")
    print(f"Timezone   : {t.tz_name} (UTC{t.utc_offset_hours:+.1f})")
    print(f"Auto mode  : {mode}")
    print("(仅预览，不修改主题)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Windows 主题切换工具（Autodark 基础版）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="查看当前本地时间/时区与主题状态")
    sub.add_parser("light", help="切换到浅色主题")
    sub.add_parser("dark", help="切换到深色主题")
    sub.add_parser("toggle", help="浅色/深色切换")
    sub.add_parser("auto-preview", help="根据当前时间给出自动模式建议（不写注册表）")

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
        parser.print_help()
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
