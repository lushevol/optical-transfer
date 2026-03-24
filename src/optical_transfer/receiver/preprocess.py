from __future__ import annotations

from PIL import Image


def preprocess_frame(image: Image.Image) -> Image.Image:
    return image.convert("1")
