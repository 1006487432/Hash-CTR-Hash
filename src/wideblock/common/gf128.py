from __future__ import annotations

from .bytes import BLOCK_SIZE


def gf_mul(x: bytes, y: bytes) -> bytes:
    if len(x) != BLOCK_SIZE or len(y) != BLOCK_SIZE:
        raise ValueError("GF multiplication operands must be 16 bytes")

    x_state = bytearray(x)
    z = bytearray(BLOCK_SIZE)
    for y_byte in y:
        mask = 0x80
        while mask > 0:
            if y_byte & mask:
                for idx in range(BLOCK_SIZE):
                    z[idx] ^= x_state[idx]
            mask >>= 1
            lsb = x_state[15] & 0x01
            for idx in range(15, 0, -1):
                carry = x_state[idx - 1] & 0x01
                x_state[idx] = (x_state[idx] >> 1) | (carry << 7)
            x_state[0] >>= 1
            if lsb:
                x_state[0] ^= 0xE1
    return bytes(z)
