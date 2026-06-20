from .GUI       import GUI
from .Fetcher   import *

from threading import Thread
from pathlib   import Path
from datetime  import datetime
import json
import os
import keyring
import keyring.backends.Windows

# Im gepackten (noconsole) Build steht keyrings Backend-Auto-Discovery nicht
# zur Verfügung → Windows Credential Manager explizit setzen, damit das Speichern
# der Zugangsdaten auch in der Exe funktioniert.
try:
    keyring.set_keyring(keyring.backends.Windows.WinVaultKeyring())
except Exception:
    pass

from Project.OAuth.oauth_listener_runner import OAuthListenerRunner
from Project.OAuth.OAuth_generate_pkce_pair import generate_pkce_pair
from Project.OAuth.OAuth_build_authorization_url import build_authorization_url
from Project.OAuth.OAuth_token_exchange import exchange_code_for_token, refresh_access_token
from Project.OAuth.Selenium_authorize import selenium_oauth_login


class Controller:

    _LOCAL_APPDATA_PATH = Path(os.getenv("APPDATA")) / "Ihre Alltagsbegleiter" / "AlldayCareFetcher"
    _SETTINGS_PATH = _LOCAL_APPDATA_PATH / "Fetcher_Settings.txt"

    # Dienstname für die OS-Keyring-Ablage der Nutzer-Zugangsdaten.
    _KEYRING_SERVICE = "AlldayCareFetcher"

    _DEFAULT_SETTINGS = {
        "organisation": "",
        "last_updated": None,
        # Optionaler lokaler SQLite-Abzug: standardmäßig deaktiviert, Pfad frei wählbar.
        "db_enabled": False,
        "db_path": "",
        # AlldayCare Refresh Token (übergangsweise in der Settings-Datei; bei der
        # späteren VPS-Auslagerung verschlüsselt auf dem Server abgelegt).
        "refresh_token": None,
    }

    SETTINGS: dict = {}

    def __init__(self):

        self.running = False

        # Nur das App-Daten-Verzeichnis für die Settings ist zwingend.
        # Die feste SharePoint-Synchronisations-Abhängigkeit entfällt (VPS-/Headless-Vorbereitung);
        # das Ziel des optionalen DB-Abzugs bestimmt der Nutzer selbst.
        self._LOCAL_APPDATA_PATH.mkdir(parents=True, exist_ok=True)

        self._load_settings()
        self._migrate_credentials_to_keyring()

        self.gui: GUI = GUI(controller = self)

    # -----------------------------------------------------------------------------
    # Nutzer-Zugangsdaten im OS-Keyring (Username/Passwort)
    # -----------------------------------------------------------------------------

    def get_credential(self, key: str) -> str:
        return keyring.get_password(self._KEYRING_SERVICE, key) or ""

    def set_credential(self, key: str, value: str):
        if value:
            keyring.set_password(self._KEYRING_SERVICE, key, value)
        else:
            try:
                keyring.delete_password(self._KEYRING_SERVICE, key)
            except keyring.errors.PasswordDeleteError:
                pass

    def _migrate_credentials_to_keyring(self):
        """Verschiebt evtl. noch in der Settings-Datei liegende Zugangsdaten
        einmalig in den OS-Keyring und entfernt sie aus der Datei."""
        migrated = False
        for key in ("username", "password"):
            legacy = self.SETTINGS.pop(key, None)
            if legacy:
                if not self.get_credential(key):
                    self.set_credential(key, legacy)
                migrated = True
        if migrated:
            self.save_settings()

    def _load_settings(self):

        def parse_ts(s: str) -> datetime.timestamp:
            try:
                return datetime.fromisoformat(s)
            except Exception:
                return self._DEFAULT_SETTINGS["last_updated"]

        if not self._SETTINGS_PATH.exists():
            self.SETTINGS = self._DEFAULT_SETTINGS.copy()
        else:
            with open(self._SETTINGS_PATH, "r", encoding="utf-8") as f:
                file_content = json.load(f)

            # Defaults + gespeicherte Werte mergen
            self.SETTINGS = {
                **self._DEFAULT_SETTINGS,
                **file_content
            }

            self.SETTINGS["last_updated"] = parse_ts(self.SETTINGS["last_updated"])

    def save_settings(self):

        settings = self.SETTINGS.copy()

        # datetime → ISO‑String
        if isinstance(settings["last_updated"], datetime):
            settings["last_updated"] = settings["last_updated"].isoformat()

        filtered = {k: v for k, v in settings.items() if k in self._DEFAULT_SETTINGS}

        with open(
            file     = self._SETTINGS_PATH,
            mode     = "w",
            encoding = "utf-8",
        ) as settings_file:
            json.dump(
                obj    = filtered,
                fp     = settings_file,
                indent = 2,
            )

    def start(self):

        self.running = True
        Thread(target = self.gui.tray_icon.run, daemon=True).start()
        self.gui.root.mainloop()

    def update_now(self):

        # UI sperren und vorherigen Zustand sauber zurücksetzen
        self.gui.set_busy(True)
        self.gui.clear_error()
        self.gui.reset_progress()
        self.gui.set_status("Vorbereitung…")

        Thread(target=self._run_sync, daemon=True).start()

    # -----------------------------------------------------------------------------
    # Token-Beschaffung: Refresh Token bevorzugt, Selenium als Fallback
    # -----------------------------------------------------------------------------

    def _obtain_token(self) -> dict:
        refresh_token = self.SETTINGS.get("refresh_token")

        if refresh_token:
            try:
                self.gui.set_status("Aktualisiere Sitzung…")
                token_response = refresh_access_token(refresh_token)
                self._store_token_response(token_response)
                return token_response
            except Exception as e:
                # z. B. invalid_grant / abgelaufen → einmal sauber auf Vollanmeldung zurückfallen
                self.gui.append_error(f"Refresh fehlgeschlagen, neue Anmeldung nötig: {e}")
                self.SETTINGS["refresh_token"] = None

        return self._full_login()

    def _full_login(self) -> dict:
        verifier, challenge = generate_pkce_pair()
        auth_url = build_authorization_url(challenge)

        # OAuth: Listener starten, per Selenium Redirect auslösen, Code holen
        self.gui.set_status("Anmeldung bei AlldayCare…")
        listener = OAuthListenerRunner()
        listener.start()

        selenium_oauth_login(
            log          = self.gui.append_error,
            auth_url     = auth_url,
            username     = self.get_credential("username"),
            password     = self.get_credential("password"),
            organisation = self.SETTINGS["organisation"],
            debug_mode   = True
        )

        code = listener.wait_for_code()
        token_response = exchange_code_for_token(code, verifier)
        self._store_token_response(token_response)
        return token_response

    def _store_token_response(self, token_response: dict):
        # Bei aktivierter Rotation liefert Auth0 ein neues refresh_token; sonst bleibt
        # das bisherige gültig (dann kein Überschreiben).
        new_refresh = token_response.get("refresh_token")
        if new_refresh:
            self.SETTINGS["refresh_token"] = new_refresh
            self.save_settings()

        # Diagnose: Laufzeit/Token-Präsenz einmalig sichtbar machen (Konsole).
        print(
            f"[TOKEN] expires_in={token_response.get('expires_in')}s, "
            f"refresh_token_present={'refresh_token' in token_response}, "
            f"scope={token_response.get('scope')}"
        )

    def _run_sync(self):

        try:
            time_before_data_pull = datetime.now()

            # 1) Token holen: bevorzugt per Refresh Token (ohne Browser-Login),
            #    sonst vollständige Anmeldung via Selenium.
            token_response = self._obtain_token()
            access_token = token_response["access_token"]
            print()  # Hold Console clean!

            # 2) Daten aus AlldayCare laden
            data = fetch_all_entities(controller=self, token=access_token)

            time_needed_to_pull_data = datetime.now() - time_before_data_pull
            output_str = f"{time_needed_to_pull_data.days} Tage, {time_needed_to_pull_data.seconds//3600} Std, {(time_needed_to_pull_data.seconds//60)%60} Min, {time_needed_to_pull_data.seconds%60} Sek"
            print(f"Time needed to pull Data from AlldayCare: {output_str}", end="\n\n")

            # 3) Optional: in lokale SQLite-Datenbank schreiben
            if self.SETTINGS.get("db_enabled") and self.SETTINGS.get("db_path"):
                db_dir = Path(self.SETTINGS["db_path"])
                db_dir.mkdir(parents=True, exist_ok=True)
                self.gui.set_status("Speichere in lokale Datenbank…")
                self.gui.hide_progress()
                push_to_sqlite(db_dir, data)

            # 4) Nach SharePoint synchronisieren
            time_before_sp_push = datetime.now()
            push_to_sharepoint(controller=self, data=data)
            time_required_for_sharepoint_push = datetime.now() - time_before_sp_push
            output_str = f"{time_required_for_sharepoint_push.days} Tage, {time_required_for_sharepoint_push.seconds//3600} Std, {(time_required_for_sharepoint_push.seconds//60)%60} Min, {time_required_for_sharepoint_push.seconds%60} Sek"
            print(f"Time needed to synchronize Data to Sharepoint: {output_str}", end="\n\n")

            # 5) Erfolg: Timestamp aktualisieren
            self.SETTINGS["last_updated"] = datetime.now()
            self.save_settings()
            ts = self.SETTINGS["last_updated"].strftime("%d.%m.%Y %H:%M")
            self.gui.root.after(0, lambda: self.gui.timer_lbl.config(text=f"Letztes Update: {ts}"))

            self.gui.set_status("")
            self.gui.set_finished("Update erfolgreich abgeschlossen.")

        except Exception as e:
            # Abbruch: Fehlermeldung bleibt eingeblendet (kein clear bis zum nächsten Start)
            self.gui.set_status("")
            self.gui.append_error(str(e))
            self.gui.set_finished("Update fehlgeschlagen.")

        finally:
            # Immer: Fortschrittsbalken ausblenden und UI wieder entsperren
            self.gui.hide_progress()
            self.gui.set_busy(False)