#!/usr/bin/env python3
"""Extensions module for Downloads folder monitoring tool"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter

from file_monitor import format_size, SHA1_SKIPPED_TOO_LARGE


__all__ = [
    "FileTypeAnalyzer",
    "FileSizeAnalyzer",
    "ChangeDetector",
    "DuplicateDetector",
    "ExtensionManager",
    "create_extension_manager",
    "create_duplicate_detector",
]


class FileTypeAnalyzer:
    """Analyze file types in Downloads folder"""
    
    def __init__(self):
        self.file_types: Dict[str, int] = {}
        self.total_files: int = 0
        self.logger = logging.getLogger(__name__)
    
    def analyze_files(self, files_data: List[Dict[str, Any]]) -> None:
        self.total_files = len(files_data)
        extensions = (Path(f.get("filename", "")).suffix.lower() or "No Extension" 
                      for f in files_data if f.get("filename"))
        self.file_types = dict(Counter(extensions))
    
    def display_statistics(self) -> None:
        self.logger.info("=== File Type Analysis ===")
        self.logger.info(f"Total files: {self.total_files}, Unique extensions: {len(self.file_types)}")
        
        if self.file_types:
            self.logger.info("File type distribution:")
            sorted_types = sorted(self.file_types.items(), key=lambda x: x[1], reverse=True)
            for ext, count in sorted_types[:10]:
                percentage = (count / self.total_files) * 100
                self.logger.info(f"  {ext}: {count} files ({percentage:.1f}%)")


class FileSizeAnalyzer:
    """Analyze file sizes in Downloads folder"""
    
    SIZE_CATEGORIES = [
        ("Tiny (< 1KB)", 1024),
        ("Small (1KB - 1MB)", 1024 * 1024),
        ("Medium (1MB - 100MB)", 100 * 1024 * 1024),
        ("Large (100MB - 1GB)", 1024 * 1024 * 1024),
        ("Huge (> 1GB)", float('inf')),
    ]
    
    def __init__(self):
        self.size_counts: Dict[str, int] = {cat[0]: 0 for cat in self.SIZE_CATEGORIES}
        self.total_size: int = 0
        self.logger = logging.getLogger(__name__)

    def analyze_files(self, files_data: List[Dict[str, Any]]) -> None:
        for cat in self.size_counts:
            self.size_counts[cat] = 0
        self.total_size = 0

        for file_info in files_data:
            # Use cached file_size to avoid repeated stat calls
            file_size = file_info.get("file_size")
            if file_size is None:
                # Fallback for backward compatibility
                file_path = file_info.get("full_path")
                if not file_path:
                    continue
                try:
                    file_size = Path(file_path).stat().st_size
                except OSError:
                    continue
            
            self.total_size += file_size
            for cat_name, threshold in self.SIZE_CATEGORIES:
                if file_size < threshold:
                    self.size_counts[cat_name] += 1
                    break

    def display_statistics(self) -> None:
        self.logger.info("=== File Size Analysis ===")
        self.logger.info(f"Total size: {format_size(self.total_size)}, Total files: {sum(self.size_counts.values())}")
        self.logger.info("Size distribution:")
        for category, count in self.size_counts.items():
            if count > 0:
                self.logger.info(f"  {category}: {count} files")


class ChangeDetector:
    """Detect changes in Downloads folder"""
    
    def __init__(self):
        self.previous_data: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self.changes: Dict[str, List[Any]] = {"new_files": [], "modified_files": [], "deleted_files": []}
        self.logger = logging.getLogger(__name__)

    def set_previous_data(self, files_data: List[Dict[str, Any]]) -> None:
        # Use rel_path as unique key for simpler and more efficient lookup
        self.previous_data = {
            f.get("rel_path", f"{f['folder_name']}/{f['filename']}"): f for f in files_data
        }

    def detect_changes(self, current_data: List[Dict[str, Any]]) -> None:
        self.changes = {"new_files": [], "modified_files": [], "deleted_files": []}
        current_keys = set()

        for file_info in current_data:
            key = file_info.get("rel_path", f"{file_info['folder_name']}/{file_info['filename']}")
            current_keys.add(key)

            if key in self.previous_data:
                prev = self.previous_data[key]
                if file_info.get("sha1") != prev.get("sha1") or file_info.get("timestamp") != prev.get("timestamp"):
                    self.changes["modified_files"].append({"file": file_info, "previous": prev})
            else:
                self.changes["new_files"].append(file_info)

        for key in self.previous_data:
            if key not in current_keys:
                self.changes["deleted_files"].append(self.previous_data[key])

    def display_changes(self) -> None:
        new_count = len(self.changes["new_files"])
        mod_count = len(self.changes["modified_files"])
        del_count = len(self.changes["deleted_files"])
        total = new_count + mod_count + del_count
        
        self.logger.info("=== Change Detection ===")
        self.logger.info(f"New: {new_count}, Modified: {mod_count}, Deleted: {del_count}, Total: {total}")
        
        if total > 0:
            for label, key, prefix in [("New files:", "new_files", "+"), 
                                        ("Modified files:", "modified_files", "*"),
                                        ("Deleted files:", "deleted_files", "-")]:
                items = self.changes[key]
                if items:
                    self.logger.info(label)
                    for item in items[:5]:
                        f = item["file"] if isinstance(item, dict) and "file" in item else item
                        self.logger.info(f"  {prefix} {f['filename']}")


class DuplicateDetector:
    """Detect and manage duplicate files"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.duplicates: Dict[str, List[Dict[str, Any]]] = {}
        self.total_duplicates = 0
        self.wasted_space = 0
    
    def find_duplicates(self, files_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        self.duplicates.clear()
        self.total_duplicates = 0
        self.wasted_space = 0
        
        hash_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        valid_files = [f for f in files_data if f.get("sha1") and f["sha1"] != SHA1_SKIPPED_TOO_LARGE]
        
        for file_info in valid_files:
            hash_groups[file_info["sha1"]].append(file_info)
        
        for sha1, files in hash_groups.items():
            if len(files) > 1:
                self.duplicates[sha1] = files
                self.total_duplicates += len(files) - 1
                
                try:
                    # Use cached file_size to avoid repeated stat calls
                    file_size = files[0].get("file_size")
                    if file_size is None:
                        first_file_path = files[0].get("full_path")
                        if first_file_path and Path(first_file_path).exists():
                            file_size = Path(first_file_path).stat().st_size
                    if file_size:
                        self.wasted_space += file_size * (len(files) - 1)
                except (OSError, FileNotFoundError, TypeError):
                    pass
        
        return self.duplicates
    
    def display_duplicates(self, max_groups: int = 10) -> None:
        if not self.duplicates:
            self.logger.info("=== Duplicate Detection ===")
            self.logger.info("No duplicate files found")
            return
        
        self.logger.info("=== Duplicate Detection ===")
        self.logger.info(f"Duplicate groups: {len(self.duplicates)}, Total duplicates: {self.total_duplicates}")
        self.logger.info(f"Wasted space: {format_size(self.wasted_space)}")
        
        self.logger.info("Top duplicate groups:")
        sorted_groups = sorted(self.duplicates.items(), key=lambda x: len(x[1]), reverse=True)
        
        for i, (sha1, files) in enumerate(sorted_groups[:max_groups]):
            self.logger.info(f"  Group {i+1} ({len(files)} files):")
            for f in files:
                self.logger.info(f"    {f.get('folder_name', '~')}/{f.get('filename', 'unknown')}")
    
    def suggest_cleanup(self) -> List[Dict[str, Any]]:
        suggestions = []
        
        for sha1, files in self.duplicates.items():
            if len(files) <= 1:
                continue
            
            # Prefer keeping files in categorized folders (key=1) over root "~" (key=0);
            # reverse=True puts categorized files first, so they are chosen as the "keep" candidate
            sorted_files = sorted(files, key=lambda f: 0 if f.get("folder_name") == "~" else 1, reverse=True)
            
            suggestions.append({
                "action": "keep",
                "file": sorted_files[0],
                "reason": f"Best location: {sorted_files[0].get('folder_name', '~')}"
            })
            
            for f in sorted_files[1:]:
                suggestions.append({"action": "delete", "file": f, "reason": "Duplicate file"})
        
        return suggestions


class ExtensionManager:
    """Manager for all extensions"""

    def __init__(self):
        self.extensions = {
            "file_type_analyzer": FileTypeAnalyzer(),
            "file_size_analyzer": FileSizeAnalyzer(),
            "change_detector": ChangeDetector(),
        }
        self.duplicate_detector = DuplicateDetector()

    def run_all_extensions(self, files_data: List[Dict[str, Any]], previous_data: Optional[List[Dict[str, Any]]] = None) -> None:
        for name, ext in self.extensions.items():
            try:
                if hasattr(ext, "analyze_files"):
                    ext.analyze_files(files_data)
                if hasattr(ext, "set_previous_data") and previous_data:
                    ext.set_previous_data(previous_data)
                if hasattr(ext, "detect_changes"):
                    ext.detect_changes(files_data)
            except Exception as e:
                logging.getLogger(__name__).error(f"Error running extension {name}: {e}")
        
        # Run duplicate detection
        self.duplicate_detector.find_duplicates(files_data)

    def display_all_results(self) -> None:
        for ext in self.extensions.values():
            if hasattr(ext, "display_statistics"):
                ext.display_statistics()
            elif hasattr(ext, "display_changes"):
                ext.display_changes()
        
        # Display duplicate results
        self.duplicate_detector.display_duplicates()


def create_extension_manager() -> ExtensionManager:
    return ExtensionManager()


def create_duplicate_detector() -> DuplicateDetector:
    return DuplicateDetector()
