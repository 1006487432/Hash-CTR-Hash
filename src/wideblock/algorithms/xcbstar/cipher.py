from __future__ import annotations

from ...common import aes_decrypt_block, aes_encrypt_block, ctr_prf, sm4_decrypt_block, sm4_encrypt_block, xor_bytes
from ..xcbv1.cipher import derive_round_keys, h


def _encrypt(key: bytes, plaintext: bytes, associated_data: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(plaintext) < 16:
        raise ValueError("plaintext must be at least 16 bytes")

    k0, k1, k2, k3, k4 = derive_round_keys(key, encrypt_block)
    a = plaintext[:16]
    b = plaintext[16:]
    delta1 = h(k1, b, associated_data)
    s = xor_bytes(encrypt_block(k0, xor_bytes(a, delta1)), delta1)
    e = xor_bytes(b, ctr_prf(k2, s, len(b)))
    delta2 = h(k3, e, associated_data)
    g = xor_bytes(decrypt_block(k4, xor_bytes(s, delta2)), delta2)
    return g + e


def _decrypt(key: bytes, ciphertext: bytes, associated_data: bytes, encrypt_block, decrypt_block) -> bytes:
    if len(ciphertext) < 16:
        raise ValueError("ciphertext must be at least 16 bytes")

    k0, k1, k2, k3, k4 = derive_round_keys(key, encrypt_block)
    g = ciphertext[:16]
    e = ciphertext[16:]
    delta2 = h(k3, e, associated_data)
    s = xor_bytes(encrypt_block(k4, xor_bytes(g, delta2)), delta2)
    b = xor_bytes(e, ctr_prf(k2, s, len(e)))
    delta1 = h(k1, b, associated_data)
    a = xor_bytes(decrypt_block(k0, xor_bytes(s, delta1)), delta1)
    return a + b


def xcbstar_aes_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, associated_data, aes_encrypt_block, aes_decrypt_block)


def xcbstar_aes_decrypt(key: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, associated_data, aes_encrypt_block, aes_decrypt_block)


def xcbstar_sm4_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> bytes:
    return _encrypt(key, plaintext, associated_data, sm4_encrypt_block, sm4_decrypt_block)


def xcbstar_sm4_decrypt(key: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    return _decrypt(key, ciphertext, associated_data, sm4_encrypt_block, sm4_decrypt_block)
