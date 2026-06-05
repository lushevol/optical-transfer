# AtlasX V1 Design

## Status

Approved design for V1 scope and architecture.

## Goal

Build a practical offline, one-way QR data transfer tool that moves a single directory from machine A to machine B through:

`MacBook screen -> phone 4K60 recording -> macOS offline recovery`

V1 prioritizes recovery success rate over throughput. The target payload size is roughly 1 MB to 10 MB.

## Non-Goals

- Maximum throughput
- Real-time receiving
- Bidirectional feedback or retransmission
- Multi-directory sessions
- Rich desktop GUI
- Full FEC implementation in V1

## Product Definition

V1 is a CLI-driven system with:

- An foo CLI that packages data and launches a local web player in Chromium for fullscreen QR playback
- An bar CLI that ingests one or more video files and reconstructs the directory offline

The system should be treated as a reliable transfer protocol over an unreliable QR channel. Video is not trusted as a reliable container.

## Confirmed Decisions

### Operating Environment

- Foo device: MacBook screen, high refresh supported
- Recording device: phone capable of 4K at 60 Hz
- Bar device: macOS
- Native dependencies are acceptable

### UX and Workflow

- Single directory per session
- Foo is CLI-based
- Bar is CLI-based
- Foo playback uses a local webpage in Chrome/Chromium
- Bar works in offline batch mode from recorded video files
- Bar may accept multiple videos and merge chunks by `session_id`
- Recovered output must go into a fresh directory and must not overwrite existing files

### Data Handling

- Archive format: `tar.gz`
- V1 preserves file content and relative paths only
- No filtering rules in V1; the provided directory is transferred as-is
- Default behavior is package -> compress -> chunk -> encrypt -> packetize -> render QR

### Security

- Security model: pre-shared password entered interactively
- User is responsible for password strength
- Use a high-cost KDF
- Use chunk-level independent AEAD encryption and authentication
- Manifest policy: minimal transport header stays in cleartext; object metadata is encrypted

### Reliability

- Fixed number of broadcast rounds
- Single large QR per frame in V1
- Protocol must reserve space for future FEC support
- V1 implementation does not include FEC encoding/decoding
- Completion logic must be designed in an FEC-compatible way
- Overall archive hash is required for final success

### Implementation Strategy

- Conservative defaults with CLI overrides
- Protocol versioning and capability bits are reserved in V1
- Incompatible protocol versions may fail fast in V1
- Bar should perform practical preprocessing, not only naive frame extraction

## Recommended High-Level Architecture

### Foo Pipeline

`directory -> tar.gz -> fixed-size logical chunks -> per-chunk AEAD -> packet assembly -> QR render -> fixed-round playback`

Modules:

- `packager`
- `manifest builder`
- `crypto`
- `framing`
- `qr renderer`
- `playback controller`

### Bar Pipeline

`videos -> frame extraction -> image preprocessing -> QR decode -> packet parse -> dedupe/collect -> per-chunk decrypt/verify -> reassembly -> archive hash verify -> unpack`

Modules:

- `video ingest`
- `preprocess`
- `qr decoder`
- `packet parser`
- `collector`
- `crypto`
- `reassembler`
- `unpacker`
- `reporter`

## Protocol Design

V1 should define three layers.

### 1. Transport Packet Layer

Each QR frame carries exactly one logical packet.

Required packet header fields:

- `magic`
- `protocol_version`
- `capability_flags`
- `session_id`
- `packet_type`
- `chunk_index`
- `total_chunks`
- `payload_length`
- `kdf_id`
- `kdf_salt` or KDF parameter reference
- `header_crc`

Reserved-for-future fields:

- `group_id`
- `symbol_index`
- `parity_flags`

Design notes:

- The header must be sufficient for the bar to identify session membership and start decryption setup
- The transport header should remain compact and mostly stable
- The transport header must not include unnecessary file semantics

### 2. Session Layer

A session represents one transfer object and one logical transmission identity.

Properties:

- Stable `session_id`
- One transfer object per session
- Same session may be replayed across multiple recording attempts
- Bar may merge data from multiple input videos for the same session

### 3. Encrypted Manifest Layer

The manifest contains object-level metadata and is encrypted.

Minimum manifest contents:

