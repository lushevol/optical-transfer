# Outbound Missing Chunks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add outbound recovery playback that serves only the manifest plus requested missing chunk packets from the original outbound session.

**Architecture:** Persist encrypted outbound packet bundles under the source directory after full session creation. Load that bundle for `--missing-chunks`, construct a filtered `SessionPayloadSet`, and pass it through the existing player server.

**Tech Stack:** Python 3.12, argparse, dataclasses, JSON, pathlib, pytest.

---

### Task 1: Missing Chunk Argument Parsing

**Files:**
- Modify: `src/atlasx/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing parser tests**

Add tests asserting `--missing-chunks 3,7,9` is parsed as raw CLI input and invalid parsing is handled by a helper.

- [ ] **Step 2: Run parser tests**

Run: `pytest tests/test_cli.py::test_outbound_command_accepts_missing_chunks_option -v`
Expected: FAIL because the option and helper do not exist.

- [ ] **Step 3: Implement parser helper**

Add `parse_missing_chunk_indexes(value: str) -> list[int]` that strips whitespace, rejects empty entries, rejects negatives, rejects duplicates, and returns sorted unique indexes.

- [ ] **Step 4: Run parser tests**

Run: `pytest tests/test_cli.py::test_outbound_command_accepts_missing_chunks_option tests/test_cli.py::test_parse_missing_chunk_indexes_rejects_invalid_input -v`
Expected: PASS.

### Task 2: Outbound Session Bundle Persistence

**Files:**
- Create: `src/atlasx/outbound/session_store.py`
- Modify: `src/atlasx/outbound/session.py`
- Test: `tests/outbound/test_session_store.py`

- [ ] **Step 1: Write failing persistence tests**

Test that saving and loading a payload set preserves `session_id`, `chunk_size`, `total_chunks`, `manifest_packet`, and `data_packets`.

- [ ] **Step 2: Run persistence tests**

Run: `pytest tests/outbound/test_session_store.py -v`
Expected: FAIL because `session_store.py` does not exist.

- [ ] **Step 3: Implement bundle save/load**

Use JSON with hex-encoded bytes. Store the bundle at `<source_dir>/.atlasx-outbound/session.json`. Reconstruct `SessionPayloadSet` with empty archive bytes and a manifest loaded from JSON bytes decrypted only indirectly is not required; instead store manifest JSON fields in the bundle.

- [ ] **Step 4: Run persistence tests**

Run: `pytest tests/outbound/test_session_store.py -v`
Expected: PASS.

### Task 3: Filtered Packet Views

**Files:**
- Modify: `src/atlasx/outbound/session.py`
- Test: `tests/outbound/test_session_store.py`

- [ ] **Step 1: Write failing filtered-view tests**

Test that a filtered payload set keeps the manifest repetitions and only repeats requested data packet indexes.

- [ ] **Step 2: Run filtered-view tests**

Run: `pytest tests/outbound/test_session_store.py::test_filter_session_payloads_keeps_only_requested_data_packets -v`
Expected: FAIL because filtering does not exist.

- [ ] **Step 3: Implement filtering**

Add `filter_session_payloads(payloads: SessionPayloadSet, missing_indexes: list[int]) -> SessionPayloadSet` and validate requested indexes are within `0 <= index < total_chunks`.

- [ ] **Step 4: Run filtered-view tests**

Run: `pytest tests/outbound/test_session_store.py -v`
Expected: PASS.

### Task 4: CLI Recovery Path

**Files:**
- Modify: `src/atlasx/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI routing tests**

Test that normal outbound saves a bundle, and `--missing-chunks` loads the saved bundle, filters it, and passes the filtered payloads to `create_player_app`.

- [ ] **Step 2: Run CLI routing tests**

Run: `pytest tests/test_cli.py::test_handle_outbound_saves_session_bundle_after_full_build tests/test_cli.py::test_handle_outbound_uses_saved_bundle_for_missing_chunks -v`
Expected: FAIL because routing is not implemented.

- [ ] **Step 3: Implement routing**

Normal outbound builds and saves. Recovery outbound parses `--missing-chunks`, loads the bundle, filters packets, and serves the existing player. Missing bundle raises `ValueError`.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_cli.py tests/outbound/test_session_store.py -v`
Expected: PASS.

### Task 5: Full Verification

**Files:**
- Modify as needed based on failures.

- [ ] **Step 1: Run full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 2: Review status**

Run: `git status --short`
Expected: only intended source, test, and docs files are changed.
