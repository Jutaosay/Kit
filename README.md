# Kit

Windows 常用功能大合集（统一入口 + 模块化管理）。

## 当前结构

- `kit.py`：主程序入口（Rich 菜单）
- `Monitor/`：已集成监控项目
- `Autodark/`：Windows 主题切换基础模块
- `modules/`：后续功能模块
- `core/`：公共能力（日志、配置、工具函数）
- `scripts/`：辅助脚本
- `docs/`：文档
- `requirements.txt`：基础依赖

## 强制虚拟环境策略（必须）

`kit.py` 启动时会检查是否运行在 `.venv` 中：

- 不在虚拟环境：直接退出并给出提示
- 在虚拟环境：正常进入菜单

## 使用方式（推荐，Windows 10）

```bat
cd /d C:\Users\<你用户名>\Codings\Projects\Kit
python -m venv .venv
.\.venv\Scripts\activate.bat
pip install -r requirements.txt
python kit.py
```

## 测试方式（严格 venv）

```bat
cd /d C:\Users\<你用户名>\Codings\Projects\Kit
.\.venv\Scripts\activate.bat
python -m py_compile kit.py
python -m py_compile Autodark\main.py
```

## Autodark（基础能力）

```bat
python Autodark\main.py status
python Autodark\main.py auto-preview
python Autodark\main.py light
python Autodark\main.py dark
python Autodark\main.py toggle
```

说明：
- `status` 会读取本地时间与时区（UTC offset）并展示当前主题状态。
- 当前自动策略仅做预览，为后续自动切换打基础。

## 规划建议

1. 每个模块单独目录（含 README 与入口）
2. `kit.py` 只做路由分发，不堆业务逻辑
3. 公共配置集中到 `core/`，减少重复代码
