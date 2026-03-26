from __future__ import annotations


BLOCK_SIZE = 16


def xor_bytes(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("xor operands must have equal length")
    return bytes(a ^ b for a, b in zip(left, right))


def pad16(data: bytes) -> bytes:
    remainder = len(data) % BLOCK_SIZE
    if remainder == 0:
        return data
    return data + b"\x00" * (BLOCK_SIZE - remainder)


def bit_length_block(bit_count: int) -> bytes:
    return bit_count.to_bytes(8, "big")


def split_blocks(data: bytes, block_size: int = BLOCK_SIZE) -> list[bytes]:
    return [data[i : i + block_size] for i in range(0, len(data), block_size)]
