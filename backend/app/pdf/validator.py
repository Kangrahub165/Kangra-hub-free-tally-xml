import os
from typing import Tuple, Optional
from pypdf import PdfReader
from app.core.config import settings
from app.core.exceptions import InvalidPDFException, PasswordProtectedPDFException

def validate_pdf_file(file_path: str, password: Optional[str] = None) -> Tuple[int, bool]:
    """
    Validates that the file:
    1. Exists and is non-empty
    2. Does not exceed max_upload_size_mb
    3. Has valid PDF magic bytes (%PDF-)
    4. Can be parsed by PdfReader
    5. Detects encryption and tests password if provided
    6. Returns (page_count, is_encrypted)
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise InvalidPDFException("The uploaded file is empty or could not be read.")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > settings.max_upload_size_mb:
        raise InvalidPDFException(
            f"File size ({file_size_mb:.1f} MB) exceeds maximum allowed size of {settings.max_upload_size_mb} MB."
        )

    # Magic byte check
    with open(file_path, "rb") as f:
        header = f.read(5)
        if not header.startswith(b"%PDF-"):
            raise InvalidPDFException("The uploaded file is not a valid PDF document.")

    try:
        reader = PdfReader(file_path)
        is_encrypted = reader.is_encrypted

        if is_encrypted:
            # Check if the document opens with an empty password (e.g. owner permission restriction only)
            empty_decrypt = reader.decrypt("")
            if empty_decrypt > 0:
                is_encrypted = False
            else:
                if not password:
                    raise PasswordProtectedPDFException()
                # Attempt decryption with provided password
                decrypt_result = reader.decrypt(password)
                if decrypt_result == 0:
                    raise InvalidPDFException("Incorrect PDF password. Please check the password and try again.")

        page_count = len(reader.pages)
        if page_count == 0:
            raise InvalidPDFException("The PDF statement contains no pages.")

        if page_count > settings.max_pages_per_file:
            raise InvalidPDFException(
                f"The PDF contains {page_count} pages, which exceeds the maximum limit of {settings.max_pages_per_file} pages."
            )

        return page_count, is_encrypted

    except (InvalidPDFException, PasswordProtectedPDFException):
        raise
    except Exception as e:
        raise InvalidPDFException(f"Failed to inspect PDF structure: {str(e)}")

def validate_image_file(file_path: str) -> Tuple[int, int]:
    """
    Validates uploaded JPG / JPEG statement file:
    1. Exists and is non-empty
    2. Does not exceed max_image_size_mb (10 MB)
    3. Valid image headers and readable by PIL
    4. Returns (width, height)
    """
    from PIL import Image

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise InvalidPDFException("The uploaded image file is empty or could not be read.")

    max_size_mb = getattr(settings, "max_image_size_mb", 10)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        raise InvalidPDFException(
            f"Image size ({file_size_mb:.1f} MB) exceeds maximum allowed size of {max_size_mb} MB."
        )

    try:
        with Image.open(file_path) as img:
            img.verify()
            width, height = img.size
            if width < 100 or height < 100:
                raise InvalidPDFException("The image resolution is too low to extract readable financial text.")
            return width, height
    except InvalidPDFException:
        raise
    except Exception as exc:
        raise InvalidPDFException(f"Invalid or corrupted JPG/JPEG image: {str(exc)}")

