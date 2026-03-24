from __future__ import annotations

import numpy as np
from PIL import Image

from optical_transfer.sender.qr_payloads import decode_payload_image


def decode_qr_payload(image: np.ndarray) -> bytes | None:
    try:
        pil_image = Image.fromarray(np.asarray(image))
        return decode_payload_image(pil_image)
    except ValueError:
        return None