- object type
- archive format (`tar.gz`)
- archive byte length
- overall archive hash
- chunk payload size
- total chunk count
- AEAD algorithm identifier
- optional original directory name
- reserved FEC-related parameters

Design notes:

- Keep transport bootstrap data outside the encrypted manifest
- Keep object metadata protected by the user password

## Cryptography Design

Preferred V1 data path:

`tar.gz -> fixed-size chunks -> each chunk independently AEAD-encrypted`

Why:

- Better fit for an unreliable QR channel
- Bad packets can be rejected independently
- Recovery progress can be tracked per chunk
- Easier future extension toward FEC

Requirements:

- Interactive password entry without echo
- High-cost KDF
- Unique nonce handling per chunk
- Authentication failure must drop the chunk
- Final archive hash must still be checked after full reconstruction

Rejected for V1:

- Encrypting one large archive blob and then hard-splitting ciphertext into arbitrary chunks

## Playback Strategy

V1 foo playback should use:

- One large QR per frame
- High-contrast fullscreen rendering
- Fixed count of broadcast rounds
- Clear separation between bootstrap/manifest packets and data packets

Recommended behavior:

- Repeat bootstrap metadata multiple times before data rounds
- Broadcast the full chunk set in each round
- Keep default behavior deterministic rather than adaptive

## Bar Strategy

The bar should accept one or more input videos and merge recoverable data by `session_id`.

Required behavior:

- Extract frames with native tools such as `ffmpeg`
- Perform practical preprocessing such as grayscale conversion, contrast enhancement, and scaling when useful
- Attempt QR decoding with mature libraries/tools
- Parse and validate packet headers
- Deduplicate by `(session_id, chunk_index, packet role)`
- Verify chunk authentication before accepting chunk payload
- Track missing chunks and reconstruction status
- Reassemble only when the logical object is complete

## Success Criteria

A session is successful only when all of the following hold:

- The bar has all required logical chunks for the object
- Every accepted chunk passed authentication
- The reconstructed archive hash matches the manifest hash
- Archive unpacking succeeds

This should be implemented in a way that is compatible with future FEC completion logic.

## Reporting and Diagnostics

The bar must emit a detailed session report.

Minimum report fields:

- input video count
- total extracted frame count
- successfully decoded frame count
- raw packet count
- deduplicated valid chunk count
- missing chunk count
- authentication failure count
- final archive hash result
- per-stage timing

This report is required for debugging and parameter tuning.

## Dependency Strategy

V1 may rely on native tooling and does not need to optimize for zero-dependency installation.

Expected dependencies:

- `ffmpeg` for frame extraction and video preprocessing
- `opencv` or equivalent image-processing capability
- `zxing`, `zbar`, or equivalent QR decoder
- `Chrome/Chromium` for the foo playback surface

## Parameter Strategy

V1 should expose a small number of tunable parameters through CLI flags while shipping conservative defaults.

Examples:

- chunk payload size
- QR density/error-correction selection
- playback FPS
- broadcast round count

V1 should not depend on auto-benchmarking, but the architecture should leave room for a future benchmark mode.

## Risks

### Payload Density Risk

If default chunk size or QR density is too aggressive, measured recovery rate will collapse under real phone-recording conditions.

### Decoder Risk

Decoder choice and preprocessing strategy may dominate recovery performance. This should be treated as a first-class engineering decision.

### No-FEC Risk

Without FEC, V1 will rely on repeat rounds and multi-video merge behavior for robustness.

### Hidden Compatibility Risk

Browser rendering behavior, screen refresh, recording compression, and decoder behavior will interact in ways that theoretical QR capacity does not predict.

## MVP Execution Order

1. Freeze packet and manifest schema for V1
2. Validate image-based roundtrip without video
3. Validate screen playback plus local screen recording
4. Validate real phone-recorded video recovery
5. Tune conservative defaults from observed recovery data
6. Add FEC implementation in a later phase

## Open Items Deferred To Implementation

These are intentionally not frozen in this document and should be validated during implementation and testing:

- exact default chunk payload size
- exact QR version and built-in QR error-correction level
- exact playback FPS
- exact default round count
- exact decoder/toolchain choice after empirical testing

The design assumption for all of these is: choose conservative defaults that maximize recovery reliability under the target capture environment.
