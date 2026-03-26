from __future__ import annotations

from ...common import (
    BLOCK_SIZE,
    aes_decrypt_block,
    aes_encrypt_block,
    bit_length_block,
    ctr_prf,
    gf_mul,
    pad16,
    sm4_decrypt_block,
    sm4_encrypt_block,
    split_blocks,
    xor_bytes,
)


def h(hash_key: bytes, left: bytes, right: bytes) -> bytes:
    x = b"\x00" * BLOCK_SIZE
    for block in split_blocks(pad16(left)):
        x = gf_mul(xor_bytes(x, block), hash_key)
    for block in split_blocks(pad16(right)):
        x = gf_mul(xor_bytes(x, block), hash_key)
    lengths = bit_length_block(len(left) * 8) + bit_length_block(len(right) * 8)
    return gf_mul(xor_bytes(x, lengths), hash_key)


def derive_round_keys(key: bytes, encrypt_block) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    if len(key) != 16:
        raise ValueError("XCBv1 uses 16-byte block-cipher keys")

    base = b"\x00" * 15
    k0 = encrypt_block(key, b"\x00" * 16)
    k1 = encrypt_block(key, base + b"\x01")
    k2 = encrypt_block(key, base + b"\x02")
    k3 = encrypt_block(key, base + b"\x03")
    k4 = encrypt_block(key, base + b"\x04")
    return k0, k1, k2, k3, k4


def _encrypt(key: bytes, plaintext: bytes, associated_data: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(plaintext) < BLOCK_SIZE:
        raise ValueError("plaintext must be at least 16 bytes")

    k0, k1, k2, k3, k4 = derive_round_keys(key, encrypt_block)
    a = plaintext[:BLOCK_SIZE]
    b = plaintext[BLOCK_SIZE:]
    c = encrypt_block(k0, a)
    d = xor_bytes(c, h(k1, b, associated_data))
    e = xor_bytes(b, ctr_prf(k2, d, len(b)))
    f = xor_bytes(d, h(k3, e, associated_data))
    g = decrypt_block(k4, f)
    return g + e


def _decrypt(key: bytes, ciphertext: bytes, associated_data: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(ciphertext) < BLOCK_SIZE:
        raise ValueError("ciphertext must be at least 16 bytes")

    k0, k1, k2, k3, k4 = derive_round_keys(key, encrypt_block)
    g = ciphertext[:BLOCK_SIZE]
    e = ciphertext[BLOCK_SIZE:]
    f = encrypt_block(k4, g)
    d = xor_bytes(f, h(k3, e, associated_data))
    b = xor_bytes(e, ctr_prf(k2, d, len(e)))
    c = xor_bytes(d, h(k1, b, associated_data))
    a = decrypt_block(k0, c)
    return a + b


def xcb_aes_v1_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, associated_data, aes_encrypt_block, aes_decrypt_block)


def xcb_aes_v1_decrypt(key: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, associated_data, aes_encrypt_block, aes_decrypt_block)


def xcb_sm4_v1_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, associated_data, sm4_encrypt_block, sm4_decrypt_block)


def xcb_sm4_v1_decrypt(key: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, associated_data, sm4_encrypt_block, sm4_decrypt_block)
