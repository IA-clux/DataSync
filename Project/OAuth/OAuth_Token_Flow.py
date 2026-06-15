import secrets
import webbrowser

from OAuth_generate_pkce_pair import generate_pkce_pair
from OAuth_build_authorization_url import build_authorization_url

verifier, challenge = generate_pkce_pair()
state = secrets.token_urlsafe(32)

url = build_authorization_url(challenge, state)

webbrowser.open(url)