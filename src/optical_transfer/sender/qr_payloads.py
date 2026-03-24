from __future__ import annotations

import math
from typing import Iterable, Sequence

from PIL import Image


def encode_payload_image(payload: bytes) -> Image.Image:
    data = len(payload).to_bytes(4, "big") + payload
    bits = _bytes_to_bits(data)
    side = max(1, math.ceil(math.sqrt(len(bits))))
    pixel_count = side * side
    padded_bits = bits + [0] * (pixel_count - len(bits))

    image = Image.new("1", (side, side), 0)
    image.putdata([255 if bit else 0 for bit in padded_bits])
    return image


def decode_payload_image(image: Image.Image) -> bytes:
    grayscale = image.convert("1")
    bits = [1 if pixel else 0 for pixel in grayscale.getdata()]
    header = _bits_to_bytes(bits[:32])
    payload_length = int.from_bytes(header, "big")
    payload_bits = bits[32 : 32 + payload_length * 8]
    return _bits_to_bytes(payload_bits)


def encode_payload_images(payloads: Sequence[bytes]) -> list[Image.Image]:
    return [encode_payload_image(payload) for payload in payloads]


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
