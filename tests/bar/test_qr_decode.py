from __future__ import annotations

import numpy as np
from PIL import Image

import atlasx.bar.qr_decode as qr_decode_module
from atlasx.bar.qr_decode import decode_qr_image


def test_decode_qr_image_preserves_aspect_ratio_when_downscaling_large_frames(monkeypatch) -> None:
    class FakeDetector:
        def detectAndDecode(self, image):
            height, width = image.shape[:2]
            if (width, height) == (1024, 576):
                return ("payload", np.ones((1, 4, 2), dtype=np.float32), None)
            return ("", None, None)

    monkeypatch.setattr("atlasx.bar.qr_decode.cv2.QRCodeDetector", lambda: FakeDetector())

    image = Image.new("RGB", (1920, 1080), "white")

    assert decode_qr_image(image) == "payload"


def test_decode_qr_image_reuses_recent_geometry_to_recover_low_contrast_frame(
    monkeypatch,
) -> None:
    class CalibrationDetector:
        def detectAndDecode(self, _image):
            return (
                "calibration",
                np.array(
                    [[[10, 10], [90, 10], [90, 90], [10, 90]]],
                    dtype=np.float32,
                ),
                None,
            )

    class RecoveryDetector:
        def detectAndDecode(self, _image):
            return ("", None, None)

        def decode(self, _image, _points):
            return ("recovered", None)

    detectors = iter([CalibrationDetector(), RecoveryDetector()])
    monkeypatch.setattr(
        qr_decode_module.cv2,
        "QRCodeDetector",
        lambda: next(detectors),
    )
    monkeypatch.setattr(qr_decode_module, "_recent_qr_geometry", None)

    image = Image.new("RGB", (100, 100), "white")

    assert decode_qr_image(image) == "calibration"
    assert decode_qr_image(image) == "recovered"
