from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Optional, TypeVar


Frame = TypeVar("Frame")
ProcessedFrame = TypeVar("ProcessedFrame")


@dataclass(frozen=True)
class FrameDecodeResult:
    frame_number: int
    packet_bytes: Optional[bytes]


def iter_decoded_frames(
    frames: Iterable[Frame],
    preprocess_frame: Callable[[Frame], ProcessedFrame],
    decode_qr_payload: Callable[[ProcessedFrame], Optional[bytes]],
    *,
    worker_count: int,
) -> Iterator[FrameDecodeResult]:
    if worker_count < 1:
        raise ValueError("decode worker count must be positive")
    if worker_count == 1:
        yield from _iter_decoded_frames_serial(frames, preprocess_frame, decode_qr_payload)
        return

    yield from _iter_decoded_frames_threaded(
        frames,
        preprocess_frame,
        decode_qr_payload,
        worker_count=worker_count,
    )


def _iter_decoded_frames_serial(
    frames: Iterable[Frame],
    preprocess_frame: Callable[[Frame], ProcessedFrame],
    decode_qr_payload: Callable[[ProcessedFrame], Optional[bytes]],
) -> Iterator[FrameDecodeResult]:
    for frame_number, frame in enumerate(frames, start=1):
        try:
            packet_bytes = _decode_frame(frame, preprocess_frame, decode_qr_payload)
        except ValueError:
            packet_bytes = None
        yield FrameDecodeResult(frame_number=frame_number, packet_bytes=packet_bytes)


def _iter_decoded_frames_threaded(
    frames: Iterable[Frame],
    preprocess_frame: Callable[[Frame], ProcessedFrame],
    decode_qr_payload: Callable[[ProcessedFrame], Optional[bytes]],
    *,
    worker_count: int,
) -> Iterator[FrameDecodeResult]:
    pending_limit = worker_count * 2
    frame_iter = enumerate(frames, start=1)
    pending: list[tuple[int, Future[Optional[bytes]]]] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for _ in range(pending_limit):
            if not _submit_next_frame(
                frame_iter,
                pending,
                executor,
                preprocess_frame,
                decode_qr_payload,
            ):
                break

        while pending:
            frame_number, future = pending.pop(0)
            try:
                packet_bytes = future.result()
            except ValueError:
                packet_bytes = None
            yield FrameDecodeResult(frame_number=frame_number, packet_bytes=packet_bytes)

            _submit_next_frame(
                frame_iter,
                pending,
                executor,
                preprocess_frame,
                decode_qr_payload,
            )


def _submit_next_frame(
    frame_iter: Iterator[tuple[int, Frame]],
    pending: list[tuple[int, Future[Optional[bytes]]]],
    executor: ThreadPoolExecutor,
    preprocess_frame: Callable[[Frame], ProcessedFrame],
    decode_qr_payload: Callable[[ProcessedFrame], Optional[bytes]],
) -> bool:
    try:
        frame_number, frame = next(frame_iter)
    except StopIteration:
        return False

    future = executor.submit(_decode_frame, frame, preprocess_frame, decode_qr_payload)
    pending.append((frame_number, future))
    return True


def _decode_frame(
    frame: Frame,
    preprocess_frame: Callable[[Frame], ProcessedFrame],
    decode_qr_payload: Callable[[ProcessedFrame], Optional[bytes]],
) -> Optional[bytes]:
    processed_frame = preprocess_frame(frame)
    return decode_qr_payload(processed_frame)
