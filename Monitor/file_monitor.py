#!/usr/bin/env python3
"""File monitoring module for Windows Downloads folder"""

import csv
import hashlib
import logging
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional, List, Dict, Any

from config_manager import get_config, EXCLUDED_FILES

# Module-level logger for standalone functions
_logger = logging.getLogger(__name__)

# Use hashlib.file_digest for Python 3.11+ (C-level optimized)
_HAS_FILE_DIGEST = hasattr(hashlib, 'file_digest')


__all__ = [
    "SHA1_SKIPPED_TOO_LARGE",
    "format_size",
    "ProgressTracker",
    "calculate_sha1",
    "get_file_timestamp",
    "scan_downloads_folder",
    "update_csv_data",
    "save_to_csv",
    "load_from_csv",
    "get_system_info",
]

# SHA1 calculation status constants
SHA1_SKIPPED_TOO_LARGE = "SKIPPED_TOO_LARGE"

# ============== Shared Utilities ==============


def format_size(size: int) -> str:
    """Format file size to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class ProgressTracker:
    """Simple progress tracker with console output"""
    
    __slots__ = ('total', 'current', 'description', 'start_time', 'last_update', 'lock', 'logger', 'show_progress')
    
    def __init__(self, total: int, description: str = "Processing"):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
        self.last_update = 0
        self.lock = Lock()
        self.logger = logging.getLogger(__name__)
        self.show_progress = self.logger.isEnabledFor(logging.INFO)
    
    def update(self, increment: int = 1, item_name: Optional[str] = None) -> None:
        with self.lock:
            self.current += increment
            if not self.show_progress:
                return
            current_time = time.time()
            if current_time - self.last_update < 0.1 and self.current < self.total:
                return
            self.last_update = current_time
            self._display_progress(item_name)
    
    def _display_progress(self, item_name: Optional[str] = None) -> None:
        if self.total == 0:
            return
        percentage = (self.current / self.total) * 100
        elapsed = time.time() - self.start_time
        
        if self.current > 0 and elapsed > 0:
            eta = (self.total - self.current) / (self.current / elapsed)
            eta_str = f"ETA: {eta:.1f}s" if eta < 3600 else f"ETA: {eta/3600:.1f}h"
        else:
            eta_str = "ETA: --"
        
        bar_length = 30
        filled = min(bar_length, int(bar_length * self.current // self.total))
        bar = '█' * filled + '░' * (bar_length - filled)
        
        if item_name and len(item_name) > 20:
            item_name = item_name[:17] + "..."
        item_str = f" | {item_name}" if item_name else ""
        
        line = f"\r{self.description}: [{bar}] {percentage:.1f}% ({self.current}/{self.total}) | {eta_str}{item_str}"
        print(line[:120] + "..." if len(line) > 120 else line, end='', flush=True)
        if self.current >= self.total:
            print()
    
    def finish(self, message: Optional[str] = None) -> None:
        with self.lock:
            self.current = self.total
            if self.show_progress:
                self._display_progress()
                self.logger.info(message or f"Completed in {time.time() - self.start_time:.2f}s")


# ============== File Monitoring Functions ==============


def calculate_sha1(file_path: str, chunk_size: int = 8192, max_size_mb: Optional[int] = None) -> Optional[str]:
    """Calculate SHA1 hash value of a file with optimized performance."""
    path = Path(file_path)

    try:
        if not path.exists():
            return None

        # 优化：先获取文件大小，避免不必要的文件操作
        try:
            file_stat = path.stat()
            file_size = file_stat.st_size
        except (OSError, FileNotFoundError):
            return None
        
        # 提前检查文件大小限制
        if max_size_mb is not None and file_size > max_size_mb * 1024 * 1024:
            _logger.debug(f"Skipping SHA1 for large file: {file_path} ({file_size / 1024 / 1024:.1f} MB)")
            return SHA1_SKIPPED_TOO_LARGE

        # 空文件特殊处理
        if file_size == 0:
            return hashlib.sha1().hexdigest()

        # Python 3.11+ 使用 C 层面优化的 file_digest
        if _HAS_FILE_DIGEST:
            with path.open("rb") as f:
                return hashlib.file_digest(f, 'sha1').hexdigest()

        # 动态优化块大小
        if file_size > 100 * 1024 * 1024:  # > 100MB
            chunk_size = 131072  # 128KB
        elif file_size > 10 * 1024 * 1024:  # > 10MB
            chunk_size = 65536   # 64KB
        elif file_size > 1024 * 1024:       # > 1MB
            chunk_size = 32768   # 32KB
        else:
            chunk_size = 8192    # 8KB for small files

        sha1_hash = hashlib.sha1()
        with path.open("rb") as f:
            while chunk := f.read(chunk_size):
                sha1_hash.update(chunk)
        
        return sha1_hash.hexdigest()

    except PermissionError:
        _logger.warning(f"Permission denied: {file_path}")
        return None
    except (OSError, IOError) as e:
        _logger.error(f"IO error calculating SHA1 for {file_path}: {e}")
        return None
    except Exception as e:
        _logger.error(f"Unexpected error calculating SHA1 for {file_path}: {e}")
        return None


def get_file_timestamp(file_path: str) -> Optional[str]:
    """Get the last modification timestamp of a file in ISO8601 format."""
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        logging.getLogger(__name__).error(f"Error getting timestamp for {file_path}: {e}")
        return None


def scan_downloads_folder(downloads_path: Optional[str] = None, excluded_files: Optional[List[str]] = None,
                          category_folders: Optional[List[str]] = None, calculate_sha1_enabled: bool = True,
                          max_file_size_mb: Optional[int] = None, show_progress: bool = False,
                          existing_data: Optional[List[Dict[str, Any]]] = None, 
                          incremental: bool = False) -> List[Dict[str, Any]]:
    """Scan Downloads folder to get information about all files.
    
    Args:
        incremental: If True, only recalculate SHA1 for new/modified files
        existing_data: Previous scan data for incremental comparison
    """
    logger = logging.getLogger(__name__)

    if downloads_path is None:
        downloads_path = get_config().get_downloads_path()
    
    path = Path(downloads_path)
    if not path.exists():
        logger.error(f"Downloads folder doesn't exist: {path}")
        return []

    excluded_set = set(excluded_files) if excluded_files else EXCLUDED_FILES
    category_folders = category_folders or ["Programs", "Documents", "Pictures", "Media", "Others"]
    category_set = set(category_folders)

    # Build index from existing data for incremental scan
    existing_index: Dict[str, Dict[str, Any]] = {}
    if incremental and existing_data:
        for item in existing_data:
            rel_path = item.get("rel_path") or f"{item['folder_name']}/{item['filename']}"
            existing_index[rel_path] = item
        logger.info(f"Incremental scan enabled, {len(existing_index)} existing records indexed")

    files_info = []
    progress_tracker = None
    skipped_count = 0
    
    try:
        # 优化文件收集：使用 os.walk 并剪枝，避免过深目录
        all_files = []
        for root, dirs, files in os.walk(path):
            relative_root = Path(root).relative_to(path)
            if len(relative_root.parts) >= 2:
                dirs[:] = []
            
            for filename in files:
                if filename in excluded_set:
                    continue
                
                item_path = Path(root) / filename
                folder_name = relative_root.parts[0] if relative_root.parts and relative_root.parts[0] in category_set else '~'
                rel_path = str(item_path.relative_to(path)).replace("\\", "/")
                all_files.append((item_path, folder_name, rel_path))
        
        if show_progress and logger.isEnabledFor(logging.INFO):
            progress_tracker = ProgressTracker(len(all_files), "Scanning files")
        
        # Process files
        for item_path, folder_name, rel_path in all_files:
            try:
                file_key = rel_path
                # Single stat() call for both timestamp and file size
                try:
                    file_stat = item_path.stat()
                    file_size = file_stat.st_size
                    current_timestamp = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
                except OSError:
                    file_size = 0
                    current_timestamp = None
                
                # Incremental scan: reuse SHA1 if file unchanged
                sha1 = None
                if calculate_sha1_enabled:
                    if incremental and file_key in existing_index:
                        existing = existing_index[file_key]
                        # File unchanged if timestamp matches
                        if existing.get("timestamp") == current_timestamp and existing.get("sha1"):
                            sha1 = existing["sha1"]
                            skipped_count += 1
                        else:
                            sha1 = calculate_sha1(str(item_path), max_size_mb=max_file_size_mb)
                    else:
                        sha1 = calculate_sha1(str(item_path), max_size_mb=max_file_size_mb)
                
                files_info.append({
                    "root_dir": "~",
                    "folder_name": folder_name,
                    "filename": item_path.name,
                    "rel_path": rel_path,
                    "full_path": str(item_path),
                    "sha1": sha1,
                    "timestamp": current_timestamp,
                    "file_size": file_size,
                })
            except Exception as e:
                logger.error(f"Error creating file info for {item_path}: {e}")
            
            if progress_tracker:
                progress_tracker.update(1, item_path.name)
        
        if progress_tracker:
            progress_tracker.finish(f"Scanned {len(files_info)} files")

    except PermissionError:
        logger.error(f"Permission denied accessing: {path}")
        return []
    
    if incremental and skipped_count > 0:
        logger.info(f"Incremental scan: {skipped_count} unchanged files skipped SHA1 calculation")
    logger.info(f"Scanned {len(files_info)} files in {path}")
    return files_info


def update_csv_data(existing_data: List[Dict[str, Any]], new_data: List[Dict[str, Any]], 
                    excluded_files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Update CSV data with SHA1-based deduplication."""
    logger = logging.getLogger(__name__)
    excluded_set = set(excluded_files) if excluded_files else EXCLUDED_FILES
    
    def get_key(item):
        sha1 = item.get("sha1")
        if not sha1 or sha1 == SHA1_SKIPPED_TOO_LARGE:
            rel_path = item.get("rel_path")
            if rel_path:
                return f"PATH:{rel_path}"
            return f"PATH:{item['folder_name']}/{item['filename']}"
        return sha1
    
    # Build index from existing data
    sha1_index: Dict[str, List[Dict[str, Any]]] = {}
    for item in existing_data:
        if item["filename"] not in excluded_set:
            key = get_key(item)
            sha1_index.setdefault(key, []).append(item)
    
    # Process new data
    updated_data = []
    processed_keys = set()
    
    for new_item in new_data:
        if new_item["filename"] in excluded_set:
            continue
        
        key = get_key(new_item)
        if key in processed_keys:
            continue
        
        if key in sha1_index:
            # Keep most recent version
            most_recent = new_item
            for existing in sha1_index[key]:
                if (existing.get("timestamp") or "") > (most_recent.get("timestamp") or ""):
                    most_recent = existing
            updated_data.append(most_recent)
        else:
            updated_data.append(new_item)
        
        processed_keys.add(key)
    
    logger.info(f"Updated data: {len(updated_data)} unique files")
    return updated_data


