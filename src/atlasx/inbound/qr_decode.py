from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from typing import List, Optional

_QR_DECODE_SIZES = (1024, 900, 768, 640, 512, 384)


def decode_qr_payload(image: np.ndarray) -> Optional[bytes]:
    try:
        pil_image = Image.fromarray(np.asarray(image))
        return _decode_payload_image(pil_image)
    except ValueError:
        return None


def decode_qr_image(image: Image.Image) -> Optional[str]:
    detector = cv2.QRCodeDetector()
    for candidate in _decode_candidates(image):
        rgb_image = np.asarray(candidate)
        bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

        try:
            decoded_text, points, _ = detector.detectAndDecode(bgr_image)
        except cv2.error:
            continue
        if points is not None and decoded_text:
            return decoded_text
    return None


def _decode_payload_image(image: Image.Image) -> bytes:
    from atlasx.outbound.qr_payloads import decode_payload_image

    return decode_payload_image(image)


def _decode_candidates(image: Image.Image) -> List[Image.Image]:
    base_image = image.convert("RGB")
    candidates = [base_image]

    seen_sizes = {base_image.size}
    for target_size in _QR_DECODE_SIZES:
        if base_image.width <= target_size and base_image.height <= target_size:
            continue

        scale = min(target_size / base_image.width, target_size / base_image.height)
        resized = base_image.resize(
            (
                max(1, round(base_image.width * scale)),
                max(1, round(base_image.height * scale)),
            ),
            Image.Resampling.NEAREST,
        )
        if resized.size in seen_sizes:
            continue
        candidates.append(resized)
        seen_sizes.add(resized.size)

    return candidates
