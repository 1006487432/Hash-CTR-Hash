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


def h1(hash_key: bytes, tweak: bytes, b: bytes) -> bytes:
    pad_bytes = 16 + ((16 - (len(b) % 16)) % 16)
    return h(hash_key, (b"\x00" * 16) + tweak, b + (b"\x00" * pad_bytes))


def h2(hash_key: bytes, tweak: bytes, e: bytes) -> bytes:
    pad_bytes = (16 - (len(e) % 16)) % 16
    lengths = bit_length_block((len(tweak) * 8) + 128) + bit_length_block(len(e) * 8)
    return h(hash_key, tweak + (b"\x00" * 16), e + (b"\x00" * pad_bytes) + lengths)


def derive_xcb_subkeys(key: bytes, encrypt_block, allowed_key_sizes: tuple[int, ...]) -> tuple[bytes, bytes, bytes, bytes]:
    if len(key) not in allowed_key_sizes:
        raise ValueError(f"XCB key must be one of {allowed_key_sizes} bytes")

    zero = b"\x00" * 15
    selectors = [1, 2, 3, 4, 5, 6]
    blocks = [encrypt_block(key, zero + bytes([selector])) for selector in selectors]
    hash_key = encrypt_block(key, b"\x00" * 16)
    key_len = len(key)
    enc_key = (blocks[0] + blocks[1])[:key_len]
    dec_key = (blocks[2] + blocks[3])[:key_len]
    ctr_key = (blocks[4] + blocks[5])[:key_len]
    return hash_key, enc_key, dec_key, ctr_key


def _encrypt(key: bytes, plaintext: bytes, associated_data: bytes, encrypt_block, decrypt_block, allowed_key_sizes: tuple[int, ...]) -> bytes:
    if len(plaintext) < BLOCK_SIZE:
        raise ValueError("plaintext must be at least 16 bytes")

    hash_key, enc_key, dec_key, ctr_key = derive_xcb_subkeys(key, encrypt_block, allowed_key_sizes)
    a = plaintext[-BLOCK_SIZE:]
    b = plaintext[:-BLOCK_SIZE]
    c = encrypt_block(enc_key, a)
    d = xor_bytes(c, h1(hash_key, associated_data, b))
    e = xor_bytes(b, ctr_prf(ctr_key, d, len(b)))
    f = xor_bytes(d, h2(hash_key, associated_data, e))
    g = decrypt_block(dec_key, f)
    return e + g


def _decrypt(key: bytes, ciphertext: bytes, associated_data: bytes, encrypt_block, decrypt_block, allowed_key_sizes: tuple[int, ...]) -> bytes:
    if len(ciphertext) < BLOCK_SIZE:
        raise ValueError("ciphertext must be at least 16 bytes")

    hash_key, enc_key, dec_key, ctr_key = derive_xcb_subkeys(key, encrypt_block, allowed_key_sizes)
    g = ciphertext[-BLOCK_SIZE:]
    e = ciphertext[:-BLOCK_SIZE]
    f = encrypt_block(dec_key, g)
    d = xor_bytes(f, h2(hash_key, associated_data, e))
    b = xor_bytes(e, ctr_prf(ctr_key, d, len(e)))
    c = xor_bytes(d, h1(hash_key, associated_data, b))
    a = decrypt_block(enc_key, c)
    return b + a


def xcb_aes_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, associated_data, aes_encrypt_block, aes_decrypt_block, (16, 32))


def xcb_aes_decrypt(key: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, associated_data, aes_encrypt_block, aes_decrypt_block, (16, 32))


def xcb_sm4_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, associated_data, sm4_encrypt_block, sm4_decrypt_block, (16,))


def xcb_sm4_decrypt(key: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, associated_data, sm4_encrypt_block, sm4_decrypt_block, (16,))
