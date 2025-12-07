"""
Pipeline Logger
Handles logging to console and file
"""

import logging
from datetime import datetime
from pathlib import Path
import sys

# Add parent to path for config
sys.path.insert(0, str(__file__).rsplit('\\', 2)[0])
from config import LOGS_DIR


class PipelineLogger:
    """Handles logging for the patent pipeline"""

    def __init__(self, name: str = "patent_pipeline"):
        self.name = name

        # Ensure logs directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        log_filename = f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_file = LOGS_DIR / log_filename

        # Setup logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers = []

        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        self.info(f"Log file: {self.log_file}")

    def info(self, message: str):
        self.logger.info(message)

    def debug(self, message: str):
        self.logger.debug(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def section(self, title: str):
        """Log a section header"""
        border = "=" * 60
        self.info(border)
        self.info(title)
        self.info(border)

    def summary(self, stats: dict):
        """Log a summary of statistics"""
        self.info("")
        self.info("SUMMARY:")
        for key, value in stats.items():
            self.info(f"  {key}: {value}")
        self.info("")

    def get_log_path(self) -> Path:
        """Return the current log file path"""
        return self.log_file
