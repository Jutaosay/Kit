# Kit

Windows 常用功能大合集（统一入口 + 模块化管理）。

## 当前结构

- `kit.py`：主程序入口（Rich 菜单）
- `Monitor/`：已集成监控项目
- `modules/`：后续功能模块
- `core/`：公共能力（日志、配置、工具函数）
- `scripts/`：辅助脚本
- `docs/`：文档
- `requirements.txt`：基础依赖

## 强制虚拟环境策略（必须）

`kit.py` 启动时会检查是否运行在 `.venv` 中：

- 不在虚拟环境：直接退出并给出提示
- 在虚拟环境：正常进入菜单

## 使用方式（推荐）

```bash
cd ~/Codings/Projects/Kit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 kit.py
```

## 测试方式（严格 venv）

```bash
cd ~/Codings/Projects/Kit
scripts/test_in_venv.sh
```

## 规划建议

1. 每个模块单独目录（含 README 与入口）
2. `kit.py` 只做路由分发，不堆业务逻辑
3. 公共配置集中到 `core/`，减少重复代码
