from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def preprocess_frame(frame_path: Path) -> np.ndarray:
    with Image.open(Path(frame_path)) as image:
        return np.array(image.convert("L"))
