# Foo Missing Chunks Design

## Goal

Foo can replay only the packets for chunk indexes reported missing by bar, so a follow-up recording can fill gaps without rebroadcasting the whole archive.

## Key Constraint

Bar progress is keyed by the original session metadata. Missing-chunk recovery must reuse the original `session_id`, KDF salt, manifest packet, and data packets. Rebuilding the archive from the source directory with new random session material would create packets that bar cannot merge into the saved progress.

## Design

Foo stores a local session bundle after building a full payload set. The bundle contains the session metadata and original packet bytes needed to reconstruct a `SessionPayloadSet` for later playback. The stored packet bytes remain encrypted; the bundle does not store the password or decrypted archive contents.

The foo CLI accepts `--missing-chunks` as a comma-separated list of zero-based chunk indexes. When the option is present, foo loads the existing bundle for the source directory, validates the requested indexes against `total_chunks`, and serves a filtered packet sequence containing the manifest packet plus only the requested data packets. Existing player behavior remains unchanged for full foo runs.

## User Flow

1. Run foo normally for a source directory.
2. Run bar. If chunks are missing, bar prints the missing chunk indexes and keeps progress in `.atlasx-progress`.
3. Run foo again with `--missing-chunks 3,7,9`.
4. Record the shorter QR playback and pass that video to bar using the same output root and password.

## Error Handling

If `--missing-chunks` is empty, malformed, duplicated, negative, or outside the session's total chunk range, foo raises `ValueError`. If no bundle exists for the source directory, foo raises `ValueError` explaining that a full foo run is required first.

## Tests

Tests cover parsing missing chunk lists, persisting and loading session bundles, building filtered payload views, and routing `handle_foo` through the recovery path when `--missing-chunks` is provided.
