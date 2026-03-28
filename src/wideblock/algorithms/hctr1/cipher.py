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


def _pad_block(block: bytes) -> bytes:
    return block + (b"\x00" * (BLOCK_SIZE - len(block)))


def _int_to_block(value: int) -> bytes:
    return value.to_bytes(BLOCK_SIZE, "big")


def _split_hctr_key(key: bytes) -> tuple[bytes, bytes]:
    if len(key) != 32:
        raise ValueError("HCTR1 key must be 32 bytes: K1 || K2")
    return key[:16], key[16:]


def _hctr_hash(hash_key: bytes, message: bytes) -> bytes:
    blocks = split_blocks(message)
    y = b"\x00" * BLOCK_SIZE
    for block in blocks:
        y = gf_mul(xor_bytes(y, _pad_block(block)), hash_key)
    return gf_mul(xor_bytes(y, _int_to_block(len(message) * 8)), hash_key)


def _hctr_ctr(data_key: bytes, seed: bytes, data: bytes, encrypt_block) -> bytes:
    if not data:
        return b""
    out = bytearray()
    block_count = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE
    for index in range(1, block_count + 1):
        counter = xor_bytes(seed, _int_to_block(index))
        out.extend(encrypt_block(data_key, counter))
    keystream = bytes(out[: len(data)])
    return bytes(a ^ b for a, b in zip(data, keystream))


def _encrypt(key: bytes, plaintext: bytes, tweak: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(plaintext) < BLOCK_SIZE:
        raise ValueError("plaintext must be at least 16 bytes")
    if len(tweak) != BLOCK_SIZE:
        raise ValueError("HCTR1 tweak must be 16 bytes")

    data_key, hash_key = _split_hctr_key(key)
    p1 = plaintext[:BLOCK_SIZE]
    tail = plaintext[BLOCK_SIZE:]
    z1 = xor_bytes(p1, _hctr_hash(hash_key, tail + tweak))
    z2 = encrypt_block(data_key, z1)
    seed = xor_bytes(z1, z2)
    ct_tail = _hctr_ctr(data_key, seed, tail, encrypt_block)
    c1 = xor_bytes(z2, _hctr_hash(hash_key, ct_tail + tweak))
    return c1 + ct_tail


def _decrypt(key: bytes, ciphertext: bytes, tweak: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(ciphertext) < BLOCK_SIZE:
        raise ValueError("ciphertext must be at least 16 bytes")
    if len(tweak) != BLOCK_SIZE:
        raise ValueError("HCTR1 tweak must be 16 bytes")

    data_key, hash_key = _split_hctr_key(key)
    c1 = ciphertext[:BLOCK_SIZE]
    tail = ciphertext[BLOCK_SIZE:]
    z2 = xor_bytes(c1, _hctr_hash(hash_key, tail + tweak))
    z1 = decrypt_block(data_key, z2)
    seed = xor_bytes(z1, z2)
    pt_tail = _hctr_ctr(data_key, seed, tail, encrypt_block)
    p1 = xor_bytes(z1, _hctr_hash(hash_key, pt_tail + tweak))
    return p1 + pt_tail


def hctr1_aes_encrypt(key: bytes, plaintext: bytes, tweak: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, tweak, aes_encrypt_block, aes_decrypt_block)


def hctr1_aes_decrypt(key: bytes, ciphertext: bytes, tweak: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, tweak, aes_encrypt_block, aes_decrypt_block)


def hctr1_sm4_encrypt(key: bytes, plaintext: bytes, tweak: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, tweak, sm4_encrypt_block, sm4_decrypt_block)


def hctr1_sm4_decrypt(key: bytes, ciphertext: bytes, tweak: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, tweak, sm4_encrypt_block, sm4_decrypt_block)
