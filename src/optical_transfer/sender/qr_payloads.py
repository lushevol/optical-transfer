from __future__ import annotations

import base64
import io
import math
from typing import Iterable, Sequence

from PIL import Image


def encode_payload_image(payload: bytes, *, canvas_size: int | None = None) -> Image.Image:
    data = len(payload).to_bytes(4, "big") + payload
    bits = _bytes_to_bits(data)
    minimum_side = max(1, math.ceil(math.sqrt(len(bits))))
    if canvas_size is None:
        side = minimum_side
    else:
        if canvas_size < minimum_side:
            raise ValueError("canvas_size is too small for payload")
        side = canvas_size
    pixel_count = side * side
    padded_bits = bits + [0] * (pixel_count - len(bits))

    image = Image.new("1", (side, side), 0)
    image.putdata([255 if bit else 0 for bit in padded_bits])
    return image


def decode_payload_image(image: Image.Image) -> bytes:
    grayscale = image.convert("1")
    bits = [1 if pixel else 0 for pixel in grayscale.getdata()]
    if len(bits) < 32:
        raise ValueError("image does not contain a complete payload length prefix")

    header = _bits_to_bytes(bits[:32])
    payload_length = int.from_bytes(header, "big")
    payload_bits_length = payload_length * 8
    available_payload_bits = len(bits) - 32
    if payload_bits_length > available_payload_bits:
        raise ValueError("image payload is truncated")

    payload_bits = bits[32 : 32 + payload_bits_length]
    return _bits_to_bytes(payload_bits)


def encode_payload_images(payloads: Sequence[bytes], *, canvas_size: int | None = None) -> list[Image.Image]:
    return [encode_payload_image(payload, canvas_size=canvas_size) for payload in payloads]


def encode_payload_data_url(payload: bytes, *, canvas_size: int | None = None) -> str:
    image = encode_payload_image(payload, canvas_size=canvas_size)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def required_canvas_size(payloads: Sequence[bytes]) -> int:
    if not payloads:
        return 1
    size = max(max(1, math.ceil(math.sqrt((len(payload) + 4) * 8))) for payload in payloads)
    if size % 2 == 1:
        size += 1
    return size


def decode_payload_images(images: Iterable[Image.Image]) -> list[bytes]:
    return [decode_payload_image(image) for image in images]


payload_to_image = encode_payload_image
image_to_payload = decode_payload_image


def _bytes_to_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def _bits_to_bytes(bits: Sequence[int]) -> bytes:
    if len(bits) % 8 != 0:
        bits = list(bits) + [0] * (8 - (len(bits) % 8))

    output = bytearray()
    for start in range(0, len(bits), 8):
        byte = 0
        for bit in bits[start : start + 8]:
            byte = (byte << 1) | int(bit)
        output.append(byte)
    return bytes(output)
