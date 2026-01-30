"""Generate an SM2 keypair using lunalib.core.sm2 if supported."""
from __future__ import annotations

import inspect
from typing import Any, Callable, Optional, Tuple

from lunalib.core import sm2


def _pick_keygen() -> Optional[Callable[..., Any]]:
    for name in (
        "generate_sm2_keypair",
        "gen_keypair",
        "generate_key_pair",
        "keygen",
        "generate_keys",
    ):
        if hasattr(sm2, name):
            fn = getattr(sm2, name)
            if callable(fn):
                return fn
    return None


def _normalize_pair(result: Any) -> Optional[Tuple[str, str]]:
    if isinstance(result, tuple) and len(result) >= 2:
        priv, pub = result[0], result[1]
        return str(priv), str(pub)
    if isinstance(result, dict):
        priv = result.get("private") or result.get("private_key")
        pub = result.get("public") or result.get("public_key")
        if priv and pub:
            return str(priv), str(pub)
    return None


def main() -> int:
    fn = _pick_keygen()
    if not fn:
        print("No SM2 keygen function found in lunalib.core.sm2.")
        print("Available functions:")
        for name, value in inspect.getmembers(sm2):
            if callable(value) and not name.startswith("_"):
                print("-", name)
        return 1

    try:
        result = fn()
    except TypeError:
        # Some APIs might require curve name or params
        try:
            result = fn("sm2p256v1")
        except Exception as exc:  # pragma: no cover
            print("SM2 keygen failed:", exc)
            return 1
    except Exception as exc:  # pragma: no cover
        print("SM2 keygen failed:", exc)
        return 1

    pair = _normalize_pair(result)
    if not pair:
        print("SM2 keygen returned an unsupported format:", type(result))
        return 1

    private_key, public_key = pair
    print("SM2 private key:", private_key)
    print("SM2 public key:", public_key)
    print()
    print("Set these environment variables:")
    print("  LUNA_SM2_PRIVATE_KEY=...")
    print("  LUNA_SM2_PUBLIC_KEY=...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
