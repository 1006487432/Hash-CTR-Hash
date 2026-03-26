from __future__ import annotations

from ...common import BLOCK_SIZE, aes_decrypt_block, aes_encrypt_block, xor_bytes


_AES_KEY_SIZES = {16, 24, 32}
_POLYVAL_MODULUS = sum(1 << power for power in [128, 127, 126, 121, 0])
_POLYVAL_CONST = sum(1 << power for power in [127, 124, 121, 114, 0])


def _validate_aes_key(key: bytes) -> None:
    if len(key) not in _AES_KEY_SIZES:
        raise ValueError("HCTR2 AES key must be 16, 24, or 32 bytes")


def _pad_block_aligned(data: bytes) -> bytes:
    remainder = len(data) % BLOCK_SIZE
    if remainder == 0:
        return data
    return data + b"\x00" * (BLOCK_SIZE - remainder)


def _polyval_multiply(x: bytes, y: bytes) -> bytes:
    if len(x) != BLOCK_SIZE or len(y) != BLOCK_SIZE:
        raise ValueError("POLYVAL operands must be 16 bytes")

    a = int.from_bytes(x, "little")
    b = int.from_bytes(y, "little")
    product = 0
    for _ in range(128):
        if b & 1:
            product ^= a
        carry = a & (1 << 127)
        a <<= 1
        if carry:
            a ^= _POLYVAL_MODULUS
        b >>= 1
    return product.to_bytes(BLOCK_SIZE, "little")


def _polyval_hash(key: bytes, message: bytes) -> bytes:
    if len(key) != BLOCK_SIZE:
        raise ValueError("POLYVAL key must be 16 bytes")
    if len(message) % BLOCK_SIZE != 0:
        raise ValueError("POLYVAL message must be block aligned")

    h = _polyval_multiply(key, _POLYVAL_CONST.to_bytes(BLOCK_SIZE, "little"))
    state = bytes(BLOCK_SIZE)
    for offset in range(0, len(message), BLOCK_SIZE):
        block = message[offset : offset + BLOCK_SIZE]
        state = _polyval_multiply(xor_bytes(state, block), h)
    return state


def _hctr2_hash(hash_key: bytes, message: bytes, tweak: bytes) -> bytes:
    awkward = len(message) % BLOCK_SIZE != 0
    length_int = len(tweak) * 16 + 2
    if awkward:
        length_int += 1

    blocks = bytearray(length_int.to_bytes(BLOCK_SIZE, "little"))
    blocks.extend(_pad_block_aligned(tweak))
    if awkward:
        blocks.extend(_pad_block_aligned(message + b"\x01"))
    else:
        blocks.extend(message)
    return _polyval_hash(hash_key, bytes(blocks))


def _schedule_block(key: bytes, index: int) -> bytes:
    return aes_encrypt_block(key, index.to_bytes(BLOCK_SIZE, "little"))


def _xctr_transform(key: bytes, data: bytes, nonce: bytes) -> bytes:
    if len(nonce) != BLOCK_SIZE:
        raise ValueError("HCTR2 nonce must be 16 bytes")

    stream = bytearray()
    counter = 0
    while len(stream) < len(data):
        counter += 1
        counter_block = counter.to_bytes(BLOCK_SIZE, "little")
        stream.extend(aes_encrypt_block(key, xor_bytes(nonce, counter_block)))
    return xor_bytes(data, bytes(stream[: len(data)]))


def hctr2_aes_encrypt(key: bytes, plaintext: bytes, tweak: bytes = b"") -> bytes:
    _validate_aes_key(key)
    if len(plaintext) < BLOCK_SIZE:
        raise ValueError("HCTR2 plaintext must be at least 16 bytes")

    hash_key = _schedule_block(key, 0)
    l_value = _schedule_block(key, 1)
    m_block = plaintext[:BLOCK_SIZE]
    n_data = plaintext[BLOCK_SIZE:]

    masked_m = xor_bytes(m_block, _hctr2_hash(hash_key, n_data, tweak))
    encrypted_masked_m = aes_encrypt_block(key, masked_m)
    stream_nonce = xor_bytes(xor_bytes(masked_m, encrypted_masked_m), l_value)
    v_data = _xctr_transform(key, n_data, stream_nonce)
    u_block = xor_bytes(encrypted_masked_m, _hctr2_hash(hash_key, v_data, tweak))
    return u_block + v_data


def hctr2_aes_decrypt(key: bytes, ciphertext: bytes, tweak: bytes = b"") -> bytes:
    _validate_aes_key(key)
    if len(ciphertext) < BLOCK_SIZE:
        raise ValueError("HCTR2 ciphertext must be at least 16 bytes")

    hash_key = _schedule_block(key, 0)
    l_value = _schedule_block(key, 1)
    u_block = ciphertext[:BLOCK_SIZE]
    v_data = ciphertext[BLOCK_SIZE:]

    encrypted_masked_m = xor_bytes(u_block, _hctr2_hash(hash_key, v_data, tweak))
    masked_m = aes_decrypt_block(key, encrypted_masked_m)
    stream_nonce = xor_bytes(xor_bytes(masked_m, encrypted_masked_m), l_value)
    n_data = _xctr_transform(key, v_data, stream_nonce)
    m_block = xor_bytes(masked_m, _hctr2_hash(hash_key, n_data, tweak))
    return m_block + n_data
