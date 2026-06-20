import urllib.parse
import secrets

CLIENT_ID     = "qW7EdZt4odPA3ZwgHfIntakDoiQ9tXly"
REDIRECT_URI  = "https://localhost:58271"
# offline_access fordert von Auth0 ein Refresh Token an, damit Folge-Syncs ohne
# erneuten interaktiven Login (Selenium) auskommen. Gibt Auth0 trotzdem keins
# zurück, ist offline_access für den Client nicht freigegeben.
SCOPE         = "openid profile email offline_access"
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