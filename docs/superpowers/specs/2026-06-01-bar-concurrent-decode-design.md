# Bar Concurrent Decode Design

## Goal

Bar should decode video frames faster by processing independent frame preprocessing and QR decode work concurrently, while keeping packet collection, progress persistence, and restore behavior deterministic.

## Key Constraint

Frame decode work is parallelizable, but bar session state is not. Packet validation updates shared collector state, writes progress files, loads saved progress, tracks manifest metadata, and reports ordered progress. Those operations should stay on the main thread.

## Design

Add a small bar frame decode helper that accepts an iterator of frames plus the existing `preprocess_frame` and `decode_qr_payload` callables. The helper yields one result per extracted frame, containing the frame number and either decoded packet bytes, no payload, or a recoverable decode error.

When worker count is `1`, the helper runs synchronously and preserves the current behavior. When worker count is greater than `1`, it uses `ThreadPoolExecutor` to run preprocessing and QR decoding for several frames at once. The helper keeps only a bounded number of pending futures so long videos do not accumulate all frames in memory.

The CLI adds `--decode-workers` for bar. The default enables threaded decode with a conservative CPU-based worker count. Users can pass `--decode-workers 1` to force the old serial path for debugging or comparison.

The main bar loop continues to read videos in order and process decoded packet results on the main thread. It updates frame counts, decoded counts, packet collection, progress files, and logs exactly as it does today.

## Error Handling

`--decode-workers` must be a positive integer. Per-frame `ValueError` from preprocessing or QR decode is treated like the current serial path: that frame is skipped and decoding continues. Unexpected exceptions should propagate so real implementation faults are visible.

## Tests

Tests cover serial helper behavior, threaded helper behavior, bounded worker validation through CLI parsing, bar passing the configured worker count into the decode helper, and existing bar recovery behavior with `--decode-workers 1`.
