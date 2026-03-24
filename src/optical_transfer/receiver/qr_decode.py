from __future__ import annotations

from PIL import Image

from optical_transfer.receiver.preprocess import preprocess_frame
from optical_transfer.sender.qr_payloads import decode_payload_image


def decode_qr_frame(image: Image.Image) -> bytes:
    return decode_payload_image(preprocess_frame(image))
