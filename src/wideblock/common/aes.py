from __future__ import annotations

from Crypto.Cipher import AES

from .bytes import BLOCK_SIZE


def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != BLOCK_SIZE:
        raise ValueError("AES block size must be 16 bytes")
    return AES.new(key, AES.MODE_ECB).encrypt(block)


def aes_decrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != BLOCK_SIZE:
        raise ValueError("AES block size must be 16 bytes")
    return AES.new(key, AES.MODE_ECB).decrypt(block)
