# logger.py - TeleFrame Logging Configuration
"""
Centralized logging configuration for TeleFrame
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


def setup_logger(log_level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """Setup centralized logging for TeleFrame"""

    # Create main logger
    logger = logging.getLogger("teleframe")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            # Ensure log directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Rotating file handler (10MB max, 5 backup files)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_level.upper()))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.info(f"File logging enabled: {log_file}")

        except Exception as e:
            logger.error(f"Failed to setup file logging: {e}")

    # Suppress some noisy loggers
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger.info(f"Logging initialized - Level: {log_level}")
    return logger


# Security audit logger
def setup_security_logger(log_file: Path) -> logging.Logger:
    """Setup dedicated security event logger"""

    security_logger = logging.getLogger("teleframe.security")
    security_logger.setLevel(logging.INFO)
    security_logger.handlers.clear()

    # Security events always go to file
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        security_formatter = logging.Formatter(
            fmt='%(asctime)s - SECURITY - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        security_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=10,
            encoding='utf-8'
        )
        security_handler.setFormatter(security_formatter)
        security_logger.addHandler(security_handler)

        security_logger.info("Security logging initialized")

    except Exception as e:
        main_logger = logging.getLogger("teleframe")
        main_logger.error(f"Failed to setup security logging: {e}")

    return security_logger


if __name__ == "__main__":
    # Test logging
    logger = setup_logger("DEBUG", Path("test.log"))

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")

    # Test security logger
    sec_logger = setup_security_logger(Path("security.log"))
    sec_logger.info("Security event test")
