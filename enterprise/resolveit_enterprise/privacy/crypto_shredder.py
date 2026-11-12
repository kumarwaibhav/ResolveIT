"""Per-incident encryption, blind index and crypto-shredding.

Raw text is encrypted with a fresh AES-256-GCM data key per incident. The
data key is stored only in wrapped form. Deleting the wrapped key makes the
ciphertext, and every backup of it, unreadable.

KeyWrapper is the KMS boundary. LocalKeyWrapper keeps the master key in
process memory and is for development and tests only; production must supply
a wrapper backed by a managed KMS.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class KeyWrapper(Protocol):
    def wrap(self, tenant_id: UUID, data_key: bytes) -> bytes: ...
    def unwrap(self, tenant_id: UUID, wrapped: bytes) -> bytes: ...
    def index_key(self, tenant_id: UUID) -> bytes: ...


class LocalKeyWrapper:
    """Development KMS stand-in: one master key, per-tenant keys derived by HKDF."""

    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise ValueError("master key must be 32 bytes")
        self._master = master_key

    def _derive(self, tenant_id: UUID, purpose: bytes) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=tenant_id.bytes, info=purpose).derive(
            self._master
        )

    def wrap(self, tenant_id: UUID, data_key: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + AESGCM(self._derive(tenant_id, b"kek")).encrypt(nonce, data_key, tenant_id.bytes)

    def unwrap(self, tenant_id: UUID, wrapped: bytes) -> bytes:
        return AESGCM(self._derive(tenant_id, b"kek")).decrypt(wrapped[:12], wrapped[12:], tenant_id.bytes)

    def index_key(self, tenant_id: UUID) -> bytes:
        return self._derive(tenant_id, b"blind-index")


@dataclass(frozen=True, slots=True)
class SealedText:
    wrapped_key: bytes
    nonce: bytes
    ciphertext: bytes


def seal(wrapper: KeyWrapper, tenant_id: UUID, incident_id: UUID, raw_text: str) -> SealedText:
    data_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(nonce, raw_text.encode("utf-8"), incident_id.bytes)
    return SealedText(wrapper.wrap(tenant_id, data_key), nonce, ciphertext)


def unseal(wrapper: KeyWrapper, tenant_id: UUID, incident_id: UUID, sealed: SealedText) -> str:
    data_key = wrapper.unwrap(tenant_id, sealed.wrapped_key)
    return AESGCM(data_key).decrypt(sealed.nonce, sealed.ciphertext, incident_id.bytes).decode("utf-8")


def blind_index(wrapper: KeyWrapper, tenant_id: UUID, kind: str, canonical_identifier: str) -> bytes:
    """Keyed HMAC of (kind, identifier): finds a person's records without storing who they are."""
    return hmac.new(
        wrapper.index_key(tenant_id), f"{kind}:{canonical_identifier}".encode(), hashlib.sha256
    ).digest()


__all__ = ["KeyWrapper", "LocalKeyWrapper", "SealedText", "blind_index", "seal", "unseal"]
