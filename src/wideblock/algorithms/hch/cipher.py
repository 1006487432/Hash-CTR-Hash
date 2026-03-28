from __future__ import annotations

from ...common import (
    BLOCK_SIZE,
    aes_decrypt_block,
    aes_encrypt_block,
    gf_mul,
    sm4_decrypt_block,
    sm4_encrypt_block,
    split_blocks,
    xor_bytes,
)


_GF_IDENTITY = bytes.fromhex("80" + "00" * 15)
_GF_X = bytes.fromhex("40" + "00" * 15)
_AES_KEY_SIZES = {16, 24, 32}


def _validate_tweak(tweak: bytes) -> None:
    if len(tweak) != BLOCK_SIZE:
        raise ValueError("HCH tweak must be 16 bytes")


def _validate_aes_key(key: bytes) -> None:
    if len(key) not in _AES_KEY_SIZES:
        raise ValueError("HCH AES key must be 16, 24, or 32 bytes")


def _validate_sm4_key(key: bytes) -> None:
    if len(key) != BLOCK_SIZE:
        raise ValueError("HCH SM4 key must be 16 bytes")


def _pad_block(block: bytes) -> bytes:
    if len(block) > BLOCK_SIZE:
        raise ValueError("block cannot exceed 16 bytes")
    return block + (b"\x00" * (BLOCK_SIZE - len(block)))


def _length_block(length_bits: int) -> bytes:
    if length_bits < 0:
        raise ValueError("length must be non-negative")
    return length_bits.to_bytes(BLOCK_SIZE, "big")


def _mul_x(block: bytes) -> bytes:
    return gf_mul(block, _GF_X)


def _hch_hash(r_key: bytes, q_key: bytes, blocks: list[bytes]) -> bytes:
    if not blocks:
        raise ValueError("HCH hash requires at least one block")
    for block in blocks:
        if len(block) != BLOCK_SIZE:
            raise ValueError("HCH hash blocks must be 16 bytes")

    state = bytes(BLOCK_SIZE)
    for block in blocks[1:]:
        state = gf_mul(xor_bytes(state, block), r_key)
    return xor_bytes(xor_bytes(q_key, blocks[0]), state)


def _ctr_blocks(key: bytes, seed: bytes, blocks: list[bytes], encrypt_block) -> list[bytes]:
    out: list[bytes] = []
    for index, block in enumerate(blocks, start=1):
        counter = xor_bytes(seed, _length_block(index))
        out.append(xor_bytes(block, encrypt_block(key, counter)))
    return out


def _encrypt_multi_block(key: bytes, plaintext: bytes, tweak: bytes, encrypt_block, decrypt_block) -> bytes:
    blocks = split_blocks(plaintext)
    p1 = blocks[0]
    tail_blocks = blocks[1:]
    padded_last = _pad_block(tail_blocks[-1])
    middle_blocks = tail_blocks[:-1]

    r_key = encrypt_block(key, tweak)
    q_key = encrypt_block(key, xor_bytes(r_key, _length_block(len(plaintext) * 8)))
    m1 = _hch_hash(r_key, q_key, [p1, *middle_blocks, padded_last])
    u1 = encrypt_block(key, m1)
    mixing = xor_bytes(m1, u1)
    seed = encrypt_block(key, mixing)

    ctr_output = _ctr_blocks(key, seed, [*middle_blocks, padded_last], encrypt_block)
    c_middle = ctr_output[:-1]
    d_last = ctr_output[-1]
    c_last = d_last[: len(tail_blocks[-1])]
    u_last = _pad_block(c_last)
    c1 = _hch_hash(r_key, _mul_x(q_key), [u1, *c_middle, u_last])
    return b"".join([c1, *c_middle, c_last])


def _decrypt_multi_block(key: bytes, ciphertext: bytes, tweak: bytes, encrypt_block, decrypt_block) -> bytes:
    blocks = split_blocks(ciphertext)
    c1 = blocks[0]
    tail_blocks = blocks[1:]
    padded_last = _pad_block(tail_blocks[-1])
    middle_blocks = tail_blocks[:-1]

    r_key = encrypt_block(key, tweak)
    q_key = encrypt_block(key, xor_bytes(r_key, _length_block(len(ciphertext) * 8)))
    u1 = _hch_hash(r_key, _mul_x(q_key), [c1, *middle_blocks, padded_last])
    m1 = decrypt_block(key, u1)
    mixing = xor_bytes(m1, u1)
    seed = encrypt_block(key, mixing)

    ctr_output = _ctr_blocks(key, seed, [*middle_blocks, padded_last], encrypt_block)
    p_middle = ctr_output[:-1]
    v_last = ctr_output[-1]
    p_last = v_last[: len(tail_blocks[-1])]
    m_last = _pad_block(p_last)
    p1 = _hch_hash(r_key, q_key, [m1, *p_middle, m_last])
    return b"".join([p1, *p_middle, p_last])


def _encrypt(key: bytes, plaintext: bytes, tweak: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(plaintext) < BLOCK_SIZE:
        raise ValueError("HCH plaintext must be at least 16 bytes")
    _validate_tweak(tweak)

    r_key = encrypt_block(key, tweak)
    q_key = encrypt_block(key, xor_bytes(r_key, _length_block(len(plaintext) * 8)))
    if len(plaintext) == BLOCK_SIZE:
        return xor_bytes(_mul_x(q_key), encrypt_block(key, xor_bytes(plaintext, q_key)))
    return _encrypt_multi_block(key, plaintext, tweak, encrypt_block, decrypt_block)


def _decrypt(key: bytes, ciphertext: bytes, tweak: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(ciphertext) < BLOCK_SIZE:
        raise ValueError("HCH ciphertext must be at least 16 bytes")
    _validate_tweak(tweak)

    r_key = encrypt_block(key, tweak)
    q_key = encrypt_block(key, xor_bytes(r_key, _length_block(len(ciphertext) * 8)))
    if len(ciphertext) == BLOCK_SIZE:
        return xor_bytes(decrypt_block(key, xor_bytes(ciphertext, _mul_x(q_key))), q_key)
    return _decrypt_multi_block(key, ciphertext, tweak, encrypt_block, decrypt_block)


def hch_aes_encrypt(key: bytes, plaintext: bytes, tweak: bytes = b"") -> bytes:
    _validate_aes_key(key)
    return _encrypt(key, plaintext, tweak, aes_encrypt_block, aes_decrypt_block)


def hch_aes_decrypt(key: bytes, ciphertext: bytes, tweak: bytes = b"") -> bytes:
    _validate_aes_key(key)
    return _decrypt(key, ciphertext, tweak, aes_encrypt_block, aes_decrypt_block)


def hch_sm4_encrypt(key: bytes, plaintext: bytes, tweak: bytes = b"") -> bytes:
    _validate_sm4_key(key)
    return _encrypt(key, plaintext, tweak, sm4_encrypt_block, sm4_decrypt_block)


def hch_sm4_decrypt(key: bytes, ciphertext: bytes, tweak: bytes = b"") -> bytes:
    _validate_sm4_key(key)
    return _decrypt(key, ciphertext, tweak, sm4_encrypt_block, sm4_decrypt_block)
