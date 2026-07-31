from __future__ import annotations

from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PIL import Image


def preprocess_frame(frame: Union[Path, np.ndarray, Image.Image]) -> np.ndarray:
    if isinstance(frame, Image.Image):
        return np.array(frame.convert("L"))

    if isinstance(frame, np.ndarray):
        if frame.ndim == 2:
            return frame.copy()
        if frame.ndim == 3 and frame.shape[2] == 3:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if frame.ndim == 3 and frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        raise ValueError("unsupported video frame shape")

    with Image.open(Path(frame)) as image:
        return np.array(image.convert("L"))
