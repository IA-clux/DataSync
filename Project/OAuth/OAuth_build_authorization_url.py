import urllib.parse
import secrets

CLIENT_ID     = "qW7EdZt4odPA3ZwgHfIntakDoiQ9tXly"
REDIRECT_URI  = "https://localhost:58271"
SCOPE         = "openid profile email"
AUDIENCE      = "https://bi.alldaycare.de"
AUTH_DOMAIN   = "alldaycare.eu.auth0.com"
AUTHORIZE_URL = f"https://{AUTH_DOMAIN}/authorize"

def build_authorization_url(code_challenge: str) -> str:
    
    state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "audience": AUDIENCE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    query_string = urllib.parse.urlencode(params)
    return f"{AUTHORIZE_URL}?{query_string}"