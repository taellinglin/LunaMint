"""Cryptographic helpers (SM2/SM3/SM4 + POW token) for bill verification."""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from lunalib.core import sm2, sm3, sm4


@dataclass
class CryptoConfig:
    issuer_id: str = "lunamint"
    validity_days: int = 365
    pow_difficulty: int = 12
    verify_base_url: str = "https://bank.linglin.art/verify"
    sm2_private_key: Optional[str] = None
    sm2_public_key: Optional[str] = None
    sm4_key: Optional[str] = None
    encrypt_payload: bool = False


def load_crypto_config() -> CryptoConfig:
    issuer_id = os.getenv("LUNA_ISSUER_ID", "lunamint")
    validity_days = int(os.getenv("LUNA_VALIDITY_DAYS", "365"))
    pow_difficulty = int(os.getenv("LUNA_POW_DIFFICULTY", "12"))
    verify_base_url = os.getenv("LUNA_VERIFY_BASE_URL", "https://bank.linglin.art/verify")
    sm2_private_key = os.getenv("LUNA_SM2_PRIVATE_KEY")
    sm2_public_key = os.getenv("LUNA_SM2_PUBLIC_KEY")
    sm4_key = os.getenv("LUNA_SM4_KEY")
    encrypt_payload = os.getenv("LUNA_SM4_ENABLE", "false").lower() == "true"

    return CryptoConfig(
        issuer_id=issuer_id,
        validity_days=validity_days,
        pow_difficulty=pow_difficulty,
        verify_base_url=verify_base_url,
        sm2_private_key=sm2_private_key,
        sm2_public_key=sm2_public_key,
        sm4_key=sm4_key,
        encrypt_payload=encrypt_payload,
    )


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sm3_digest(data: bytes) -> bytes:
    if hasattr(sm3, "hash"):
        result = sm3.hash(data)
    elif hasattr(sm3, "sm3_hash"):
        result = sm3.sm3_hash(data)
    elif hasattr(sm3, "hash_bytes"):
        result = sm3.hash_bytes(data)
    else:
        raise RuntimeError("lunalib.core.sm3 does not expose a hash function")

    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        try:
            return bytes.fromhex(result)
        except ValueError:
            return result.encode("utf-8")
    if isinstance(result, list):
        return bytes(result)
    raise TypeError("Unsupported SM3 hash return type")


def _normalize_sm2_result(result: Any, data: bytes) -> bytes:
    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        try:
            return bytes.fromhex(result)
        except ValueError:
            return result.encode("utf-8")
    if isinstance(result, list):
        return bytes(result)
    if result is None:
        raise TypeError("SM2 sign returned None")
    raise TypeError("Unsupported SM2 sign return type")


def _try_sm2_callable(fn: Any, data: bytes, private_key: str) -> bytes | None:
    payloads = [data, data.hex(), data.decode("utf-8", errors="ignore")]
    for payload in payloads:
        try:
            return _normalize_sm2_result(fn(payload, private_key), data)
        except AttributeError:
            if isinstance(payload, (bytes, bytearray)):
                try:
                    return _normalize_sm2_result(fn(payload.decode("utf-8", errors="ignore"), private_key), data)
                except (TypeError, AttributeError):
                    pass
        except TypeError:
            try:
                return _normalize_sm2_result(fn(private_key, payload), data)
            except (TypeError, AttributeError):
                continue
    return None


def _try_sm2_instance(obj: Any, data: bytes) -> bytes | None:
    for method_name in ("sign", "sign_with_sm3", "sm2_sign"):
        if not hasattr(obj, method_name):
            continue
        method = getattr(obj, method_name)
        for payload in (data, data.hex()):
            try:
                return _normalize_sm2_result(method(payload), data)
            except TypeError:
                pass
            try:
                import secrets

                return _normalize_sm2_result(method(payload, secrets.token_hex(32)), data)
            except TypeError:
                continue
    return None


def _sm2_sign(data: bytes, private_key: str, public_key: Optional[str] = None) -> bytes:
    candidates = (
        "sign",
        "sm2_sign",
        "sign_data",
        "sign_bytes",
        "sign_message",
        "sign_digest",
        "sign_hash",
        "sign_hex",
    )
    for name in candidates:
        if hasattr(sm2, name):
            fn = getattr(sm2, name)
            result = _try_sm2_callable(fn, data, private_key)
            if result is not None:
                return result

    for cls_name in ("CryptSM2", "SM2"):
        if hasattr(sm2, cls_name):
            cls = getattr(sm2, cls_name)
            try:
                obj = cls(private_key=private_key, public_key=public_key or "")
            except TypeError:
                try:
                    obj = cls(private_key, public_key or "")
                except Exception:
                    obj = None
            if obj is not None:
                result = _try_sm2_instance(obj, data)
                if result is not None:
                    return result

    sign_fns = [name for name in dir(sm2) if "sign" in name.lower()]
    raise RuntimeError(
        "lunalib.core.sm2 does not expose a compatible sign function. "
        f"Available sign-like symbols: {', '.join(sign_fns) or 'none'}"
    )


