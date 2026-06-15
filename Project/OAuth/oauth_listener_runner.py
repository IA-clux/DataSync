from threading import Thread
from Project.OAuth.OAuth_listener import wait_for_oauth_redirect


class OAuthListenerRunner:
    def __init__(self):
        self._code = None
        self._thread = None
        self._error = None

    def start(self):
        """
        Startet den OAuth-Listener in einem separaten Thread.
        Blockiert NICHT.
        """
        def _worker():
            try:
                self._code = wait_for_oauth_redirect()
            except Exception as e:
                self._error = e

        self._thread = Thread(target=_worker, daemon=True)
        self._thread.start()

    def wait_for_code(self, timeout: int = 130) -> str:
        """
        Wartet auf den Authorization Code.
        """
        if not self._thread:
            raise RuntimeError("OAuth Listener wurde nicht gestartet")

        self._thread.join(timeout=timeout)

        if self._thread.is_alive():
            raise TimeoutError("OAuth Redirect wurde nicht empfangen")

        if self._error:
            raise self._error

        if not self._code:
            raise RuntimeError("Kein Authorization Code erhalten")

        return self._code
