from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


def iter_video_frames(video_path: Path) -> Iterator[np.ndarray]:
    capture = cv2.VideoCapture(str(Path(video_path)))
    try:
        if not capture.isOpened():
            raise ValueError(f"could not open video: {video_path}")

        while True:
            success, frame = capture.read()
            if not success:
                break
            if frame is None:
                continue
            yield frame
    finally:
        capture.release()
