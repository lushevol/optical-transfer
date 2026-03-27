from __future__ import annotations

import base64
import io
from typing import Iterable, List, Optional, Sequence

from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_M


_QR_BOX_SIZE = 12
_QR_BORDER = 4
_BASE45_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
_BASE45_INDEX = {character: index for index, character in enumerate(_BASE45_CHARSET)}


def encode_payload_image(payload: bytes, *, canvas_size: Optional[int] = None) -> Image.Image:
    image = _build_qr_image(payload)
    if canvas_size is None:
        return image

    if canvas_size < image.width or canvas_size < image.height:
        raise ValueError("canvas_size is too small for payload")

    canvas = Image.new("RGB", (canvas_size, canvas_size), "white")
    left = (canvas_size - image.width) // 2
    top = (canvas_size - image.height) // 2
    canvas.paste(image, (left, top))
    return canvas


def decode_payload_image(image: Image.Image) -> bytes:
    from optical_transfer.receiver.qr_decode import decode_qr_image

    decoded_text = decode_qr_image(image)
    if decoded_text is None:
        raise ValueError("image does not contain a decodable QR payload")

    try:
        return _base45_decode(decoded_text)
    except ValueError as exc:
        raise ValueError("image QR payload is not valid base45") from exc


def encode_payload_images(payloads: Sequence[bytes], *, canvas_size: Optional[int] = None) -> List[Image.Image]:
    return [encode_payload_image(payload, canvas_size=canvas_size) for payload in payloads]


def encode_payload_data_url(payload: bytes, *, canvas_size: Optional[int] = None) -> str:
    image = encode_payload_image(payload, canvas_size=canvas_size)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def required_canvas_size(payloads: Sequence[bytes]) -> int:
    if not payloads:
        return 1
    size = max(_build_qr_image(payload).width for payload in payloads)
    if size % 2 == 1:
        size += 1
    return size


def decode_payload_images(images: Iterable[Image.Image]) -> List[bytes]:
    return [decode_payload_image(image) for image in images]


payload_to_image = encode_payload_image
image_to_payload = decode_payload_image


def _build_qr_image(payload: bytes) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=_QR_BOX_SIZE,
        border=_QR_BORDER,
    )
    qr.add_data(_base45_encode(payload))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def _base45_encode(data: bytes) -> str:
    characters: List[str] = []
    for index in range(0, len(data), 2):
        chunk = data[index : index + 2]
        if len(chunk) == 2:
            value = chunk[0] * 256 + chunk[1]
            characters.append(_BASE45_CHARSET[value % 45])
            characters.append(_BASE45_CHARSET[(value // 45) % 45])
            characters.append(_BASE45_CHARSET[value // 2025])
            continue

        value = chunk[0]
        characters.append(_BASE45_CHARSET[value % 45])
        characters.append(_BASE45_CHARSET[value // 45])
    return "".join(characters)


def _base45_decode(data: str) -> bytes:
    decoded = bytearray()
    index = 0
    while index < len(data):
        remaining = len(data) - index
        if remaining < 2:
            raise ValueError("base45 payload has an incomplete trailing group")

        if remaining >= 3:
            try:
                value = (
                    _BASE45_INDEX[data[index]]
                    + _BASE45_INDEX[data[index + 1]] * 45
                    + _BASE45_INDEX[data[index + 2]] * 2025
                )
            except KeyError as exc:
                raise ValueError("base45 payload contains an invalid character") from exc

            if value > 0xFFFF:
                raise ValueError("base45 payload contains an out-of-range triplet")
            decoded.extend(divmod(value, 256))
            index += 3
            continue

        try:
            value = _BASE45_INDEX[data[index]] + _BASE45_INDEX[data[index + 1]] * 45
        except KeyError as exc:
            raise ValueError("base45 payload contains an invalid character") from exc

        if value > 0xFF:
            raise ValueError("base45 payload contains an out-of-range pair")
        decoded.append(value)
        index += 2

    return bytes(decoded)
