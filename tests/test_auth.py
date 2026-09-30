import jwt
from challenge.app.auth import issue_token, verify_token, admin_gate
from tests.conftest import HS256_SECRET

def test_issue_and_verify_roundtrip():
    t = issue_token("analyst", "analyst", False)
    claims = verify_token(t)
    assert claims["sub"] == "analyst"
    assert claims["role"] == "analyst"
    assert claims["mfa"] is False

def test_alg_none_forgery_is_accepted_bug():
    forged = jwt.encode({"sub": "x", "role": "admin", "mfa": True}, key="", algorithm="none")
    claims = verify_token(forged)
    assert claims is not None
    assert claims["role"] == "admin"

def test_hs256_with_wrong_secret_is_rejected():
    bad = jwt.encode({"sub": "x", "role": "admin"}, key="wrong", algorithm="HS256")
    assert verify_token(bad) is None

def test_admin_gate_requires_admin_and_mfa():
    assert admin_gate(None) == (False, "unauthorized")
    assert admin_gate({"role": "analyst", "mfa": True}) == (False, "unauthorized")
    assert admin_gate({"role": "admin", "mfa": False}) == (False, "mfa_required")
    assert admin_gate({"role": "admin", "mfa": True}) == (True, "")

def test_non_string_alg_header_returns_none_not_raise():
    import base64, json
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    tok = f'{b64({"alg": 123, "typ": "JWT"})}.{b64({"sub": "x", "role": "admin"})}.sig'
    assert verify_token(tok) is None
    forged = jwt.encode({"sub": "x", "role": "admin", "mfa": True}, key="", algorithm="none")
    assert verify_token(forged)["role"] == "admin"
