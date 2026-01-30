"""Generate an SM4 key using lunalib.core.sm4 if supported."""
from __future__ import annotations

import os
from typing import Any, Callable, Optional

from lunalib.core import sm4


def _pick_keygen() -> Optional[Callable[..., Any]]:
    for name in (
        "generate_key",
        "generate_key_bytes",
        "gen_key",
        "keygen",
        "new_key",
    ):
        if hasattr(sm4, name):
            fn = getattr(sm4, name)
            if callable(fn):
                return fn
    return None


def _normalize_key(result: Any) -> Optional[bytes]:
    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        try:
            return bytes.fromhex(result)
        except ValueError:
            return result.encode("utf-8")
    return None


def main() -> int:
    fn = _pick_keygen()
    if fn:
        try:
            result = fn()
        except TypeError:
            try:
                result = fn(16)
            except Exception as exc:  # pragma: no cover
                print("SM4 keygen failed:", exc)
                return 1
        except Exception as exc:  # pragma: no cover
            print("SM4 keygen failed:", exc)
            return 1

        key_bytes = _normalize_key(result)
        if not key_bytes:
            print("SM4 keygen returned an unsupported format:", type(result))
            return 1
    else:
        key_bytes = os.urandom(16)

    key_hex = key_bytes.hex()
    print("SM4 key (hex):", key_hex)
    print()
    print("Set this environment variable:")
    print("  LUNA_SM4_KEY=...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
