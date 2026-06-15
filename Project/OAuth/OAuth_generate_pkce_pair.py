import secrets
import base64
import hashlib

def generate_pkce_pair():
    random_bytes = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(random_bytes).rstrip(b"=").decode("ascii")

    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    return verifier, challenge

