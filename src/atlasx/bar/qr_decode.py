from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from threading import Lock
from typing import List, Optional

_QR_DECODE_SIZES = (1024, 900, 768, 640, 512, 384)
_RECTIFIED_SIZE = 900
_RECTIFIED_QR_INSET = 60
_recent_geometry_lock = Lock()
_recent_qr_geometry: Optional[np.ndarray] = None


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
            _remember_qr_geometry(points, candidate.size)
            return decoded_text

    return _decode_with_recent_geometry(image, detector)


def _remember_qr_geometry(points: np.ndarray, image_size: tuple[int, int]) -> None:
    width, height = image_size
    geometry = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if geometry.shape != (4, 2) or width <= 0 or height <= 0:
        return
    if not np.isfinite(geometry).all():
        return
    if abs(cv2.contourArea(geometry)) < width * height * 0.01:
        return

    normalized = geometry / np.array([width, height], dtype=np.float32)
    with _recent_geometry_lock:
        global _recent_qr_geometry
        _recent_qr_geometry = normalized


def _decode_with_recent_geometry(
    image: Image.Image,
    detector: cv2.QRCodeDetector,
) -> Optional[str]:
    with _recent_geometry_lock:
        geometry = (
            None
            if _recent_qr_geometry is None
            else _recent_qr_geometry.copy()
        )
    if geometry is None:
        return None

    grayscale = np.asarray(image.convert("L"))
    height, width = grayscale.shape[:2]
    source_points = geometry * np.array([width, height], dtype=np.float32)
    inset = _RECTIFIED_QR_INSET
    far_edge = _RECTIFIED_SIZE - inset
    destination_points = np.array(
        [
            [inset, inset],
            [far_edge, inset],
            [far_edge, far_edge],
            [inset, far_edge],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(source_points, destination_points)
    rectified = cv2.warpPerspective(
        grayscale,
        transform,
        (_RECTIFIED_SIZE, _RECTIFIED_SIZE),
        borderValue=255,
    )
    decode_points = destination_points.reshape(1, 4, 2)

    # A local threshold restores low-contrast modules hidden by screen glare.
    thresholded = cv2.adaptiveThreshold(
        rectified,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        21,
        1,
    )
    try:
        decoded_text, _ = detector.decode(thresholded, decode_points)
    except (AttributeError, cv2.error):
        decoded_text = ""
    if decoded_text:
        return decoded_text

    # Some dense payloads decode more reliably when OpenCV redetects the
    # finder pattern after thresholding over a wider neighborhood.
    thresholded = cv2.adaptiveThreshold(
        rectified,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        81,
        1,
    )
    try:
        decoded_text, _, _ = detector.detectAndDecode(thresholded)
    except cv2.error:
        return None
    if decoded_text:
        return decoded_text
    return None


def _decode_payload_image(image: Image.Image) -> bytes:
    from atlasx.foo.qr_payloads import decode_payload_image

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
