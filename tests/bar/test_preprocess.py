from __future__ import annotations

import numpy as np

from atlasx.bar.preprocess import preprocess_frame


def test_preprocess_frame_converts_opencv_bgr_pixels_to_grayscale() -> None:
    frame = np.array([[[255, 0, 0], [0, 0, 255]]], dtype=np.uint8)

    processed = preprocess_frame(frame)

    assert processed.tolist() == [[29, 76]]


def test_preprocess_frame_preserves_grayscale_arrays() -> None:
    frame = np.array([[0, 127, 255]], dtype=np.uint8)

    processed = preprocess_frame(frame)

    assert np.array_equal(processed, frame)
    assert processed is not frame


def test_preprocess_frame_rejects_unsupported_array_shape() -> None:
    frame = np.zeros((8, 8, 2), dtype=np.uint8)

    try:
        preprocess_frame(frame)
    except ValueError as exc:
        assert str(exc) == "unsupported video frame shape"
    else:
        raise AssertionError("expected unsupported video frame shape")
