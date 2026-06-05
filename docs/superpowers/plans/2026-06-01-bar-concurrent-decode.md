# Bar Concurrent Decode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Speed up bar video decoding by running per-frame preprocessing and QR decoding concurrently.

**Architecture:** Add a focused bar helper that turns video frames into decode results. The helper owns threading and bounded future submission; `handle_bar` remains responsible for packet processing and progress state.

**Tech Stack:** Python standard library `concurrent.futures`, existing OpenCV/Pillow/Numpy decode adapters, pytest.

---

### Task 1: Add Frame Decode Helper

**Files:**
- Create: `src/atlasx/bar/frame_decode.py`
- Test: `tests/bar/test_frame_decode.py`

- [ ] **Step 1: Write failing tests**

```python
def test_iter_decoded_frames_runs_serially_when_worker_count_is_one():
    frames = ["a", "bad", "b"]

    def preprocess(frame):
        if frame == "bad":
            raise ValueError("bad frame")
        return frame.upper()

    def decode(image):
        return image.encode("ascii")

    results = list(iter_decoded_frames(frames, preprocess, decode, worker_count=1))

    assert [result.frame_number for result in results] == [1, 2, 3]
    assert [result.packet_bytes for result in results] == [b"A", None, b"B"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bar/test_frame_decode.py -v`
Expected: FAIL because `atlasx.bar.frame_decode` does not exist.

- [ ] **Step 3: Implement minimal helper**

Define `FrameDecodeResult` and `iter_decoded_frames(frames, preprocess_frame, decode_qr_payload, *, worker_count)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/bar/test_frame_decode.py -v`
Expected: PASS.

### Task 2: Wire CLI Option

**Files:**
- Modify: `src/atlasx/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing parser and wiring tests**

Add tests that `bar --decode-workers 1 recording.mp4` parses worker count and that `handle_bar` passes the value to `iter_decoded_frames`.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_cli.py::test_bar_command_accepts_decode_workers_override tests/test_cli.py::test_handle_bar_passes_decode_workers_to_frame_decoder -v`
Expected: FAIL because the option and injectable helper do not exist.

- [ ] **Step 3: Implement CLI wiring**

Add `--decode-workers`, default it from a small helper, import or inject `iter_decoded_frames`, and replace inline preprocess/decode calls with helper results.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_cli.py::test_bar_command_accepts_decode_workers_override tests/test_cli.py::test_handle_bar_passes_decode_workers_to_frame_decoder -v`
Expected: PASS.

### Task 3: Regression Suite

**Files:**
- Existing bar and integration tests.

- [ ] **Step 1: Run focused bar tests**

Run: `pytest tests/bar tests/test_cli.py tests/integration/test_roundtrip_images.py -v`
Expected: PASS.
