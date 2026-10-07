import io
import math
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import cv2
import pypdfium2 as pdfium
import pdfplumber
from typing import List, Tuple, Optional

def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    """
    Applies image preprocessing tailored specifically for invoice documents:
    1. Auto-orient based on EXIF (if any)
    2. Resolution normalization (scaling up small images to min 1800px width/height)
    3. Grayscale conversion
    4. Deskew (detecting and correcting slight rotation angles)
    5. Adaptive contrast enhancement
    """
    # 1. EXIF auto-orientation
    img = ImageOps.exif_transpose(img)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')

    # 2. Resolution normalization
    w, h = img.size
    min_dim = min(w, h)
    if min_dim < 1500:
        scale_factor = 1800.0 / float(min_dim)
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Convert to OpenCV numpy array
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # 3. Grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    # 4. Deskew detection
    try:
        angle = detect_skew_angle(gray)
        if abs(angle) > 0.5 and abs(angle) < 45.0:
            gray = rotate_image(gray, -angle)
    except Exception:
        pass

    # 5. Mild contrast enhancement (CLAHE: Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    return Image.fromarray(enhanced)

def detect_skew_angle(gray_img: np.ndarray) -> float:
    """
    Calculates document skew angle using Hough line transform.
    Returns angle in degrees.
    """
    edges = cv2.Canny(gray_img, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return 0.0

    angles = []
    for line in lines[:50]:
        rho, theta = line[0]
        deg = (theta * 180.0 / np.pi) - 90.0
        if -45.0 < deg < 45.0:
            angles.append(deg)

    if not angles:
        return 0.0
    return float(np.median(angles))

def rotate_image(mat: np.ndarray, angle: float) -> np.ndarray:
    """Rotates an image matrix by the specified angle without clipping."""
    height, width = mat.shape[:2]
    image_center = (width / 2.0, height / 2.0)

    rotation_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    abs_cos = abs(rotation_mat[0, 0])
    abs_sin = abs(rotation_mat[0, 1])

    bound_w = int(height * abs_sin + width * abs_cos)
    bound_h = int(height * abs_cos + width * abs_sin)

    rotation_mat[0, 2] += bound_w / 2.0 - image_center[0]
    rotation_mat[1, 2] += bound_h / 2.0 - image_center[1]

    return cv2.warpAffine(mat, rotation_mat, (bound_w, bound_h), borderValue=(255, 255, 255))

def render_pdf_to_images(pdf_bytes: bytes, dpi: int = 300) -> List[Image.Image]:
    """
    Renders all pages of a PDF to high-resolution PIL images using pypdfium2.
    """
    pdf = pdfium.PdfDocument(pdf_bytes)
    images = []
    scale = dpi / 72.0
    for page in pdf:
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        images.append(pil_image)
    return images

def is_digital_pdf(pdf_bytes: bytes) -> Tuple[bool, List[str]]:
    """
    Determines whether a PDF is a digitally generated PDF (rich text extractable)
    or a scanned/image-based PDF.
    Returns (is_digital, page_texts).
    """
    page_texts = []
    total_text_length = 0
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            page_texts.append(t)
            total_text_length += len(t.strip())

    page_count = len(page_texts) if page_texts else 1
    avg_chars_per_page = total_text_length / float(page_count)
    # If average characters per page > 100 and keywords like Tax/Invoice/GST/Total appear
    is_digital = avg_chars_per_page >= 100
    return is_digital, page_texts
