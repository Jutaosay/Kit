# Kit

**EN (Primary)**

Kit is a Windows-focused toolbox repository with a single launcher and modular structure.
It is designed for daily utility workflows while keeping dependency isolation strict via `.venv`.

## Structure

- `kit.py`: main launcher (Rich menu with clear-screen refresh + run-result feedback)
- `Monitor/`: file/download monitoring module
- `Autodark/`: Windows theme switching foundation
- `modules/`: future modules
- `core/`: shared utilities
- `scripts/`: helper scripts
- `docs/`: documentation
- `requirements.txt`: base dependencies

## Virtual Environment Policy (Mandatory)

`kit.py` refuses to run outside virtual environment.

## Recommended Usage (Windows 10)

```bat
cd /d C:\Users\<YourUser>\Codings\Projects\Kit
run.bat
```

`run.bat` will auto-detect Python, create `.venv` if missing, install dependencies, and launch `kit.py`.

## Strict Test (inside venv)

```bat
cd /d C:\Users\<YourUser>\Codings\Projects\Kit
.\.venv\Scripts\activate.bat
python -m py_compile kit.py
python -m py_compile Autodark\autodark.py
python -m py_compile Monitor\monitor.py
```

## Autodark Commands

```bat
python Autodark\autodark.py status
python Autodark\autodark.py auto-preview
python Autodark\autodark.py light
python Autodark\autodark.py dark
python Autodark\autodark.py toggle
```

---

**中文（次要）**

Kit 是一个面向 Windows 的常用功能合集，采用统一入口 + 模块化结构。
核心原则是：所有运行与测试都必须在 `.venv` 中进行，避免污染系统 Python 环境。

## 目录说明

- `kit.py`：主程序入口（Rich 菜单）
- `Monitor/`：文件/下载监控模块
- `Autodark/`：Windows 主题切换基础模块
- `modules/`：后续扩展模块
- `core/`：公共能力
- `scripts/`：辅助脚本
- `docs/`：文档

## 运行要求

- 必须在虚拟环境 `.venv` 中运行
- 非虚拟环境会被 `kit.py` 拒绝执行

## 建议

1. 子模块入口文件统一按功能命名（如 `monitor.py`、`autodark.py`）
2. Launcher 只做路由与调度，不堆业务逻辑
3. 公共配置与工具沉淀到 `core/`


Autodark now supports interactive actions from `kit.py`: `status`, `auto-preview`, `light`, `dark`, `toggle`.


For stable scheduling on mainland Windows hosts, prefer `auto-cst` (fixed UTC+8 rule).


## Launcher UX

- Three-column dashboard layout:
  - Left top: `Main Directory`
  - Left bottom: `Run Status`
  - Right: `Sub Menu` (context actions for selected module)
- Autodark submenu is grouped as `Inspect` vs `Apply`, with recommended action order hints.
- Main command style:
  - `1` / `2` to switch selected module
  - `L<key>` to run a sub-menu action (example: `L1`, `L3`)
  - `q` to quit
- Sub-menu `Run` column now shows executable tokens directly (`L1`, `L2`, ...), with explicit bottom hint text.
- Main Directory panel height is compacted to reduce excessive vertical blank area.
- Monitor sub-menu includes run/info/continuous shortcuts and defaults to INFO logs for clearer progress visibility.
- UI refreshes each loop using `console.clear()` for stable, non-overlapping output.

## Git Push Workflow (token-safe, reproducible)

When pushing from automation environments where interactive credential prompts are unreliable, use an explicit auth header workflow.

1) Load token env (example stores secrets in `~/.openclaw/secrets.env`):

```bash
source /home/ubuntu/.openclaw/secrets.env
```

2) Push with explicit username + token (without writing token to git config):

```bash
git -c http.extraheader="AUTHORIZATION: basic $(printf 'Jutaosay:%s' "$L2_GITHUB_WRITE_TOKEN" | base64 -w0)" \
  push origin main
```

3) Verify:

```bash
git log --oneline origin/main -n 3
```

Notes:
- Prefer write token (`L2`) only for push; use read token (`L1`) for read-only operations.
- Do not hardcode tokens in scripts or commit history.

