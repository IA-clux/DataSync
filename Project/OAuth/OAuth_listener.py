from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import ssl
import threading
import time
import sys


# ---------------------------------------------------------
# Shared Result Container
# ---------------------------------------------------------

class OAuthResult:
    code = None
    state = None


# ---------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------

class OAuthCallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # OAuth Parameter auslesen
        OAuthResult.code = query_params.get("code", [None])[0]
        OAuthResult.state = query_params.get("state", [None])[0]

        # Antwort an Browser
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"OAuth Login erfolgreich. Fenster kann geschlossen werden."
        )

    def log_message(self, format, *args):
        # Konsolen-Logging unterdrücken
        return


# ---------------------------------------------------------
# Public API: HTTPS OAuth Listener
# ---------------------------------------------------------

def wait_for_oauth_redirect(
    host: str = "localhost",
    port: int = 58271,
    timeout: int = 60
) -> str:
    """
    Startet einen HTTPS OAuth Redirect Listener und wartet
    auf den Authorization Code.

    :return: Authorization Code
    :raises TimeoutError: wenn kein Redirect empfangen wird
    """

    # Zustand zurücksetzen
    OAuthResult.code = None
    OAuthResult.state = None

    # --- HTTP Server vorbereiten (noch ohne TLS) ---
    httpd = HTTPServer((host, port), OAuthCallbackHandler)

    # --- TLS-Zertifikate laden ---
    cert_file = resource_path("certs/localhost.pem")
    key_file = resource_path("certs/localhost-key.pem")

    if not cert_file.exists() or not key_file.exists():
        raise FileNotFoundError(
            f"TLS-Zertifikate nicht gefunden:\n{cert_file}\n{key_file}"
        )

    # --- TLS aktivieren ---
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(
        certfile=cert_file,
        keyfile=key_file
    )

    httpd.socket = ssl_context.wrap_socket(
        httpd.socket,
        server_side=True
    )

    # --- Server in separatem Thread starten ---
    server_thread = threading.Thread(
        target=httpd.serve_forever,
        daemon=True
    )
    server_thread.start()

    # --- Auf Redirect warten (blocking) ---
    start_time = time.time()
    try:
        while OAuthResult.code is None:
            if time.time() - start_time > timeout:
                raise TimeoutError("OAuth Redirect wurde nicht empfangen.")
            time.sleep(0.1)
    finally:
        httpd.shutdown()

    return OAuthResult.code

def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path