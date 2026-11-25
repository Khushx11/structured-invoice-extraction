"""Image preprocessing that preserves the displayed page coordinate frame."""
from PIL import ImageFilter, ImageOps


def enhance_scan(image):
    grey = ImageOps.grayscale(image)
    # Leave almost-flat pages alone. Amplifying blank-page noise creates false OCR.
    if grey.getextrema()[1] - grey.getextrema()[0] < 18:
        return image
    contrast = ImageOps.autocontrast(grey, cutoff=(1, 1))
    return contrast.filter(ImageFilter.UnsharpMask(radius=1.6, percent=140, threshold=2)).convert("RGB")
