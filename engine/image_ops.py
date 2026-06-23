"""Image analysis helpers shared by samplers and PFMs."""

from __future__ import annotations

import numpy as np
from PIL import Image


def luminance(img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    """Return (gray float32 0-1, alpha float32 0-1) from any PIL image."""
    gray = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
    if img.mode in ("RGBA", "LA"):
        alpha = np.asarray(img.split()[-1], dtype=np.float32) / 255.0
    else:
        alpha = np.ones_like(gray)
    return gray, alpha


def apply_brightness_contrast(gray: np.ndarray, brightness: float, contrast: float) -> np.ndarray:
    """Brightness/contrast around 0.5 mid-grey. 1.0 = identity for both."""
    out = (gray - 0.5) * float(contrast) + 0.5
    out = out * float(brightness)
    return np.clip(out, 0.0, 1.0)


def darkness(gray: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Density map: dark, opaque pixels are 'heavy'. Range 0-1."""
    return (1.0 - gray) * alpha


def canny(gray: np.ndarray, lo: float = 50.0, hi: float = 150.0) -> np.ndarray:
    """Canny edges as a float32 0/1 map. Uses OpenCV when available."""
    try:
        import cv2
        u8 = (np.clip(gray, 0, 1) * 255).astype(np.uint8)
        edges = cv2.Canny(u8, lo, hi)
        return (edges > 0).astype(np.float32)
    except Exception:
        from skimage.feature import canny as sk_canny
        return sk_canny(gray).astype(np.float32)


def sobel(gray: np.ndarray) -> np.ndarray:
    """Sobel gradient magnitude normalised to 0-1."""
    try:
        import cv2
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    except Exception:
        from scipy.ndimage import sobel as nd_sobel
        gx = nd_sobel(gray, axis=1)
        gy = nd_sobel(gray, axis=0)
    mag = np.hypot(gx, gy)
    m = mag.max()
    return (mag / m).astype(np.float32) if m > 0 else mag.astype(np.float32)
