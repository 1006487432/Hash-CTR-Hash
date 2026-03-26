from __future__ import annotations

from collections.abc import Callable

from .algorithms.hch.cipher import hch_aes_decrypt, hch_aes_encrypt, hch_sm4_decrypt, hch_sm4_encrypt
from .algorithms.hctr1.cipher import (
    hctr1_aes_decrypt,
    hctr1_aes_encrypt,
    hctr1_sm4_decrypt,
    hctr1_sm4_encrypt,
)
from .algorithms.hctr2.cipher import hctr2_aes_decrypt, hctr2_aes_encrypt
from .algorithms.xcbstar.cipher import (
    xcbstar_aes_decrypt,
    xcbstar_aes_encrypt,
    xcbstar_sm4_decrypt,
    xcbstar_sm4_encrypt,
)
from .algorithms.xcbv1.cipher import (
    xcb_aes_v1_decrypt,
    xcb_aes_v1_encrypt,
    xcb_sm4_v1_decrypt,
    xcb_sm4_v1_encrypt,
)
from .algorithms.xcbv2.cipher import (
    xcb_aes_decrypt,
    xcb_aes_encrypt,
    xcb_sm4_decrypt,
    xcb_sm4_encrypt,
)


CipherFn = Callable[[bytes, bytes, bytes], bytes]


ALGORITHMS: dict[str, dict[str, CipherFn]] = {
    "hch_aes": {"encrypt": hch_aes_encrypt, "decrypt": hch_aes_decrypt},
    "hch_sm4": {"encrypt": hch_sm4_encrypt, "decrypt": hch_sm4_decrypt},
    "hctr1_aes": {"encrypt": hctr1_aes_encrypt, "decrypt": hctr1_aes_decrypt},
    "hctr1_sm4": {"encrypt": hctr1_sm4_encrypt, "decrypt": hctr1_sm4_decrypt},
    "hctr2": {"encrypt": hctr2_aes_encrypt, "decrypt": hctr2_aes_decrypt},
    "xcbstar": {"encrypt": xcbstar_aes_encrypt, "decrypt": xcbstar_aes_decrypt},
    "xcbstar_sm4": {"encrypt": xcbstar_sm4_encrypt, "decrypt": xcbstar_sm4_decrypt},
    "xcbv1": {"encrypt": xcb_aes_v1_encrypt, "decrypt": xcb_aes_v1_decrypt},
    "xcbv1_sm4": {"encrypt": xcb_sm4_v1_encrypt, "decrypt": xcb_sm4_v1_decrypt},
    "xcbv2": {"encrypt": xcb_aes_encrypt, "decrypt": xcb_aes_decrypt},
    "xcbv2_sm4": {"encrypt": xcb_sm4_encrypt, "decrypt": xcb_sm4_decrypt},
}


def list_algorithms() -> list[str]:
    return sorted(ALGORITHMS)


def get_algorithm(name: str) -> dict[str, CipherFn]:
    try:
        return ALGORITHMS[name]
    except KeyError as exc:
        raise KeyError(f"unknown algorithm: {name}") from exc