def save_to_csv(data: List[Dict[str, Any]], csv_path: Optional[str] = None) -> bool:
    """Save data to CSV file."""
    logger = logging.getLogger(__name__)
    downloads_path = Path(get_config().get_downloads_path())

    if csv_path is None:
        csv_file = downloads_path / "results.csv"
    else:
        csv_file = Path(csv_path) if Path(csv_path).is_absolute() else downloads_path / csv_path

    try:
        with csv_file.open("w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["path", "rel_path", "folder_name", "filename", "sha1sum", "mtime_iso", "file_size"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Streaming write - write each row directly to avoid memory buildup
            for item in data:
                folder_name = item["folder_name"]
                filename = item['filename']
                timestamp = item.get('timestamp', '')
                
                if folder_name == "~":
                    path_str, rel_path = f"~\\{filename}", filename
                else:
                    path_str, rel_path = f"~\\{folder_name}\\{filename}", f"{folder_name}/{filename}"
                
                writer.writerow({
                    "path": path_str, "rel_path": rel_path, "folder_name": folder_name,
                    "filename": filename, "sha1sum": item.get("sha1", ""),
                    "mtime_iso": timestamp, "file_size": item.get("file_size", "")
                })
        
        logger.info(f"Data saved to {csv_file} ({len(data)} records)")
        return True
        
    except PermissionError:
        logger.error(f"Permission denied writing to: {csv_file}")
        return False
    except Exception as e:
        logger.error(f"Error saving CSV file: {e}")
        return False


def load_from_csv(csv_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load data from CSV file with backward compatibility."""
    logger = logging.getLogger(__name__)
    downloads_path = Path(get_config().get_downloads_path())

    csv_file = Path(csv_path) if csv_path else downloads_path / "results.csv"

    if not csv_file.exists():
        logger.info(f"CSV file not found: {csv_file}")
        return []

    data = []
    downloads_path_str = str(downloads_path)
    
    try:
        with csv_file.open("r", newline="", encoding="utf-8") as csvfile:
            for row in csv.DictReader(csvfile):
                if "folder_name" in row and "filename" in row:
                    folder_name, filename = row["folder_name"], row["filename"]
                    rel_path = row.get("rel_path", "")
                else:
                    # Legacy format
                    row_path = row["path"]
                    if row_path.startswith("~\\"):
                        parts = row_path[2:].split("\\")
                        folder_name = "~" if len(parts) == 1 else parts[0]
                        filename = parts[0] if len(parts) == 1 else parts[1]
                        rel_path = filename if folder_name == "~" else f"{folder_name}/{filename}"
                    else:
                        folder_name, filename, rel_path = "~", row_path, row_path

                full_path = f"{downloads_path_str}\\{filename}" if folder_name == "~" else f"{downloads_path_str}\\{folder_name}\\{filename}"
                
                # Parse file_size, supporting both new and legacy CSV formats
                file_size_raw = row.get("file_size", "")
                file_size = int(file_size_raw) if file_size_raw and file_size_raw.isdigit() else None

                data.append({
                    "root_dir": "~", "folder_name": folder_name, "filename": filename,
                    "full_path": full_path, "rel_path": rel_path,
                    "sha1": row.get("sha1sum", ""),
                    "timestamp": row.get("mtime_iso") or row.get("timestamp", ""),
                    "file_size": file_size,
                })
        
        logger.info(f"Loaded {len(data)} records from {csv_file}")
        
    except PermissionError:
        logger.error(f"Permission denied reading: {csv_file}")
    except Exception as e:
        logger.error(f"Error loading CSV file: {e}")
    
    return data


def get_system_info() -> Dict[str, Any]:
    """Get system information for debugging"""
    return {
        "platform": "Windows",
        "platform_version": platform.version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "downloads_path": get_config().get_downloads_path(),
    }
