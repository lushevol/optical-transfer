from __future__ import annotations

import numpy as np
from PIL import Image

from atlasx.inbound.qr_decode import decode_qr_image


def test_decode_qr_image_preserves_aspect_ratio_when_downscaling_large_frames(monkeypatch) -> None:
    class FakeDetector:
        def detectAndDecode(self, image):
            height, width = image.shape[:2]
            if (width, height) == (1024, 576):
                return ("payload", np.ones((1, 4, 2), dtype=np.float32), None)
            return ("", None, None)

    monkeypatch.setattr("atlasx.inbound.qr_decode.cv2.QRCodeDetector", lambda: FakeDetector())

    image = Image.new("RGB", (1920, 1080), "white")

    assert decode_qr_image(image) == "payload"
