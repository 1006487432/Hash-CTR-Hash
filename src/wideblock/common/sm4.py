from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .bytes import BLOCK_SIZE


def sm4_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(key) != BLOCK_SIZE:
        raise ValueError("SM4 key must be 16 bytes")
    if len(block) != BLOCK_SIZE:
        raise ValueError("SM4 block size must be 16 bytes")
    cipher = Cipher(algorithms.SM4(key), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(block) + encryptor.finalize()


def sm4_decrypt_block(key: bytes, block: bytes) -> bytes:
    if len(key) != BLOCK_SIZE:
        raise ValueError("SM4 key must be 16 bytes")
    if len(block) != BLOCK_SIZE:
        raise ValueError("SM4 block size must be 16 bytes")
    cipher = Cipher(algorithms.SM4(key), modes.ECB())
    decryptor = cipher.decryptor()
    return decryptor.update(block) + decryptor.finalize()
