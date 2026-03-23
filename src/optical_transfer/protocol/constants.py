from __future__ import annotations

import struct

PROTOCOL_HEADER_MAGIC = b"OTV1"
PROTOCOL_HEADER_VERSION = 1
PROTOCOL_KDF_SALT_SIZE = 16

# Wire format:
#   magic[4] | protocol_version[1] | capability_flags[4] | session_id[16]
#   packet_type[1] | chunk_index[4] | total_chunks[4] | payload_length[4]
#   kdf_id[1] | kdf_salt[16] | header_crc[4]
PROTOCOL_HEADER_BODY_STRUCT = struct.Struct(">4sBI16sBIIIB16s")
PROTOCOL_HEADER_STRUCT = struct.Struct(">4sBI16sBIIIB16sI")
PROTOCOL_HEADER_SIZE = PROTOCOL_HEADER_STRUCT.size
PROTOCOL_HEADER_BODY_SIZE = PROTOCOL_HEADER_BODY_STRUCT.size
PROTOCOL_SESSION_ID_SIZE = 16
