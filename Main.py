import sys
import os


def _ensure_std_streams():
    """PyInstaller --noconsole startet ohne Standard-Streams (sys.stdout/err = None);
    print() wuerde dann crashen. Auf eine Logdatei im App-Daten-Verzeichnis umleiten,
    damit Diagnose-Ausgaben erhalten bleiben statt die Anwendung zu beenden."""
    if sys.stdout is not None and sys.stderr is not None:
        return

    log_dir = os.path.join(
        os.getenv("APPDATA", os.getcwd()),
        "Ihre Alltagsbegleiter", "AlldayCareFetcher"
    )
    try:
        os.makedirs(log_dir, exist_ok=True)
        sink = open(os.path.join(log_dir, "datasync.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        sink = open(os.devnull, "w")

    if sys.stdout is None:
        sys.stdout = sink
    if sys.stderr is None:
        sys.stderr = sink


_ensure_std_streams()

from Project.Controller import Controller

if __name__ == "__main__":
    app = Controller()
    app.start()
