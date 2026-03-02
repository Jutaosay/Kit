#!/usr/bin/env python3
"""Installed software cleaner - Remove installers for already installed programs"""

import logging
import platform
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

# Windows-only module
if platform.system() != "Windows":
    raise ImportError("installed_cleaner module is only available on Windows")

import winreg

from file_monitor import format_size


__all__ = [
    "InstalledSoftwareDetector",
    "InstallerCleaner",
    "create_installer_cleaner",
]


class InstalledSoftwareDetector:
    """Detect installed software on Windows"""
    
    REGISTRY_PATHS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.installed_software: Dict[str, dict] = {}
        
    def scan_installed_software(self) -> Dict[str, dict]:
        """Scan Windows registry for installed software"""
        self.installed_software.clear()
        
        for hkey, path in self.REGISTRY_PATHS:
            try:
                self._scan_registry_key(hkey, path)
            except OSError as e:
                self.logger.debug(f"Could not access registry path {path}: {e}")
        
        self.logger.info(f"Found {len(self.installed_software)} installed programs")
        return self.installed_software
    
    def _scan_registry_key(self, hkey, path: str) -> None:
        """Scan a specific registry key for installed software"""
        try:
            with winreg.OpenKey(hkey, path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey_path = f"{path}\\{subkey_name}"
                        
                        try:
                            with winreg.OpenKey(hkey, subkey_path) as subkey:
                                software_info = self._get_software_info(subkey)
                                
                                if software_info and software_info.get("name"):
                                    name = software_info["name"]
                                    key_name = name.lower()
                                    if key_name not in self.installed_software:
                                        self.installed_software[key_name] = software_info
                        except (OSError, WindowsError):
                            pass
                        
                        i += 1
                    except OSError:
                        break
        except OSError:
            return
    
    def _get_software_info(self, key) -> Optional[dict]:
        """Extract software information from registry key"""
        info = {}
        
        try:
            info["name"] = winreg.QueryValueEx(key, "DisplayName")[0]
        except OSError:
            return None
        
        for field, reg_name in [("version", "DisplayVersion"), ("publisher", "Publisher")]:
            try:
                info[field] = winreg.QueryValueEx(key, reg_name)[0]
            except OSError:
                info[field] = ""
        
        return info
    
    def get_software_names(self) -> Set[str]:
        return set(self.installed_software.keys())


class InstallerCleaner:
    """Clean up installers for already installed software"""
    
    # Noise words to filter out when extracting core software names
    INSTALLER_NOISE_WORDS = frozenset({
        'setup', 'install', 'installer', 'update', 'updater',
        'x64', 'x86', 'win64', 'win32', 'win', 'windows',
        'portable', 'full', 'stable', 'overseas', 'global', 'latest',
        'x', 'exe', 'msi'
    })
    
    # Supported installer file extensions
    INSTALLER_EXTENSIONS = frozenset({'.exe', '.msi', '.appx', '.msix', '.appxbundle', '.msixbundle'})
    
    def __init__(self, programs_path: str):
        self.programs_path = Path(programs_path)
        self.logger = logging.getLogger(__name__)
        self.detector = InstalledSoftwareDetector()
        self.matches: List[Tuple[Path, str, float]] = []
        self.installer_table: Dict[Path, str] = {}
        self._matched_paths: Set[Path] = set()  # For O(1) duplicate check

    def scan_and_match(self) -> List[Tuple[Path, str, float]]:
        """Scan Programs folder, build installer table, then match against installed software"""
        self.matches.clear()
        self.installer_table.clear()
        self._matched_paths.clear()
        
        if not self.programs_path.exists():
            self.logger.warning(f"Programs folder not found: {self.programs_path}")
            return []
        
        self._build_installer_table()
        self.logger.info(f"Found {len(self.installer_table)} installer files")
        
        self.detector.scan_installed_software()
        
        for software_key, software_info in self.detector.installed_software.items():
            software_name = software_info.get("name", software_key)
            self._find_matching_installers(software_name)
        
        self.matches.sort(key=lambda x: x[2], reverse=True)
        return self.matches
    
    def _build_installer_table(self) -> None:
        """Build table of installer files with their extracted core names"""
        try:
            for file_path in self.programs_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.INSTALLER_EXTENSIONS:
                    core_name = self._extract_core_name(file_path.stem)
                    self.installer_table[file_path] = core_name
                    self.logger.debug(f"Installer: {file_path.name} -> core: '{core_name}'")
        except (OSError, PermissionError) as e:
            self.logger.error(f"Error scanning Programs folder: {e}")
    
    def _extract_core_name(self, filename: str) -> str:
        """Extract core software name from installer filename"""
        name = filename.lower()
        parts = re.split(r'[-_.\s]+', name)
        
        clean_parts = []
        for part in parts:
            if part in self.INSTALLER_NOISE_WORDS:
                continue
            if re.match(r'^v?\d+[\d.]*((build|beta|alpha|rc)\d*)?$', part):
                continue
            if len(part) >= 2:
                clean_parts.append(part)
        
        return ''.join(clean_parts)
    
    def _normalize_software_name(self, name: str) -> str:
        """Normalize installed software name for comparison"""
        name = name.lower()
        name = re.sub(r'\s*\(.*?\)\s*', '', name)
        name = re.sub(r'\s*-\s*.*$', '', name)
        name = re.sub(r'\s+v?\d+[\d.]*.*$', '', name)
        name = re.sub(r'[\s\-_\.\(\)\[\]]+', '', name)
        return name.strip()
    
    def _find_matching_installers(self, software_name: str) -> None:
        """Find installers that match this installed software"""
        software_normalized = self._normalize_software_name(software_name)
        if len(software_normalized) < 3:
            return
        
        software_keywords = self._extract_keywords(software_name)
        
        for file_path, core_name in self.installer_table.items():
            if file_path in self._matched_paths:
                continue
            
            confidence = self._calculate_similarity(core_name, software_normalized, software_keywords)
            
            if confidence >= 0.5:
                self.matches.append((file_path, software_name, confidence))
                self._matched_paths.add(file_path)
                self.logger.debug(f"Match: {file_path.name} <-> {software_name} ({confidence:.0%})")
    
    def _extract_keywords(self, software_name: str) -> Set[str]:
        """Extract meaningful keywords from software name"""
        words = re.split(r'[\s\-_\.\(\)\[\]]+', software_name.lower())
        noise = {'microsoft', 'x64', 'x86', 'user', 'runtime', 'additional', 'minimum'}
        keywords = {w for w in words if len(w) >= 4 and w not in noise}
        
        cap_words = re.findall(r'[A-Z][a-z]+', software_name)
        if len(cap_words) >= 2:
            acronym = ''.join(w[0].lower() for w in cap_words)
            if len(acronym) >= 2:
                keywords.add(acronym)
        
        return keywords

    def _calculate_similarity(self, installer_core: str, software_name: str, software_keywords: Set[str] = None) -> float:
        """Calculate similarity between installer core name and software name"""
        if not installer_core or not software_name:
            return 0.0
        
        if installer_core == software_name:
            return 0.98
        
        if len(installer_core) >= 4 and installer_core in software_name:
            return 0.95
        if len(software_name) >= 4 and software_name in installer_core:
            return 0.90
        
        if software_keywords:
            for keyword in software_keywords:
                if len(keyword) >= 2 and len(keyword) <= 4:
                    if installer_core.startswith(keyword) or keyword in installer_core:
                        return 0.85
                if len(keyword) >= 5:
                    if keyword in installer_core or installer_core in keyword:
                        return 0.85
                    lcs = self._longest_common_substring_length(installer_core, keyword)
                    if lcs >= 5 and lcs >= len(min(installer_core, keyword, key=len)) * 0.7:
                        return 0.75
        
        lcs_len = self._longest_common_substring_length(installer_core, software_name)
        shorter_len = min(len(installer_core), len(software_name))
        longer_len = max(len(installer_core), len(software_name))
        
        if lcs_len >= 5 and shorter_len >= 5:
            lcs_ratio = lcs_len / shorter_len
            coverage = lcs_len / longer_len
            if lcs_ratio >= 0.8 and coverage >= 0.4:
                return 0.5 + lcs_ratio * 0.4
        
        return 0.0
    
    @staticmethod
    @lru_cache(maxsize=256)
    def _longest_common_substring_length(s1: str, s2: str) -> int:
        """Find length of longest common substring"""
        if not s1 or not s2:
            return 0
        
        m, n = len(s1), len(s2)
        if m > n:
            s1, s2, m, n = s2, s1, n, m
        
        prev = [0] * (n + 1)
        curr = [0] * (n + 1)
        max_len = 0
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    curr[j] = prev[j-1] + 1
                    max_len = max(max_len, curr[j])
                else:
                    curr[j] = 0
            prev, curr = curr, prev
        
        return max_len
    
    def display_matches(self) -> None:
        """Display matched installers"""
        if not self.matches:
            self.logger.info("=== Installer Cleanup ===")
            self.logger.info("No installers found matching installed software")
            return
        
        self.logger.info("=== Installer Cleanup Suggestions ===")
        self.logger.info(f"Found {len(self.matches)} installers for already installed software:\n")
        
        total_size = 0
        for file_path, software_name, confidence in self.matches:
            try:
                size = file_path.stat().st_size
                total_size += size
                size_str = format_size(size)
            except OSError:
                size_str = "???"
            
            self.logger.info(f"  [{confidence*100:.0f}%] {file_path.name}")
            self.logger.info(f"         -> Installed: {software_name} ({size_str})")
        
        self.logger.info(f"\nTotal space that can be freed: {format_size(total_size)}")
    
    def cleanup(self, min_confidence: float = 0.5, dry_run: bool = True) -> Dict[str, int]:
        """Clean up matched installers"""
        stats = {"deleted": 0, "skipped": 0, "errors": 0, "freed_bytes": 0}
        
        if not self.matches:
            self.logger.info("No installers to clean up")
            return stats
        
        self.logger.info(f"{'[DRY RUN] ' if dry_run else ''}Cleaning up installers (min confidence: {min_confidence*100:.0f}%)...")
        
        for file_path, software_name, confidence in self.matches:
            if confidence < min_confidence:
                self.logger.debug(f"Skipping {file_path.name} (confidence {confidence*100:.0f}% < {min_confidence*100:.0f}%)")
                stats["skipped"] += 1
                continue
            
            try:
                size = file_path.stat().st_size
                
                if dry_run:
                    self.logger.info(f"[DRY RUN] Would delete: {file_path.name} ({format_size(size)})")
                else:
                    file_path.unlink()
                    self.logger.info(f"Deleted: {file_path.name} ({format_size(size)})")
                
                stats["deleted"] += 1
                stats["freed_bytes"] += size
                    
            except PermissionError:
                self.logger.error(f"Permission denied: {file_path.name}")
                stats["errors"] += 1
            except OSError as e:
                self.logger.error(f"Error deleting {file_path.name}: {e}")
                stats["errors"] += 1
        
        self.logger.info(f"Cleanup complete: {stats['deleted']} deleted, {stats['skipped']} skipped, {stats['errors']} errors")
        self.logger.info(f"Space freed: {format_size(stats['freed_bytes'])}")
        
        return stats


def create_installer_cleaner(programs_path: str) -> InstallerCleaner:
    """Factory function to create InstallerCleaner"""
    return InstallerCleaner(programs_path)
