import logging
import sys
import re

class SensitiveDataFilter(logging.Filter):
    """Filter to ensure passwords, auth tokens, and sensitive credentials are never logged."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            # Redact passwords/pins/tokens
            record.msg = re.sub(
                r'(password|passwd|token|secret|pin|authorization)[\s:=]+([^\s,]+)',
                r'\1=***REDACTED***',
                record.msg,
                flags=re.IGNORECASE
            )
            # Redact Bearer tokens
            record.msg = re.sub(
                r'(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*',
                r'\1***REDACTED***',
                record.msg,
                flags=re.IGNORECASE
            )
        return True

def setup_logger(name: str = "kangra_hub") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
    return logger

app_logger = setup_logger()
