from __future__ import annotations

from atlasx.bar.frame_decode import iter_decoded_frames


def test_iter_decoded_frames_runs_serially_when_worker_count_is_one() -> None:
    frames = ["a", "bad", "b"]

    def preprocess(frame: str) -> str:
        if frame == "bad":
            raise ValueError("bad frame")
        return frame.upper()

    def decode(image: str) -> bytes:
        return image.encode("ascii")

    results = list(iter_decoded_frames(frames, preprocess, decode, worker_count=1))

    assert [result.frame_number for result in results] == [1, 2, 3]
    assert [result.packet_bytes for result in results] == [b"A", None, b"B"]


def test_iter_decoded_frames_uses_multiple_workers_without_reordering_results() -> None:
    frames = ["slow", "fast", "empty"]
    seen_images: list[str] = []

    def preprocess(frame: str) -> str:
        return frame.upper()

    def decode(image: str) -> bytes | None:
        seen_images.append(image)
        if image == "EMPTY":
            return None
        return image.encode("ascii")

    results = list(iter_decoded_frames(frames, preprocess, decode, worker_count=2))

    assert [result.frame_number for result in results] == [1, 2, 3]
    assert [result.packet_bytes for result in results] == [b"SLOW", b"FAST", None]
    assert sorted(seen_images) == ["EMPTY", "FAST", "SLOW"]


def test_iter_decoded_frames_rejects_non_positive_worker_count() -> None:
    try:
        list(iter_decoded_frames(["frame"], lambda frame: frame, lambda image: None, worker_count=0))
    except ValueError as exc:
        assert str(exc) == "decode worker count must be positive"
    else:
        raise AssertionError("expected ValueError")
