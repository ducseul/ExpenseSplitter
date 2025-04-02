import os
import pickle
import time
import threading
import logging
from datetime import datetime


class BackupManager:
    def __init__(self, expense_manager, backup_file='backup.bak', interval_seconds=3600):
        self.expense_manager = expense_manager
        self.backup_file = backup_file
        self.interval_seconds = interval_seconds
        self.should_run = True
        self.backup_thread = None
        self.logger = logging.getLogger('backup_manager')

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def start(self):
        """Start the backup scheduler in a separate thread"""
        self.backup_thread = threading.Thread(target=self._backup_scheduler)
        self.backup_thread.daemon = True  # Thread will exit when main program exits
        self.backup_thread.start()
        self.logger.info(f"Backup scheduler started with {self.interval_seconds / 3600} hour interval")

    def stop(self):
        """Stop the backup scheduler"""
        self.should_run = False
        if self.backup_thread:
            self.backup_thread.join(timeout=1.0)
        self.logger.info("Backup scheduler stopped")

    def _backup_scheduler(self):
        """Run periodic backups at the specified interval"""
        while self.should_run:
            self.create_backup()
            # Sleep for the specified interval
            for _ in range(int(self.interval_seconds)):
                if not self.should_run:
                    break
                time.sleep(1)

    def create_backup(self):
        """Create a backup of all groups data"""
        try:
            groups_data = self.expense_manager.groups
            with open(self.backup_file, 'wb') as f:
                pickle.dump(groups_data, f)
            self.logger.info(f"Backup created successfully with {len(groups_data)} groups at {datetime.now()}")
            return True
        except Exception as e:
            self.logger.error(f"Backup creation failed: {str(e)}")
            return False

    def load_backup(self):
        """Load groups data from backup file if it exists"""
        if not os.path.exists(self.backup_file):
            self.logger.info("No backup file found")
            return False

        try:
            with open(self.backup_file, 'rb') as f:
                groups_data = pickle.load(f)

            # Restore the groups data to the expense manager
            self.expense_manager.groups = groups_data

            # Log the number of groups restored
            group_count = len(groups_data)
            self.logger.info(f"Successfully loaded {group_count} groups from backup")

            # Clean up any expired or inactive groups after loading
            self.expense_manager.clean_expired_groups()
            self.expense_manager.clean_inactive_groups()

            active_count = len(self.expense_manager.groups)
            if active_count < group_count:
                self.logger.info(f"Removed {group_count - active_count} expired/inactive groups after loading backup")

            return True
        except Exception as e:
            self.logger.error(f"Failed to load backup: {str(e)}")
            return False