def sm2_sign_bytes(data: bytes, private_key: str, public_key: Optional[str] = None) -> bytes:
    return _sm2_sign(data, private_key, public_key=public_key)


def _sm2_verify(data: bytes, signature: bytes, public_key: str) -> bool:
    if hasattr(sm2, "verify"):
        try:
            return bool(sm2.verify(data, signature, public_key))
        except TypeError:
            return bool(sm2.verify(public_key, data, signature))
    if hasattr(sm2, "sm2_verify"):
        return bool(sm2.sm2_verify(data, signature, public_key))
    raise RuntimeError("lunalib.core.sm2 does not expose a verify function")


def _sm4_encrypt(data: bytes, key: str) -> bytes:
    if hasattr(sm4, "encrypt"):
        try:
            return sm4.encrypt(data, key)
        except TypeError:
            return sm4.encrypt(key, data)
    if hasattr(sm4, "sm4_encrypt"):
        return sm4.sm4_encrypt(data, key)
    raise RuntimeError("lunalib.core.sm4 does not expose an encrypt function")


def _sm4_decrypt(data: bytes, key: str) -> bytes:
    if hasattr(sm4, "decrypt"):
        try:
            return sm4.decrypt(data, key)
        except TypeError:
            return sm4.decrypt(key, data)
    if hasattr(sm4, "sm4_decrypt"):
        return sm4.sm4_decrypt(data, key)
    raise RuntimeError("lunalib.core.sm4 does not expose a decrypt function")


def _leading_zero_bits(data: bytes) -> int:
    count = 0
    for b in data:
        if b == 0:
            count += 8
            continue
        for i in range(7, -1, -1):
            if (b >> i) & 1:
                return count
            count += 1
    return count


def _pow_nonce(base: bytes, difficulty: int) -> int:
    nonce = 0
    while True:
        digest = _sm3_digest(base + nonce.to_bytes(8, "big"))
        if _leading_zero_bits(digest) >= difficulty:
            return nonce
        nonce += 1


def build_crypto_payload(
    serial: str,
    denomination: int,
    issued_at_ms: int,
    config: Optional[CryptoConfig] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = config or load_crypto_config()
    if not cfg.sm2_private_key:
        raise RuntimeError("LUNA_SM2_PRIVATE_KEY is required to sign bill tokens")

    expires_at_ms = issued_at_ms + int(cfg.validity_days * 24 * 60 * 60 * 1000)

    payload = {
        "v": 1,
        "serial": serial,
        "denom": int(denomination),
        "issuer": cfg.issuer_id,
        "issued_at": int(issued_at_ms),
        "expires_at": int(expires_at_ms),
    }
    if extra:
        payload.update(extra)

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    pow_nonce = _pow_nonce(canonical, cfg.pow_difficulty)

    payload["pow_nonce"] = pow_nonce
    payload["pow_difficulty"] = cfg.pow_difficulty

    hashed = _sm3_digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = _sm2_sign(hashed, cfg.sm2_private_key)

    payload["sm3"] = _b64url(hashed)
    payload["sm2_sig"] = _b64url(signature)

    return payload


def build_qr_token(payload: Dict[str, Any], config: Optional[CryptoConfig] = None) -> str:
    cfg = config or load_crypto_config()
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    if cfg.encrypt_payload:
        if not cfg.sm4_key:
            raise RuntimeError("LUNA_SM4_KEY is required when SM4 encryption is enabled")
        encrypted = _sm4_encrypt(raw, cfg.sm4_key)
        return "E1." + _b64url(encrypted)

    return "J1." + _b64url(raw)


def build_qr_url(serial: str, denomination: int, issued_at_ms: int, config: Optional[CryptoConfig] = None) -> str:
    cfg = config or load_crypto_config()
    payload = build_crypto_payload(serial, denomination, issued_at_ms, cfg)
    token = build_qr_token(payload, cfg)
    sep = "&" if "?" in cfg.verify_base_url else "?"
    return f"{cfg.verify_base_url}{sep}serial={serial}&token={token}"


def verify_payload(payload: Dict[str, Any], config: Optional[CryptoConfig] = None) -> bool:
    cfg = config or load_crypto_config()
    if not cfg.sm2_public_key:
        raise RuntimeError("LUNA_SM2_PUBLIC_KEY is required to verify bill tokens")

    sm3_b64 = payload.get("sm3")
    sig_b64 = payload.get("sm2_sig")
    if not sm3_b64 or not sig_b64:
        return False

    compare_payload = dict(payload)
    compare_payload.pop("sm3", None)
    compare_payload.pop("sm2_sig", None)

    expected = _sm3_digest(json.dumps(compare_payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if _b64url(expected) != sm3_b64:
        return False

    signature = base64.urlsafe_b64decode(sig_b64 + "=")
    return _sm2_verify(expected, signature, cfg.sm2_public_key)
