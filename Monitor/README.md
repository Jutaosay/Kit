# Downloads Folder Monitor

[English](#english) | [中文](#中文)

---

<a name="english"></a>

## English

Windows-only Python CLI that keeps your Downloads folder tidy: auto-organizes files, tracks hashes, detects duplicates, and cleans up installers for software you already installed. No third-party dependencies.

### Features
- Automatic file organization into Programs, Documents, Pictures, Media, Others
- Smart filename rules (e.g., `screenshot*`, `*setup*`) take priority over extension matching
- Incremental scanning with SHA1 caching to skip unchanged files
- Duplicate detection plus file type/size/change analytics
- Optional installer cleanup (matches installers in `Programs/` to installed software)
- CSV export of scan results for searching/auditing
- Zero external dependencies; uses Python standard library

### Quick Start
```bash
# Run once (organize + optional installer cleanup + scan)
python monitor.py

# Verbose output
python monitor.py --log-level INFO

# Continuous monitoring (default 2h interval)
python monitor.py -c
python monitor.py -c 3600   # custom interval in seconds

# Show system info
python monitor.py --info

# Duplicate cleanup suggestions
python monitor.py --cleanup

# Installer cleanup (dry run / real)
python monitor.py --clean-installers
python monitor.py --clean-installers --no-dry-run
```

### Command Line Options
| Option | Description |
|--------|-------------|
| `-c, --continuous [SECONDS]` | Run continuously (default 7200s) |
| `--no-ext` | Disable extensions |
| `--ext-only` | Run extensions on existing data only |
| `--cleanup` | Show duplicate cleanup suggestions |
| `--clean-installers` | Scan installers in `Programs/` against installed software |
| `--no-dry-run` | Actually delete installers (use with `--clean-installers`) |
| `--min-confidence FLOAT` | Installer match threshold (default 0.7) |
| `--downloads-path PATH` | Override Downloads folder |
| `--csv-path PATH` | Override CSV output file |
| `--config PATH` | Use a different config file (default `config.json`) |
| `--log-level LEVEL` | DEBUG/INFO/WARNING/ERROR |
| `--log-file PATH` | Write logs to a file |
| `--info, -i` | Show system information |

### Configuration (config.json)
```json
{
  "downloads_path": null,
  "csv_path": "results.csv",
  "monitoring": {
    "interval_seconds": 7200,
    "enable_extensions": true,
    "calculate_sha1": true,
    "incremental_scan": true
  },
  "organization": {
    "auto_organize": true,
    "auto_clean_installers": true,
    "installer_min_confidence": 0.7,
    "categories": {
      "Programs": [".exe", ".msi", ".bat", ".cmd", ".ps1", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".torrent"],
      "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".md", ".csv", ".xls", ".xlsx", ".ppt", ".pptx", ".epub", ".mobi", ".azw", ".azw3", ".py", ".js", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".php", ".java", ".cpp", ".c", ".h"],
      "Pictures": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif", ".ttf", ".otf", ".woff", ".woff2", ".eot"],
      "Media": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
      "Others": []
    },
    "excluded_files": ["results.csv", "desktop.ini", "Thumbs.db", ".DS_Store"],
    "smart_rules": [
      {"pattern": "screenshot*", "category": "Pictures"},
      {"pattern": "Screen Shot*", "category": "Pictures"},
      {"pattern": "IMG_*", "category": "Pictures"},
      {"pattern": "DSC_*", "category": "Pictures"},
      {"pattern": "wallpaper*", "category": "Pictures"},
      {"pattern": "*setup*", "category": "Programs"},
      {"pattern": "*installer*", "category": "Programs"},
      {"pattern": "*portable*", "category": "Programs"}
    ]
  },
  "performance": {
    "max_file_size_for_sha1_mb": 500,
    "chunk_size_bytes": 32768
  },
  "logging": {
    "level": "WARNING",
    "file": null,
    "console": true
  }
}
```

### Project Structure
```
monitor.py            # CLI entry, monitoring orchestration
file_monitor.py       # Scanning, SHA1, CSV persistence, progress tracker
file_organizer.py     # File organization and empty-folder cleanup
config_manager.py     # Config defaults, validation, helpers
extensions.py         # Analytics extensions and duplicate detector
installed_cleaner.py  # Installer cleanup via registry matching
config.json           # User configuration
```

### Scheduling
- For always-on mode, use `python monitor.py -c 7200` in a long-running shell.

### Built-in Extensions
- File Type Analyzer
- File Size Analyzer
- Change Detector
- Duplicate Detector

### Code Quality
- Thread-safe singleton ConfigManager with proper locking
- Type hints throughout all modules
- Deep copy for nested configuration to prevent mutation
- Context managers for Windows registry access
- LRU cache for performance-critical string matching
- Platform safety checks for Windows-only modules
- Named constants instead of magic strings
- `__slots__` optimization for memory-efficient progress tracking
- Precompiled smart rules for O(1) pattern matching
- Single stat() call per file to avoid redundant I/O
- Streaming CSV write for reduced memory footprint
- `Counter` for efficient file type statistics
- Symlink exclusion to prevent unexpected file moves
- O(1) duplicate check using set for installer matching
- Extended installer format support (`.appx`, `.msix`, etc.)
- `hashlib.file_digest` for faster SHA1 on Python 3.11+
- `shutil.move` for cross-drive file organization safety
- Graceful shutdown with 1-second response for continuous monitoring
- File size persisted in CSV to avoid redundant stat() on reload
- Safe timestamp comparison to prevent `TypeError` on missing values

### Requirements
- Windows 10/11
- Python 3.8+ (standard library only; Python 3.11+ recommended for optimal SHA1 performance)

### License
MIT

---

<a name="中文"></a>

## 中文

仅限 Windows 的 Python 命令行工具，用于保持下载文件夹整洁：自动整理文件、跟踪哈希值、检测重复文件，并清理已安装软件的安装程序。无需任何第三方依赖。

### 功能特点
- 自动将文件整理到 Programs（程序）、Documents（文档）、Pictures（图片）、Media（媒体）、Others（其他）目录
- 智能文件名规则（如 `screenshot*`、`*setup*`）优先于扩展名匹配
- 增量扫描，使用 SHA1 缓存跳过未更改的文件
- 重复文件检测及文件类型/大小/变更分析
- 可选的安装程序清理（将 `Programs/` 中的安装程序与已安装软件进行匹配）
- 导出扫描结果为 CSV 文件，便于搜索和审计
- 零外部依赖，仅使用 Python 标准库

### 快速开始
```bash
# 单次运行（整理 + 可选的安装程序清理 + 扫描）
python monitor.py

# 详细输出
python monitor.py --log-level INFO

# 持续监控（默认 2 小时间隔）
python monitor.py -c
python monitor.py -c 3600   # 自定义间隔（秒）

# 显示系统信息
python monitor.py --info

# 重复文件清理建议
python monitor.py --cleanup

# 安装程序清理（预览模式 / 实际删除）
python monitor.py --clean-installers
python monitor.py --clean-installers --no-dry-run
```

### 命令行选项
| 选项 | 说明 |
|------|------|
| `-c, --continuous [秒数]` | 持续运行（默认 7200 秒） |
| `--no-ext` | 禁用扩展功能 |
| `--ext-only` | 仅对现有数据运行扩展 |
| `--cleanup` | 显示重复文件清理建议 |
| `--clean-installers` | 扫描 `Programs/` 中的安装程序与已安装软件 |
| `--no-dry-run` | 实际删除安装程序（与 `--clean-installers` 配合使用） |
| `--min-confidence 浮点数` | 安装程序匹配阈值（默认 0.7） |
| `--downloads-path 路径` | 指定下载文件夹路径 |
| `--csv-path 路径` | 指定 CSV 输出文件路径 |
| `--config 路径` | 使用不同的配置文件（默认 `config.json`） |
| `--log-level 级别` | DEBUG/INFO/WARNING/ERROR |
| `--log-file 路径` | 将日志写入文件 |
| `--info, -i` | 显示系统信息 |

### 配置文件 (config.json)
```json
{
  "downloads_path": null,
  "csv_path": "results.csv",
  "monitoring": {
    "interval_seconds": 7200,
    "enable_extensions": true,
    "calculate_sha1": true,
    "incremental_scan": true
  },
  "organization": {
    "auto_organize": true,
    "auto_clean_installers": true,
    "installer_min_confidence": 0.7,
    "categories": {
      "Programs": [".exe", ".msi", ".bat", ".cmd", ".ps1", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".torrent"],
      "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".md", ".csv", ".xls", ".xlsx", ".ppt", ".pptx", ".epub", ".mobi", ".azw", ".azw3", ".py", ".js", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".php", ".java", ".cpp", ".c", ".h"],
      "Pictures": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif", ".ttf", ".otf", ".woff", ".woff2", ".eot"],
      "Media": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
      "Others": []
    },
    "excluded_files": ["results.csv", "desktop.ini", "Thumbs.db", ".DS_Store"],
    "smart_rules": [
      {"pattern": "screenshot*", "category": "Pictures"},
      {"pattern": "Screen Shot*", "category": "Pictures"},
      {"pattern": "IMG_*", "category": "Pictures"},
      {"pattern": "DSC_*", "category": "Pictures"},
      {"pattern": "wallpaper*", "category": "Pictures"},
      {"pattern": "*setup*", "category": "Programs"},
      {"pattern": "*installer*", "category": "Programs"},
      {"pattern": "*portable*", "category": "Programs"}
    ]
  },
  "performance": {
    "max_file_size_for_sha1_mb": 500,
    "chunk_size_bytes": 32768
  },
  "logging": {
    "level": "WARNING",
    "file": null,
    "console": true
  }
}
```

### 项目结构
```
app.py                # 命令行入口，监控调度
file_monitor.py       # 扫描、SHA1 计算、CSV 持久化、进度追踪
file_organizer.py     # 文件整理和空文件夹清理
config_manager.py     # 配置默认值、验证、辅助函数
extensions.py         # 分析扩展和重复文件检测器
installed_cleaner.py  # 通过注册表匹配进行安装程序清理
config.json           # 用户配置文件
```

### 定时任务
- 如需持续运行，在长期运行的终端中使用 `python monitor.py -c 7200`。

### 内置扩展
- 文件类型分析器
- 文件大小分析器
- 变更检测器
- 重复文件检测器

### 代码质量
- 线程安全的单例 ConfigManager，使用适当的锁机制
- 所有模块均有类型提示
- 嵌套配置使用深拷贝以防止数据变更
- Windows 注册表访问使用上下文管理器
- 性能关键的字符串匹配使用 LRU 缓存
- Windows 专用模块的平台安全检查
- 使用命名常量代替魔法字符串
- 使用 `__slots__` 优化进度追踪器的内存占用
- 预编译智能规则实现 O(1) 模式匹配
- 单次 stat() 调用避免重复 I/O 操作
- CSV 流式写入减少内存占用
- 使用 `Counter` 高效统计文件类型
- 排除符号链接防止意外文件移动
- 使用集合实现 O(1) 安装程序重复检查
- 扩展安装程序格式支持（`.appx`、`.msix` 等）
- Python 3.11+ 使用 `hashlib.file_digest` 加速 SHA1 计算
- 使用 `shutil.move` 支持跨驱动器文件整理
- 持续监控支持秒级优雅停止响应
- CSV 持久化文件大小，避免重新加载时重复 stat()
- 安全的时间戳比较，防止缺失值导致 `TypeError`

### 系统要求
- Windows 10/11
- Python 3.8+（仅需标准库；推荐 Python 3.11+ 以获得最佳 SHA1 性能）

### 许可证
MIT
