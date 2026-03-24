from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from optical_transfer.receiver.preprocess import preprocess_frame
from optical_transfer.sender.qr_payloads import decode_payload_image


def decode_qr_payload(image: np.ndarray) -> bytes | None:
    try:
        pil_image = Image.fromarray(np.asarray(image))
        return decode_payload_image(pil_image)
    except ValueError:
        return None


def decode_qr_frame(image: Any) -> bytes | None:
    if isinstance(image, np.ndarray):
        return decode_qr_payload(image)
    return decode_qr_payload(preprocess_frame(image))
