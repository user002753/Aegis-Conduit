"""Identity manager: Ed25519 signing/verification helper with graceful fallback."""
from __future__ import annotations

from typing import Dict, Any
import hashlib

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError
    _HAS_PYNACL = True
except Exception:
    SigningKey = None
    VerifyKey = None
    BadSignatureError = Exception
    _HAS_PYNACL = False

if _HAS_PYNACL:
    # provide hex helpers for convenience
    def signature_to_hex(sig: bytes) -> str:
        return sig.hex()

    def hex_to_signature(hexstr: str) -> bytes:
        return bytes.fromhex(hexstr)


class IdentityManager:
    def __init__(self, seed: bytes = None):
        self._signing = None
        self._verify = None
        if _HAS_PYNACL:
            if seed is None:
                self._signing = SigningKey.generate()
            else:
                self._signing = SigningKey(seed)
            self._verify = self._signing.verify_key

    def public_key_hex(self) -> str:
        """Return the active verification key as hex when Ed25519 is available."""
        if _HAS_PYNACL and self._verify:
            return bytes(self._verify).hex()
        return "sha256-fallback"

    def sign(self, payload: bytes) -> bytes:
        if not _HAS_PYNACL or not self._signing:
            return hashlib.sha256(payload).digest()
        return bytes(self._signing.sign(payload).signature)

    def verify(self, payload: bytes, signature: bytes, public_key: bytes | None = None) -> bool:
        if not _HAS_PYNACL or not self._verify:
            return signature == hashlib.sha256(payload).digest()
        try:
            verify_key = VerifyKey(public_key) if public_key else self._verify
            verify_key.verify(payload, signature)
            return True
        except BadSignatureError:
            return False
        except Exception:
            return False

    def verify_report(self, report: Dict[str, Any]) -> bool:
        sig = report.get("signature")
        body = report.get("body") or report.get("payload") or str(report).encode("utf-8")
        public_key = report.get("public_key")
        if isinstance(body, str):
            body = body.encode("utf-8")
        if not sig:
            return False
        if isinstance(sig, str):
            try:
                sig = bytes.fromhex(sig)
            except Exception:
                return False
        if isinstance(public_key, str) and public_key != "sha256-fallback":
            try:
                public_key = bytes.fromhex(public_key)
            except Exception:
                return False
        else:
            public_key = None
        return self.verify(body, sig, public_key)
