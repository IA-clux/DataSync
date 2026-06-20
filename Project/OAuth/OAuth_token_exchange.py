import requests


# ---------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------

AUTH_DOMAIN = "alldaycare.eu.auth0.com"
TOKEN_URL = f"https://{AUTH_DOMAIN}/oauth/token"

CLIENT_ID = "qW7EdZt4odPA3ZwgHfIntakDoiQ9tXly"
REDIRECT_URI = "https://localhost:58271"


# ---------------------------------------------------------
# Token Exchange
# ---------------------------------------------------------

def exchange_code_for_token(
    authorization_code: str,
    code_verifier: str,
    timeout: int = 30
) -> dict:
    """
    Tauscht einen OAuth Authorization Code gegen Tokens (PKCE Flow).

    :param authorization_code: Code vom OAuth Redirect
    :param code_verifier: PKCE Code Verifier
    :param timeout: HTTP Timeout in Sekunden
    :return: vollständige Token-Response (access_token, ggf. refresh_token,
             expires_in, scope, …)
    :raises RuntimeError: bei Fehlern im Token Exchange
    """

    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    try:
        response = requests.post(
            TOKEN_URL,
            json=payload,
            timeout=timeout
        )

        response.raise_for_status()

    except requests.RequestException as e:
        raise RuntimeError(
            f"Fehler beim OAuth Token Exchange: {e}"
        ) from e

    data = response.json()

    if "access_token" not in data:
        raise RuntimeError(
            f"Kein Access Token erhalten. Antwort: {data}"
        )

    return data


def refresh_access_token(
    refresh_token: str,
    timeout: int = 30
) -> dict:
    """
    Holt mit einem Refresh Token ein neues Access Token (kein interaktiver Login).

    Bei aktivierter Refresh-Token-Rotation liefert Auth0 ein neues refresh_token
    in der Antwort; ansonsten bleibt das bisherige gültig.

    :param refresh_token: gespeichertes Refresh Token
    :param timeout: HTTP Timeout in Sekunden
    :return: vollständige Token-Response (access_token, ggf. neues refresh_token,
             expires_in, scope, …)
    :raises RuntimeError: wenn das Refresh Token ungültig/abgelaufen ist oder
            kein Access Token zurückkommt
    """

    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token,
    }

    try:
        response = requests.post(
            TOKEN_URL,
            json=payload,
            timeout=timeout
        )

        response.raise_for_status()

    except requests.RequestException as e:
        raise RuntimeError(
            f"Refresh Token konnte nicht eingelöst werden: {e}"
        ) from e

    data = response.json()

    if "access_token" not in data:
        raise RuntimeError(
            f"Kein Access Token aus Refresh erhalten. Antwort: {data}"
        )

    return data