from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image


def preprocess_frame(frame: Union[Path, np.ndarray, Image.Image]) -> np.ndarray:
    if isinstance(frame, Image.Image):
        return np.array(frame.convert("L"))

    if isinstance(frame, np.ndarray):
        return np.array(Image.fromarray(frame).convert("L"))

    with Image.open(Path(frame)) as image:
        return np.array(image.convert("L"))
