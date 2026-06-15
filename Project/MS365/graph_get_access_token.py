import requests

def graph_get_access_token(
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> str:

    TOKEN_URL = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    token_data = {
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "client_credentials",
        "scope":         "https://graph.microsoft.com/.default"
    }

    token_response = requests.post(TOKEN_URL, data=token_data)
    token_response.raise_for_status()

    access_token = token_response.json()["access_token"]

    return access_token