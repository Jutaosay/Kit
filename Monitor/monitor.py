#!/usr/bin/env python3
"""Downloads folder monitoring main program - Windows-only CLI version"""

import time
import argparse
import logging
from pathlib import Path

from file_monitor import scan_downloads_folder, load_from_csv, update_csv_data, save_to_csv, get_system_info
from file_organizer import organize_downloads_folder
from config_manager import get_config, ConfigManager

# Optional module imports with graceful fallback
try:
    from extensions import create_extension_manager
    EXTENSIONS_AVAILABLE = True
except ImportError:
    EXTENSIONS_AVAILABLE = False

try:
    from installed_cleaner import create_installer_cleaner
    CLEANER_AVAILABLE = True
except ImportError:
    CLEANER_AVAILABLE = False


__all__ = [
    "DownloadsMonitor",
    "ContinuousMonitor",
    "main",
]


def format_interval(seconds: int) -> str:
    """Format interval seconds into human-readable string.
    
    Args:
        seconds: Number of seconds to format
        
    Returns:
        Human-readable string like "30s", "5m", "2h", or "2h30m"
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    else:
        hours, mins = seconds // 3600, (seconds % 3600) // 60
        return f"{hours}h" if mins == 0 else f"{hours}h{mins}m"


def setup_logging(config: ConfigManager) -> logging.Logger:
    """Configure application logging based on config settings.
    
    Args:
        config: ConfigManager instance with logging settings
        
    Returns:
        Configured root logger
    """
    log_level = config.get("logging.level", "INFO")
    log_file = config.get("logging.file")
    console_enabled = config.get("logging.console", True)
    
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.handlers.clear()
    
    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(console_handler)
    
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Failed to create log file: {e}")
    
    return logger


class DownloadsMonitor:
    """Main monitoring class for Downloads folder"""
    
    def __init__(self, config: ConfigManager = None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        self.downloads_path = self.config.get_downloads_path()
        self.csv_path = self.config.get_csv_path()
        self.existing_data = []
        self.new_data = []
        self.updated_data = []
        self.enable_extensions = self.config.get("monitoring.enable_extensions", True) and EXTENSIONS_AVAILABLE
        self.extension_manager = None
        
        if self.enable_extensions:
            try:
                self.extension_manager = create_extension_manager()
                self.logger.info("Extensions loaded successfully")
            except Exception as e:
                self.logger.warning(f"Failed to load extensions: {e}")
                self.enable_extensions = False

    def initialize(self) -> bool:
        self.logger.info("Initializing Downloads folder monitor...")
        self._display_system_info()
        
        if not Path(self.downloads_path).exists():
            self.logger.error(f"Downloads folder doesn't exist: {self.downloads_path}")
            return False
        
        self.logger.info(f"Monitoring path: {self.downloads_path}")
        self.existing_data = load_from_csv(self.csv_path)
        self.logger.info(f"Existing records: {len(self.existing_data)}")
        return True
    
    def _display_system_info(self) -> None:
        self.logger.info("=== System Information ===")
        for key, value in get_system_info().items():
            self.logger.info(f"{key}: {value}")
        self.logger.info(f"Extensions enabled: {self.enable_extensions}")
    
    def scan_folder(self) -> bool:
        self.logger.info("Scanning Downloads folder...")
        incremental = self.config.get("monitoring.incremental_scan", True)
        self.new_data = scan_downloads_folder(
            downloads_path=self.downloads_path,
            excluded_files=self.config.get_excluded_files(),
            category_folders=list(self.config.get_categories().keys()),
            calculate_sha1_enabled=self.config.get("monitoring.calculate_sha1", True),
            max_file_size_mb=self.config.get("performance.max_file_size_for_sha1_mb", 500),
            show_progress=self.logger.isEnabledFor(logging.INFO),
            existing_data=self.existing_data if incremental else None,
            incremental=incremental
        )
        self.logger.info(f"Files scanned: {len(self.new_data)}")
        return bool(self.new_data)
    
    def update_and_save(self) -> bool:
        self.logger.info("Updating data...")
        self.updated_data = update_csv_data(self.existing_data, self.new_data, self.config.get_excluded_files())
        self.logger.info(f"Updated records: {len(self.updated_data)}")
        self.logger.info("Saving data to CSV...")
        return save_to_csv(self.updated_data, self.csv_path)
    
    def run_extensions(self) -> None:
        if not self.enable_extensions or not self.extension_manager:
            return
        self.logger.info("Running extensions...")
        try:
            self.extension_manager.run_all_extensions(self.updated_data, self.existing_data)
            self.extension_manager.display_all_results()
        except Exception as e:
            self.logger.error(f"Error running extensions: {e}")
    
    def display_statistics(self) -> None:
        self.logger.info("=== Statistics ===")
        self.logger.info(f"Downloads path: {self.downloads_path}")
        self.logger.info(f"Total files: {len(self.updated_data)}")
        
        folder_stats = {}
        for item in self.updated_data:
            folder = item["folder_name"] if item["folder_name"] else "Root Directory"
            folder_stats[folder] = folder_stats.get(folder, 0) + 1
        
        self.logger.info("By folder distribution:")
        for folder, count in sorted(folder_stats.items()):
            self.logger.info(f"  {folder}: {count} files")
    
    def run_monitoring_cycle(self) -> bool:
        self.logger.info("Starting Downloads folder monitoring...")
        
        if not self.initialize():
            return False
        
        if self.config.get("organization.auto_organize", True):
            self.logger.info("=== File Organization Phase ===")
            stats = organize_downloads_folder(
                self.downloads_path,
                category_folders=self.config.get_categories(),
                excluded_files=self.config.get_excluded_files(),
                smart_rules=self.config.get_smart_rules()
            )
            self.logger.info(f"Organization stats: {stats}")
        
        # Auto cleanup installed installers
        if self.config.get("organization.auto_clean_installers", True) and CLEANER_AVAILABLE:
            self._run_installer_cleanup()
        
        if not self.scan_folder():
            self.logger.warning("No files scanned")
            return False
        
        if not self.update_and_save():
            return False
        
        self.run_extensions()
        self.display_statistics()
        self.logger.info("Monitoring completed!")
        return True
    
    def _run_installer_cleanup(self) -> None:
        """Auto cleanup installers for installed software"""
        programs_path = Path(self.downloads_path) / "Programs"
        if not programs_path.exists():
            return
        
        try:
            cleaner = create_installer_cleaner(str(programs_path))
            cleaner.scan_and_match()
            
            if cleaner.matches:
                self.logger.info("=== Installer Cleanup Phase ===")
                min_confidence = self.config.get("organization.installer_min_confidence", 0.7)
                stats = cleaner.cleanup(min_confidence=min_confidence, dry_run=False)
                self.logger.info(f"Cleaned {stats['deleted']} installers, freed {stats['freed_bytes'] / 1024 / 1024:.1f} MB")
        except Exception as e:
            self.logger.warning(f"Installer cleanup failed: {e}")


class ContinuousMonitor:
    """Continuous monitoring implementation"""
    
    def __init__(self, monitor: DownloadsMonitor, interval: int):
        self.monitor = monitor
        self.interval = interval
        self.logger = logging.getLogger(__name__)
        self.is_running = False
    
    def start(self) -> None:
        self.is_running = True
        self.logger.info(f"Starting continuous monitoring (interval: {format_interval(self.interval)})")
        
        try:
            while self.is_running:
                self.logger.info("Running monitoring cycle...")
                if not self.monitor.run_monitoring_cycle():
                    self.logger.warning("Monitoring cycle failed, continuing...")
                self.logger.info(f"Waiting {format_interval(self.interval)} until next cycle...")
                # Sleep in small increments for responsive shutdown
                for _ in range(self.interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Continuous monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"Error in continuous monitoring: {e}")
        finally:
            self.is_running = False


def show_system_info() -> None:
    """Display system information to console."""
    print("=== System Information ===")
    for key, value in get_system_info().items():
        print(f"{key}: {value}")


def show_cleanup_suggestions(config: ConfigManager) -> bool:
    logger = logging.getLogger(__name__)
    logger.info("Analyzing files for cleanup suggestions...")
    
    if not EXTENSIONS_AVAILABLE:
        logger.error("Extensions module not available")
        return False
    
    existing_data = load_from_csv(config.get_csv_path())
    if not existing_data:
        logger.error("No existing data found. Run monitoring first.")
        return False
    
    try:
        manager = create_extension_manager()
        duplicates = manager.duplicate_detector.find_duplicates(existing_data)
        
        if not duplicates:
            logger.info("No duplicate files found. Your Downloads folder is clean!")
            return True
        
        manager.duplicate_detector.display_duplicates()
        suggestions = manager.duplicate_detector.suggest_cleanup()
        
        logger.info("=== Cleanup Suggestions ===")
        delete_count = sum(1 for s in suggestions if s["action"] == "delete")
        keep_count = sum(1 for s in suggestions if s["action"] == "keep")
        
        logger.info(f"Files to keep: {keep_count}, Files to delete: {delete_count}")
        
        if delete_count > 0:
            logger.info("Files suggested for deletion:")
            for s in suggestions:
                if s["action"] == "delete":
                    f = s["file"]
                    logger.info(f"  {f.get('folder_name', '~')}/{f.get('filename', 'unknown')} - {s['reason']}")
        return True
    except Exception as e:
        logger.error(f"Error analyzing cleanup suggestions: {e}")
        return False


def run_extensions_only(config: ConfigManager) -> bool:
    logger = logging.getLogger(__name__)
    
    if not EXTENSIONS_AVAILABLE:
        logger.error("Extensions module not available")
        return False
    
    logger.info("Running extensions on existing data...")
    existing_data = load_from_csv(config.get_csv_path())
    
    if not existing_data:
        logger.error("No existing data found. Run monitoring first.")
        return False
    
    try:
        manager = create_extension_manager()
        manager.run_all_extensions(existing_data)
        manager.display_all_results()
        return True
    except Exception as e:
        logger.error(f"Error running extensions: {e}")
        return False


def clean_installed_installers(config: ConfigManager, dry_run: bool = True, min_confidence: float = 0.7) -> bool:
    """Clean up installers for already installed software"""
    logger = logging.getLogger(__name__)
    
    if not CLEANER_AVAILABLE:
        logger.error("Installer cleaner module not available")
        return False
    
    downloads_path = config.get_downloads_path()
    programs_path = Path(downloads_path) / "Programs"
    
    if not programs_path.exists():
        logger.error(f"Programs folder not found: {programs_path}")
        logger.info("Run monitoring first to organize files into Programs folder")
        return False
    
    try:
        cleaner = create_installer_cleaner(str(programs_path))
        cleaner.scan_and_match()
        cleaner.display_matches()
        
        if cleaner.matches:
            stats = cleaner.cleanup(min_confidence=min_confidence, dry_run=dry_run)
            if not dry_run:
                logger.info(f"Cleanup completed: {stats['deleted']} files deleted, {stats['freed_bytes'] / 1024 / 1024:.1f} MB freed")
            else:
                logger.info(f"[DRY RUN] Would delete {stats['deleted']} files, freeing {stats['freed_bytes'] / 1024 / 1024:.1f} MB")
                logger.info("Use --clean-installers --no-dry-run to actually delete files")
        
        return True
    except Exception as e:
        logger.error(f"Error cleaning installers: {e}")
        return False


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Downloads folder monitoring tool - Windows-only version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                    # Execute monitoring once
  %(prog)s -c                 # Continuous monitoring, 2h interval  
  %(prog)s -c 3600            # Continuous monitoring, 1h interval
  %(prog)s --info             # Show system information
  %(prog)s --cleanup          # Show cleanup suggestions
  %(prog)s --clean-installers # Show installers that can be deleted (dry run)
  %(prog)s --clean-installers --no-dry-run  # Actually delete installers"""
    )
    
    parser.add_argument("-c", "--continuous", nargs="?", const=7200, type=int, metavar="SECONDS",
                        help="Enable continuous monitoring with optional interval (default: 7200s/2h)")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually perform deletions (use with --clean-installers)")
    parser.add_argument("--no-ext", action="store_true", help="Disable extensions")
    parser.add_argument("--ext-only", action="store_true", help="Run only extensions")
    parser.add_argument("--downloads-path", type=str, help="Override Downloads folder path")
    parser.add_argument("--csv-path", type=str, help="Override CSV output file path")
    parser.add_argument("--config", type=str, default="config.json", help="Path to configuration file")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set logging level")
    parser.add_argument("--log-file", type=str, help="Write logs to file")
    parser.add_argument("--info", "-i", action="store_true", help="Show system information")
    parser.add_argument("--cleanup", action="store_true", help="Show duplicate file cleanup suggestions")
    parser.add_argument("--clean-installers", action="store_true", 
                        help="Clean up installers for already installed software")
    parser.add_argument("--min-confidence", type=float, default=0.7, metavar="0.0-1.0",
                        help="Minimum confidence for installer matching (default: 0.7)")
    
    return parser


def main() -> int:
    parser = create_argument_parser()
    args = parser.parse_args()
    
    config = ConfigManager(args.config)
    
    if args.log_level:
        config.set("logging.level", args.log_level)
    if args.log_file:
        config.set("logging.file", args.log_file)
    if args.downloads_path:
        config.set("downloads_path", args.downloads_path)
    if args.csv_path:
        config.set("csv_path", args.csv_path)
    if args.no_ext:
        config.set("monitoring.enable_extensions", False)
    
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    try:
        if args.info:
            show_system_info()
            return 0
        elif args.ext_only:
            return 0 if run_extensions_only(config) else 1
        elif args.cleanup:
            return 0 if show_cleanup_suggestions(config) else 1
        elif args.clean_installers:
            dry_run = not args.no_dry_run
            return 0 if clean_installed_installers(config, dry_run=dry_run, min_confidence=args.min_confidence) else 1
        elif args.continuous is not None:
            logger.info(f"Starting continuous monitoring with {format_interval(args.continuous)} interval")
            monitor = DownloadsMonitor(config)
            ContinuousMonitor(monitor, args.continuous).start()
            return 0
        else:
            return 0 if DownloadsMonitor(config).run_monitoring_cycle() else 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    main()
