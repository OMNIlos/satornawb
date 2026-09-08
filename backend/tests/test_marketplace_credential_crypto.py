from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.security.marketplace_credentials import (
    CredentialCryptoError,
    CredentialIdentity,
    CredentialKeyring,
    DecryptedCredential,
    EncryptedCredential,
    decrypt_credential,
    encrypt_credential,
)


CANARY = "synthetic-credential-canary-9f3a"
NOW = datetime(2026, 9, 8, 12, 30, tzinfo=timezone.utc)


def _keyring(*, current: int = 7) -> CredentialKeyring:
    return CredentialKeyring(current_key_version=current, keys={7: b"a" * 32, 8: b"b" * 32})


def _identity(
    *,
    provider: str = "wb",
    kind: str = "wb_api",
    schema: int = 1,
    expires_at: datetime | None = None,
) -> CredentialIdentity:
    return CredentialIdentity(
        organization_id=11,
        marketplace_account_id=29,
        provider=provider,
        credential_kind=kind,
        payload_schema_version=schema,
        credential_id=UUID("d7260d6a-f9f2-45d4-9b7e-f1fdd79f571a"),
        generation=3,
        expires_at=expires_at,
    )


def _flip_first(value: bytes) -> bytes:
    return bytes((value[0] ^ 1,)) + value[1:]


def _flip_last(value: bytes) -> bytes:
    return value[:-1] + bytes((value[-1] ^ 1,))


@pytest.mark.parametrize(
    ("identity", "payload"),
    [
        (_identity(), {"token": CANARY}),
        (
            _identity(provider="avito", kind="avito_oauth_client"),
            {"clientId": "synthetic-client", "clientSecret": CANARY},
        ),
        (
            _identity(
                provider="avito",
                kind="avito_oauth_access",
                expires_at=NOW + timedelta(hours=1),
            ),
            {"accessToken": CANARY, "expiresAt": "2026-09-08T13:30:00Z"},
        ),
    ],
)
def test_round_trip_for_every_payload_schema(identity, payload) -> None:
    encrypted = encrypt_credential(identity, payload, _keyring())

    assert encrypted.algorithm == "AES-256-GCM"
    assert encrypted.key_version == 7
    assert encrypted.aad_version == 1
    assert len(encrypted.nonce) == 12
    assert len(encrypted.ciphertext) >= 16
    assert CANARY.encode() not in encrypted.ciphertext

    decrypted = decrypt_credential(identity, encrypted, _keyring())
    assert isinstance(decrypted, DecryptedCredential)
    assert decrypted.reveal() == payload


def test_random_nonce_changes_ciphertext(monkeypatch) -> None:
    nonces = iter((b"1" * 12, b"2" * 12))
    monkeypatch.setattr("app.security.marketplace_credentials._random_nonce", lambda: next(nonces))

    first = encrypt_credential(_identity(), {"token": CANARY}, _keyring())
    second = encrypt_credential(_identity(), {"token": CANARY}, _keyring())

    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext


@pytest.mark.parametrize(
    "mutate",
    [
        lambda identity, encrypted: (identity, replace(encrypted, algorithm="AES-128-GCM")),
        lambda identity, encrypted: (identity, replace(encrypted, key_version=8)),
        lambda identity, encrypted: (replace(identity, credential_id=UUID("f832fdfa-7278-4275-9358-a39e3f28666f")), encrypted),
        lambda identity, encrypted: (replace(identity, generation=4), encrypted),
        lambda identity, encrypted: (replace(identity, organization_id=12), encrypted),
        lambda identity, encrypted: (replace(identity, marketplace_account_id=30), encrypted),
        lambda identity, encrypted: (replace(identity, provider="avito"), encrypted),
        lambda identity, encrypted: (replace(identity, credential_kind="avito_oauth_client"), encrypted),
        lambda identity, encrypted: (replace(identity, payload_schema_version=2), encrypted),
        lambda identity, encrypted: (replace(identity, expires_at=NOW), encrypted),
        lambda identity, encrypted: (identity, replace(encrypted, aad_version=2)),
        lambda identity, encrypted: (identity, replace(encrypted, nonce=_flip_first(encrypted.nonce))),
        lambda identity, encrypted: (identity, replace(encrypted, ciphertext=_flip_first(encrypted.ciphertext))),
        lambda identity, encrypted: (identity, replace(encrypted, ciphertext=_flip_last(encrypted.ciphertext))),
    ],
)
def test_metadata_or_ciphertext_mutation_fails_closed(mutate) -> None:
    identity = _identity()
    encrypted = encrypt_credential(identity, {"token": CANARY}, _keyring())
    changed_identity, changed_encrypted = mutate(identity, encrypted)

    with pytest.raises(CredentialCryptoError) as caught:
        decrypt_credential(changed_identity, changed_encrypted, _keyring())

    assert caught.value.code in {
        "credential_auth_failed",
        "credential_contract_invalid",
        "credential_key_unavailable",
    }
    assert CANARY not in str(caught.value)


@pytest.mark.parametrize(
    "encrypted",
    [
        EncryptedCredential("AES-256-GCM", 99, 1, b"n" * 12, b"c" * 17),
        EncryptedCredential("AES-256-GCM", 7, 1, b"short", b"c" * 17),
        EncryptedCredential("AES-256-GCM", 7, 1, b"n" * 12, b"short"),
    ],
)
def test_unknown_key_and_invalid_lengths_are_typed(encrypted) -> None:
    with pytest.raises(CredentialCryptoError) as caught:
        decrypt_credential(_identity(), encrypted, _keyring())
    assert caught.value.code in {"credential_contract_invalid", "credential_key_unavailable"}


@pytest.mark.parametrize(
    ("identity", "payload"),
    [
        (_identity(provider="unknown"), {"token": CANARY}),
        (_identity(), {"token": ""}),
        (_identity(), {"token": CANARY, "extra": "forbidden"}),
        (_identity(), {"token": "x" * 20_000}),
        (
            _identity(provider="avito", kind="avito_oauth_access", expires_at=NOW),
            {"accessToken": CANARY, "expiresAt": "2026-09-08T12:31:00Z"},
        ),
    ],
)
def test_invalid_allowlist_schema_and_size_fail_closed(identity, payload) -> None:
    with pytest.raises(CredentialCryptoError) as caught:
        encrypt_credential(identity, payload, _keyring())
    assert caught.value.code == "credential_contract_invalid"
    assert CANARY not in str(caught.value)


def test_secret_types_and_errors_are_redacted(caplog) -> None:
    decrypted = DecryptedCredential({"token": CANARY})
    error = CredentialCryptoError("credential_auth_failed")

    assert CANARY not in repr(decrypted)
    assert CANARY not in str(decrypted)
    assert decrypted.__dict__ == {"_payload": {"token": CANARY}}
    assert repr(decrypted) == "<DecryptedCredential redacted>"
    assert str(decrypted) == "<DecryptedCredential redacted>"
    assert str(error) == "credential_auth_failed"
    assert repr(error) == "CredentialCryptoError(code='credential_auth_failed')"

    with caplog.at_level(logging.ERROR):
        logging.getLogger("credential-test").error("credential failure: %s", error)
    assert CANARY not in caplog.text


def test_keyring_rejects_bad_keys_without_disclosing_material() -> None:
    with pytest.raises(CredentialCryptoError) as caught:
        CredentialKeyring(current_key_version=7, keys={7: (CANARY + "x").encode()})
    assert caught.value.code == "credential_configuration_invalid"
    assert CANARY not in str(caught.value)
    assert CANARY not in repr(caught.value)
