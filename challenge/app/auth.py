import jwt

HS256_SECRET = "foresight-hs256-please-rotate"

def issue_token(sub: str, role: str, mfa: bool) -> str:
    return jwt.encode({"sub": sub, "role": role, "mfa": mfa}, HS256_SECRET, algorithm="HS256")

def verify_token(token: str):
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return None
    # DELIBERATE VULNERABILITY (CTF): trust the token's own alg header.
    if str(header.get("alg", "")).lower() == "none":
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None
    try:
        return jwt.decode(token, HS256_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def admin_gate(claims):
    if not claims or claims.get("role") != "admin":
        return (False, "unauthorized")
    if claims.get("mfa") is not True:
        return (False, "mfa_required")
    return (True, "")
