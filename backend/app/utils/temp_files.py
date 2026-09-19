import os
import tempfile
import time
from contextlib import contextmanager
from typing import Generator
from app.core.config import settings
from app.utils.logger import app_logger

# Designated temp directory for conversion processing
TEMP_PROCESSING_DIR = os.path.join(tempfile.gettempdir(), "kangra_hub_tally")
os.makedirs(TEMP_PROCESSING_DIR, exist_ok=True)

@contextmanager
def temporary_upload_file(suffix: str = ".pdf") -> Generator[str, None, None]:
    """
    Creates a temporary file for PDF processing and guarantees immediate deletion
    in the finally block once extraction is complete.
    """
    fd, path = tempfile.mkstemp(suffix=suffix, dir=TEMP_PROCESSING_DIR)
    os.close(fd)
    try:
        yield path
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            app_logger.warning(f"Failed to remove temp file {path}: {e}")

def cleanup_old_temp_files(max_age_minutes: int = 60) -> int:
    """Cleans up any orphaned temp files older than max_age_minutes."""
    now = time.time()
    count = 0
    cutoff = now - (max_age_minutes * 60)
    try:
        for f in os.listdir(TEMP_PROCESSING_DIR):
            fpath = os.path.join(TEMP_PROCESSING_DIR, f)
            if os.path.isfile(fpath):
                if os.path.getmtime(fpath) < cutoff:
                    try:
                        os.remove(fpath)
                        count += 1
                    except Exception:
                        pass
    except Exception as e:
        app_logger.warning(f"Error during temp file cleanup: {e}")
    return count
