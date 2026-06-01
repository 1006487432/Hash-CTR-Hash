from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


BLOCK_SIZE = 16


def xor_bytes(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("xor operands must have equal length")
    return bytes(a ^ b for a, b in zip(left, right))


def bit_length_block(bit_count: int) -> bytes:
    return bit_count.to_bytes(8, "big")


def pad16(data: bytes) -> bytes:
    remainder = len(data) % BLOCK_SIZE
    if remainder == 0:
        return data
    return data + b"\x00" * (BLOCK_SIZE - remainder)


def split_blocks(data: bytes, block_size: int = BLOCK_SIZE) -> list[bytes]:
    return [data[i : i + block_size] for i in range(0, len(data), block_size)]


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


def h(hash_key: bytes, left: bytes, right: bytes) -> bytes:
    x = b"\x00" * BLOCK_SIZE
    for block in split_blocks(pad16(left)):
        x = gf_mul(xor_bytes(x, block), hash_key)
    for block in split_blocks(pad16(right)):
        x = gf_mul(xor_bytes(x, block), hash_key)
    lengths = bit_length_block(len(left) * 8) + bit_length_block(len(right) * 8)
    return gf_mul(xor_bytes(x, lengths), hash_key)


def increment_counter(block: bytes) -> bytes:
    if len(block) != BLOCK_SIZE:
        raise ValueError("counter block must be 16 bytes")
    prefix = block[:12]
    counter = (int.from_bytes(block[12:], "big") + 1) % (1 << 32)
    return prefix + counter.to_bytes(4, "big")



_GF_IDENTITY = b"\x80" + b"\x00" * 15


@dataclass(frozen=True)
class XcbStarCycleAttackTranscript:
    plaintext: bytes
    ciphertext: bytes
    forged_plaintext: bytes
    forged_ciphertext: bytes
    decrypted_forgery: bytes
    delta: bytes
    distance: int
    delta_block: bytes


@dataclass(frozen=True)
class _RoundKeys:
    k0: bytes
    k1: bytes
    k2: bytes
    k3: bytes
    k4: bytes


def _sample_bytes(label: str, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(sha256(f"xcbstar-cycle:{label}:{counter}".encode("ascii")).digest())
        counter += 1
    return bytes(out[:length])


def _toy_encrypt_block(key: bytes, block: bytes) -> bytes:
    return xor_bytes(key, block)


def _toy_decrypt_block(key: bytes, block: bytes) -> bytes:
    return xor_bytes(key, block)


def _toy_ctr_prf(key: bytes, initial_counter: bytes, output_len: int) -> bytes:
    out = bytearray()
    counter = initial_counter
    while len(out) < output_len:
        out.extend(_toy_encrypt_block(key, counter))
        counter = increment_counter(counter)
    return bytes(out[:output_len])


def _encrypt_with_round_keys(round_keys: _RoundKeys, plaintext: bytes, associated_data: bytes) -> bytes:
    if len(plaintext) < BLOCK_SIZE:
        raise ValueError("plaintext must be at least 16 bytes")

    a = plaintext[:BLOCK_SIZE]
    b = plaintext[BLOCK_SIZE:]
    delta1 = h(round_keys.k1, b, associated_data)
    s = xor_bytes(_toy_encrypt_block(round_keys.k0, xor_bytes(a, delta1)), delta1)
    e = xor_bytes(b, _toy_ctr_prf(round_keys.k2, s, len(b)))
    delta2 = h(round_keys.k3, e, associated_data)
    g = xor_bytes(_toy_decrypt_block(round_keys.k4, xor_bytes(s, delta2)), delta2)
    return g + e


def _decrypt_with_round_keys(round_keys: _RoundKeys, ciphertext: bytes, associated_data: bytes) -> bytes:
    if len(ciphertext) < BLOCK_SIZE:
        raise ValueError("ciphertext must be at least 16 bytes")

    g = ciphertext[:BLOCK_SIZE]
    e = ciphertext[BLOCK_SIZE:]
    delta2 = h(round_keys.k3, e, associated_data)
    s = xor_bytes(_toy_encrypt_block(round_keys.k4, xor_bytes(g, delta2)), delta2)
    b = xor_bytes(e, _toy_ctr_prf(round_keys.k2, s, len(e)))
    delta1 = h(round_keys.k1, b, associated_data)
    a = xor_bytes(_toy_decrypt_block(round_keys.k0, xor_bytes(s, delta1)), delta1)
    return a + b


def _build_delta(message_len: int, *, block_index: int, distance: int, delta_block: bytes) -> bytes:
    if message_len % BLOCK_SIZE != 0:
        raise ValueError("cycle attack PoC expects block-aligned B data")
    if len(delta_block) != BLOCK_SIZE:
        raise ValueError("delta block must be 16 bytes")

    block_count = message_len // BLOCK_SIZE
    paired_index = block_index + distance
    if block_index < 0 or paired_index >= block_count:
        raise ValueError("cycle attack delta positions are outside B")

    blocks = [bytes(BLOCK_SIZE) for _ in range(block_count)]
    blocks[block_index] = delta_block
    blocks[paired_index] = delta_block
    return b"".join(blocks)


def run_xcbstar_cycle_attack_poc() -> XcbStarCycleAttackTranscript:
    distance = 1
    delta_block = _sample_bytes("delta", BLOCK_SIZE)
    associated_data = _sample_bytes("ad", BLOCK_SIZE)
    plaintext = _sample_bytes("plaintext", BLOCK_SIZE * 5)
    round_keys = _RoundKeys(
        k0=_sample_bytes("k0", BLOCK_SIZE),
        k1=_GF_IDENTITY,
        k2=_sample_bytes("k2", BLOCK_SIZE),
        k3=_GF_IDENTITY,
        k4=_sample_bytes("k4", BLOCK_SIZE),
    )

    ciphertext = _encrypt_with_round_keys(round_keys, plaintext, associated_data)
    b_data = plaintext[BLOCK_SIZE:]
    delta = _build_delta(len(b_data), block_index=0, distance=distance, delta_block=delta_block)
    forged_plaintext = plaintext[:BLOCK_SIZE] + xor_bytes(b_data, delta)
    forged_ciphertext = ciphertext[:BLOCK_SIZE] + xor_bytes(ciphertext[BLOCK_SIZE:], delta)
    decrypted_forgery = _decrypt_with_round_keys(round_keys, forged_ciphertext, associated_data)

    return XcbStarCycleAttackTranscript(
        plaintext=plaintext,
        ciphertext=ciphertext,
        forged_plaintext=forged_plaintext,
        forged_ciphertext=forged_ciphertext,
        decrypted_forgery=decrypted_forgery,
        delta=delta,
        distance=distance,
        delta_block=delta_block,
    )


__all__ = ["XcbStarCycleAttackTranscript", "run_xcbstar_cycle_attack_poc"]
