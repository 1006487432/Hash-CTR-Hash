from __future__ import annotations

from .aes import aes_encrypt_block
from .bytes import BLOCK_SIZE


def increment_counter(block: bytes) -> bytes:
    if len(block) != BLOCK_SIZE:
        raise ValueError("counter block must be 16 bytes")
    prefix = block[:12]
    counter = (int.from_bytes(block[12:], "big") + 1) % (1 << 32)
    return prefix + counter.to_bytes(4, "big")


def ctr_prf(key: bytes, initial_counter: bytes, output_len: int) -> bytes:
    if output_len < 0:
        raise ValueError("output_len must be non-negative")
    out = bytearray()
    counter = initial_counter
    while len(out) < output_len:
        out.extend(aes_encrypt_block(key, counter))
        counter = increment_counter(counter)
    return bytes(out[:output_len])
