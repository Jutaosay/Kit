# Kit

**EN (Primary)**

Kit is a Windows-focused toolbox repository with a single launcher and modular structure.
It is designed for daily utility workflows while keeping dependency isolation strict via `.venv`.

## Structure

- `kit.py`: main launcher (Rich menu with clear-screen refresh + run-result feedback)
- `Monitor/`: file/download monitoring module
- `Autodark/`: Windows theme switching foundation
- `Cleaner/`: Windows cache/residue listing module
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
python -m py_compile Cleaner\cleaner.py
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

- Main menu uses full-screen refresh (`console.clear()`) for cleaner interaction.
- After each module run, launcher shows exit status and asks for next step (`rerun/main menu/quit`).
- Autodark has its own sub-menu loop with immediate rerun support.
- Monitor is launched with `--log-level INFO` by default via launcher so scan progress is clearly visible.

## Cleaner Commands

```bat
python Cleaner\cleaner.py
python Cleaner\cleaner.py --top 100 --min-large-mb 2048
python Cleaner\cleaner.py --portable-root D:\\PortableApps --portable-root E:\\Tools
python Cleaner\cleaner.py --snapshot-path cleaner_snapshot.json
python Cleaner\cleaner.py --size-delta-threshold-mb 100 --diff-top 20
python Cleaner\cleaner.py --registry-residue
python Cleaner\cleaner.py --registry-residue --registry-top 200 --json
```

Cleaner is report-only (no deletion), now with risk scoring, incremental snapshot diff, stronger installed-signature matching, and prioritized registry-residue triage.


Default portable root includes: `C:\Users\<YourUser>\Repo\Applications`
