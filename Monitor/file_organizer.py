#!/usr/bin/env python3
"""File organizer module for Windows Downloads folder"""

import fnmatch
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config_manager import EXCLUDED_FILES


__all__ = [
    "FileOrganizer",
    "organize_downloads_folder",
]


class FileOrganizer:
    """Organize files in Downloads folder into categorized subdirectories."""

    DEFAULT_EXCLUDED = EXCLUDED_FILES

    def __init__(self, downloads_path: str, category_folders: Optional[Dict[str, List[str]]] = None,
                 excluded_files: Optional[List[str]] = None, smart_rules: Optional[List[Dict[str, str]]] = None):
        self.downloads_path = Path(downloads_path)
        self._downloads_root = self.downloads_path.resolve()
        self.logger = logging.getLogger(__name__)
        
        # 使用配置管理器获取默认分类，避免重复定义
        if category_folders is None:
            from config_manager import get_config
            category_folders = get_config().get_categories()
        
        self.category_folders = category_folders
        self.excluded_files = set(excluded_files or self.DEFAULT_EXCLUDED)  # 使用集合提高查找性能
        self.smart_rules = smart_rules or []
        
        # Precompile smart rules - convert patterns to lowercase once
        self._compiled_rules: List[Tuple[str, str]] = [
            (rule.get("pattern", "").lower(), rule.get("category", ""))
            for rule in self.smart_rules
            if rule.get("pattern") and rule.get("category") in (category_folders or {})
        ]
        
        # Build extension to category mapping with performance optimization
        self._ext_to_category = {}
        for category, extensions in self.category_folders.items():
            for ext in extensions:
                self._ext_to_category[ext.lower()] = category  # 预先转换为小写
    
    def _match_smart_rules(self, filename: str) -> Optional[str]:
        """Match filename against precompiled smart rules (pattern-based classification)"""
        filename_lower = filename.lower()
        for pattern, category in self._compiled_rules:
            if fnmatch.fnmatch(filename_lower, pattern):
                self.logger.debug(f"Smart rule matched: '{filename}' -> {category} (pattern: {pattern})")
                return category
        return None

    def _is_within_root(self, target: Path) -> bool:
        """Compatibility wrapper for Path.is_relative_to for Python 3.8+"""
        try:
            return target.resolve().is_relative_to(self._downloads_root)
        except AttributeError:
            try:
                target.resolve().relative_to(self._downloads_root)
                return True
            except ValueError:
                return False

    def organize_files(self, dry_run: bool = False) -> Dict[str, int]:
        self.logger.info("Starting file organization...")
        stats = {"total_files": 0, "organized": 0, "skipped": 0, "errors": 0}
        
        if not dry_run:
            for folder_name in self.category_folders:
                folder_path = self.downloads_path / folder_name
                if not folder_path.exists():
                    try:
                        folder_path.mkdir(parents=True, exist_ok=True)
                        self.logger.info(f"Created folder: {folder_name}")
                    except Exception as e:
                        self.logger.error(f"Failed to create folder {folder_name}: {e}")
        
        try:
            # 优化文件过滤逻辑，使用集合查找
            files_to_organize = []
            for f in self.downloads_path.iterdir():
                if f.is_file() and not f.is_symlink() and f.name not in self.excluded_files:
                    files_to_organize.append(f)
        except PermissionError:
            self.logger.error(f"Permission denied accessing: {self.downloads_path}")
            return stats
        except OSError as e:
            self.logger.error(f"OS error accessing {self.downloads_path}: {e}")
            return stats
        
        stats["total_files"] = len(files_to_organize)
        
        if not files_to_organize:
            self.logger.info("No files to organize in root directory")
            return stats
        
        self.logger.info(f"Found {len(files_to_organize)} files to organize")
        
        for source_path in files_to_organize:
            # 优先使用智能规则匹配，其次使用扩展名匹配，最后使用"Others"兜底
            category = (self._match_smart_rules(source_path.name) or 
                       self._ext_to_category.get(source_path.suffix.lower()) or
                       "Others")
            
            # 如果配置中没有"Others"分类，则跳过未分类文件
            if category == "Others" and "Others" not in self.category_folders:
                self.logger.debug(f"No category for '{source_path.name}' - leaving in root")
                stats["skipped"] += 1
                continue
            
            if category:
                dest_folder = self.downloads_path / category
                
                # Security check
                if not self._is_within_root(dest_folder):
                    self.logger.error(f"Destination outside downloads path. Skipping '{source_path.name}'.")
                    stats["errors"] += 1
                    continue

                dest_path = dest_folder / source_path.name
                
                # Handle filename conflicts
                if dest_path.exists():
                    counter = 1
                    while dest_path.exists():
                        dest_path = dest_folder / f"{source_path.stem}_{counter}{source_path.suffix}"
                        counter += 1
                
                if dry_run:
                    self.logger.info(f"[DRY RUN] Would move '{source_path.name}' to '{category}/'")
                    stats["organized"] += 1
                else:
                    try:
                        shutil.move(str(source_path), str(dest_path))
                        self.logger.info(f"Moved '{source_path.name}' to '{category}/'")
                        stats["organized"] += 1
                    except PermissionError:
                        self.logger.error(f"Permission denied moving '{source_path.name}'")
                        stats["errors"] += 1
                    except Exception as e:
                        self.logger.error(f"Error moving '{source_path.name}': {e}")
                        stats["errors"] += 1
        
        self.logger.info(f"Organization completed: {stats['organized']} organized, {stats['skipped']} skipped, {stats['errors']} errors")
        
        # Clean up extra empty folders
        if not dry_run:
            self._cleanup_extra_folders()
        
        return stats
    
    def _cleanup_extra_folders(self) -> None:
        """Remove empty folders that are not in the category list"""
        valid_folders = set(self.category_folders.keys())
        
        try:
            for item in self.downloads_path.iterdir():
                if not item.is_dir():
                    continue
                
                # Skip valid category folders
                if item.name in valid_folders:
                    continue
                
                # Check if folder is empty
                try:
                    contents = list(item.iterdir())
                    if not contents:
                        item.rmdir()
                        self.logger.info(f"Removed empty folder: {item.name}")
                    else:
                        self.logger.debug(f"Skipped non-empty folder: {item.name} ({len(contents)} items)")
                except PermissionError:
                    self.logger.warning(f"Permission denied accessing folder: {item.name}")
                except OSError as e:
                    self.logger.warning(f"Error checking folder {item.name}: {e}")
        except Exception as e:
            self.logger.warning(f"Error during folder cleanup: {e}")


def organize_downloads_folder(downloads_path: str, category_folders: Optional[Dict[str, List[str]]] = None,
                              excluded_files: Optional[List[str]] = None, smart_rules: Optional[List[Dict[str, str]]] = None,
                              dry_run: bool = False) -> Dict[str, int]:
    organizer = FileOrganizer(downloads_path, category_folders, excluded_files, smart_rules)
    return organizer.organize_files(dry_run=dry_run)
