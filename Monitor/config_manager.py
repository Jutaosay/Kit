#!/usr/bin/env python3
"""Configuration management for Downloads Monitor"""

import copy
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Dict, Any, Optional, List


__all__ = [
    "EXCLUDED_FILES",
    "ConfigManager",
    "get_config",
]

# Common excluded files across the application
EXCLUDED_FILES = frozenset(["results.csv", "desktop.ini", "Thumbs.db", ".DS_Store"])

# Windows Shell Folder registry constants
_SHELL_FOLDERS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
_DOWNLOADS_FOLDER_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"


class ConfigManager:
    """Manage application configuration"""

    DEFAULT_CONFIG = {
        "downloads_path": None,
        "csv_path": "results.csv",
        "monitoring": {
            "interval_seconds": 7200,
            "enable_extensions": True,
            "calculate_sha1": True,
            "incremental_scan": True
        },
        "organization": {
            "auto_organize": True,
            "auto_clean_installers": True,
            "installer_min_confidence": 0.7,
            "categories": {
                "Programs": [".exe", ".msi", ".bat", ".cmd", ".ps1", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".torrent"],
                "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".md", ".csv", ".xls", ".xlsx", ".ppt", ".pptx", ".epub", ".mobi", ".azw", ".azw3", ".py", ".js", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".php", ".java", ".cpp", ".c", ".h"],
                "Pictures": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif", ".ttf", ".otf", ".woff", ".woff2", ".eot"],
                "Media": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
                "Others": []
            },
            "excluded_files": list(EXCLUDED_FILES),
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
        "performance": {"max_file_size_for_sha1_mb": 500, "chunk_size_bytes": 32768},
        "logging": {"level": "INFO", "file": None, "console": True}
    }

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        config_path = Path(self.config_path)
        if config_path.exists():
            try:
                with config_path.open('r', encoding='utf-8') as f:
                    config = json.load(f)
                merged = self._merge_with_defaults(config)
                errors = self._validate_config(merged)
                if errors:
                    self.logger.warning("Configuration validation errors:")
                    for error in errors:
                        self.logger.warning(f"  - {error}")
                return merged
            except Exception as e:
                self.logger.warning(f"Failed to load config: {e}. Using defaults.")
                return copy.deepcopy(self.DEFAULT_CONFIG)
        else:
            self.save_config(self.DEFAULT_CONFIG)
            return copy.deepcopy(self.DEFAULT_CONFIG)

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        def merge(default: Dict, custom: Dict) -> Dict:
            result = copy.deepcopy(default)
            for key, value in custom.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge(result[key], value)
                else:
                    result[key] = value
            return result
        return merge(self.DEFAULT_CONFIG, config)

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        try:
            with Path(self.config_path).open('w', encoding='utf-8') as f:
                json.dump(config or self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, key_path: str, value: Any) -> None:
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value

    def get_downloads_path(self) -> str:
        """Get the Downloads folder path from config or Windows registry."""
        config_path = self.get("downloads_path")
        if config_path and Path(config_path).exists():
            return config_path
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _SHELL_FOLDERS_KEY) as key:
                downloads_path, _ = winreg.QueryValueEx(key, _DOWNLOADS_FOLDER_GUID)
            return downloads_path
        except (ImportError, FileNotFoundError, OSError):
            return str(Path.home() / "Downloads")

    def get_csv_path(self) -> str:
        csv_path = Path(self.get("csv_path", "results.csv"))
        return str(csv_path) if csv_path.is_absolute() else str(Path(self.get_downloads_path()) / csv_path)

    def get_excluded_files(self) -> List[str]:
        """Get list of excluded filenames."""
        return self.get("organization.excluded_files", [])

    def get_categories(self) -> Dict[str, List[str]]:
        """Get file extension categories for organization."""
        return self.get("organization.categories", {})

    def get_smart_rules(self) -> List[Dict[str, str]]:
        """Get smart rules for pattern-based file classification."""
        return self.get("organization.smart_rules", [])

    def _validate_config(self, config: Dict[str, Any]) -> List[str]:
        errors = []
        try:
            # 验证分类配置
            categories = config.get("organization", {}).get("categories", {})
            if categories:
                extension_count = {}
                for category, extensions in categories.items():
                    if not isinstance(extensions, list):
                        errors.append(f"Category '{category}' extensions must be a list")
                        continue
                    for ext in extensions:
                        if not isinstance(ext, str) or not ext.startswith('.'):
                            errors.append(f"Invalid extension '{ext}' in category '{category}'")
                        elif ext in extension_count:
                            errors.append(f"Duplicate extension '{ext}' in categories '{extension_count[ext]}' and '{category}'")
                        else:
                            extension_count[ext] = category
            
            # 验证性能配置
            perf = config.get("performance", {})
            max_size = perf.get("max_file_size_for_sha1_mb", 500)
            if not isinstance(max_size, (int, float)) or max_size < 1:
                errors.append("max_file_size_for_sha1_mb must be a number >= 1")
            
            chunk_size = perf.get("chunk_size_bytes", 32768)
            if not isinstance(chunk_size, int) or chunk_size < 1024:
                errors.append("chunk_size_bytes must be an integer >= 1024")
            
            # 验证监控配置
            monitoring = config.get("monitoring", {})
            interval = monitoring.get("interval_seconds", 7200)
            if not isinstance(interval, (int, float)) or interval < 60:
                errors.append("interval_seconds must be a number >= 60 (1 minute)")
            elif interval < 3600:  # Less than 1 hour
                errors.append("Warning: interval_seconds < 3600 (1 hour) may cause excessive resource usage for background monitoring")
            elif interval > 18000:  # More than 5 hours
                errors.append("Warning: interval_seconds > 18000 (5 hours) may be too infrequent for effective monitoring")
            
            # 验证路径配置
            downloads_path = config.get("downloads_path")
            if downloads_path:
                if not isinstance(downloads_path, str):
                    errors.append("downloads_path must be a string")
                elif not Path(downloads_path).exists():
                    errors.append(f"downloads_path does not exist: {downloads_path}")
                elif not Path(downloads_path).is_dir():
                    errors.append(f"downloads_path is not a directory: {downloads_path}")
            
            # 验证日志配置
            logging_config = config.get("logging", {})
            log_level = logging_config.get("level", "INFO")
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if log_level not in valid_levels:
                errors.append(f"Invalid log level '{log_level}'. Must be one of: {valid_levels}")
                
        except Exception as e:
            errors.append(f"Validation error: {e}")
        return errors


_config_lock = Lock()
_config_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global ConfigManager instance (thread-safe singleton)."""
    global _config_instance
    if _config_instance is None:
        with _config_lock:
            if _config_instance is None:
                _config_instance = ConfigManager()
    return _config_instance
