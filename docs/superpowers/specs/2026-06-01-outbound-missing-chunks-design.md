# Outbound Missing Chunks Design

## Goal

Outbound can replay only the packets for chunk indexes reported missing by inbound, so a follow-up recording can fill gaps without rebroadcasting the whole archive.

## Key Constraint

Inbound progress is keyed by the original session metadata. Missing-chunk recovery must reuse the original `session_id`, KDF salt, manifest packet, and data packets. Rebuilding the archive from the source directory with new random session material would create packets that inbound cannot merge into the saved progress.

## Design

Outbound stores a local session bundle after building a full payload set. The bundle contains the session metadata and original packet bytes needed to reconstruct a `SessionPayloadSet` for later playback. The stored packet bytes remain encrypted; the bundle does not store the password or decrypted archive contents.

The outbound CLI accepts `--missing-chunks` as a comma-separated list of zero-based chunk indexes. When the option is present, outbound loads the existing bundle for the source directory, validates the requested indexes against `total_chunks`, and serves a filtered packet sequence containing the manifest packet plus only the requested data packets. Existing player behavior remains unchanged for full outbound runs.

## User Flow

1. Run outbound normally for a source directory.
2. Run inbound. If chunks are missing, inbound prints the missing chunk indexes and keeps progress in `.atlasx-progress`.
3. Run outbound again with `--missing-chunks 3,7,9`.
4. Record the shorter QR playback and pass that video to inbound using the same output root and password.

## Error Handling

If `--missing-chunks` is empty, malformed, duplicated, negative, or outside the session's total chunk range, outbound raises `ValueError`. If no bundle exists for the source directory, outbound raises `ValueError` explaining that a full outbound run is required first.

## Tests

Tests cover parsing missing chunk lists, persisting and loading session bundles, building filtered payload views, and routing `handle_outbound` through the recovery path when `--missing-chunks` is provided.
