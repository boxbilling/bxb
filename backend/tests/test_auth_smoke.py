"""Smoke tests for JWT auth utilities and password hashing."""

import uuid

import jwt
import pytest

from app.core.jwt import create_access_token, decode_access_token
from app.core.security import hash_password, verify_password


def test_create_access_token_produces_jwt():
    """create_access_token returns a valid JWT string."""
    token = create_access_token(
        user_id=uuid.uuid4(), org_id=uuid.uuid4(), role="admin"
    )
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # JWT has 3 parts


def test_decode_access_token_round_trip():
    """create then decode returns matching claims."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, org_id=org_id, role="member")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["org"] == str(org_id)
    assert payload["role"] == "member"
    assert "exp" in payload
    assert "iat" in payload


def test_expired_token_raises():
    """A token created with negative expiry raises ExpiredSignatureError."""
    token = create_access_token(
        user_id=uuid.uuid4(), org_id=uuid.uuid4(), role="admin", expires_minutes=-1
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_hash_and_verify_password():
    """hash_password + verify_password round-trips correctly."""
    pw = "my-secret-password-123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True


def test_verify_wrong_password():
    """verify_password returns False for wrong password."""
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False
