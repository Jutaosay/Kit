# Autodark

Windows 主题切换基础模块（为后续自动切换打基础）。

## 功能

- 读取本地时间与时区（用于自动策略）
- 读取当前 Windows 主题状态（app/system）
- 切换浅色/深色主题
- `auto-preview` 预览自动模式建议（不写入）

## 命令

```bat
python Autodark\autodark.py status
python Autodark\autodark.py light
python Autodark\autodark.py dark
python Autodark\autodark.py toggle
python Autodark\autodark.py auto-preview
```

## 说明

- 需要在 Windows 环境执行主题切换相关命令。
- 当前自动策略仅做时间判断预览：
  - 19:00~06:59 推荐 dark
  - 07:00~18:59 推荐 light


### Auto apply logic

- Reads local time and timezone from the running system.
- Uses local hour window to choose mode (`dark` or `light`).
- Default expectation is UTC+8 (`--expected-utc-offset 8`).
- If current theme already matches target, no change is applied unless `--force` is used.


### Fixed UTC+8 schedule (recommended)

- `auto-cst` ignores local timezone setting and computes mode from UTC+8 directly.
- Rule: **dark 18:00-05:59**, **light 06:00-17:59** (CST/UTC+8).
- Suitable for Windows Task Scheduler one-shot runs.
