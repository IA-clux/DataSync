from .GUI       import GUI
from .Fetcher   import *

from threading import Thread
from pathlib   import Path
from datetime  import datetime
import json
import os

from Project.OAuth.oauth_listener_runner import OAuthListenerRunner
from Project.OAuth.OAuth_generate_pkce_pair import generate_pkce_pair
from Project.OAuth.OAuth_build_authorization_url import build_authorization_url
from Project.OAuth.OAuth_token_exchange import exchange_code_for_token
from Project.OAuth.Selenium_authorize import selenium_oauth_login


class Controller:

    _SHAREPOINT_PATH = Path.home() / "Ihre Alltagsbegleiter" / "Ihre Alltagsbegleiter - Dokumente"
    _DATABASE_PATH   = _SHAREPOINT_PATH / "Datenbank"

    _LOCAL_APPDATA_PATH = Path(os.getenv("APPDATA")) / "Ihre Alltagsbegleiter" / "AlldayCareFetcher"
    _SETTINGS_PATH = _LOCAL_APPDATA_PATH / "Fetcher_Settings.txt"

    _DEFAULT_SETTINGS = {
        "username": "",
        "password": "",
        "organisation": "",
        "last_updated": None
    }

    SETTINGS: dict = {}

    def __init__(self):

        self.running = False

        if not self._SHAREPOINT_PATH.exists():
            raise FileNotFoundError(
                "Fehler beim Starten der Datenbank-Dienste.\n " \
                "Bitte synchronisieren Sie den Sharepoint mit diesem PC und starten Sie das Programm manuell erneut.")
        
        self._LOCAL_APPDATA_PATH.mkdir(parents=True, exist_ok=True)
        self._DATABASE_PATH.mkdir(parents=True, exist_ok=True)

        self._load_settings()

        self.gui: GUI = GUI(controller = self)

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

        # --- 1) Button sofort deaktivieren ---
        self.gui.root.after(0, lambda: self.gui.force_update_btn.config(state="disabled"))

        # --- 2) UI vorher resetten ---
        def prepare_ui():
            self.gui.error_msg.config(state="normal")
            self.gui.error_msg.delete("1.0", "end")
            self.gui.error_msg.config(state="disabled")

            self.gui.customer_progress_lbl.config(text="Lade Kundendaten:")
            self.gui.employees_progress_lbl.config(text="")
            self.gui.insurances_progress_lbl.config(text="")
            self.gui.receipts_progress_lbl.config(text="")

            self.gui.customer_progress.config(text="")
            self.gui.employees_progress.config(text="")
            self.gui.insurances_progress.config(text="")
            self.gui.receipts_progress.config(text="")

            self.gui.finished_lbl.config(text="")

        self.gui.root.after(0, prepare_ui)

        # --- 3) Hintergrund-Thread für das Update ---
        def worker():
            try:
                time_before_data_pull = datetime.now()
                verifier, challenge = generate_pkce_pair()
                auth_url = build_authorization_url(challenge)

                # ✅ 1) Listener starten (NICHT blockierend)
                listener = OAuthListenerRunner()
                listener.start()

                # ✅ 2) Selenium triggert OAuth-Redirect
                selenium_oauth_login(
                    log          = self.gui.error_msg,
                    auth_url     = auth_url,
                    username     = self.SETTINGS["username"],
                    password     = self.SETTINGS["password"],
                    organisation = self.SETTINGS["organisation"],
                    debug_mode   = True
                )

                # ✅ 3) Jetzt auf den Redirect warten
                code = listener.wait_for_code()
                token = exchange_code_for_token(code, verifier)
                print() # Hold Console clean!
                data = fetch_all_entities(
                    controller = self, 
                    token      = token)
                
                time_after_data_pull = datetime.now()
                time_needed_to_pull_data = time_after_data_pull - time_before_data_pull
                output_str = f"{time_needed_to_pull_data.days} Tage, {time_needed_to_pull_data.seconds//3600} Std, {(time_needed_to_pull_data.seconds//60)%60} Min, {time_needed_to_pull_data.seconds%60} Sek"
                print(f"Time needed to pull Data from AlldayCare: {output_str}", end = "\n\n")

                # Push to SQL
                push_to_sqlite(self._DATABASE_PATH, data)

                # Push to SP and measure time needed
                time_before_sp_push = datetime.now()
                push_to_sharepoint(data)
                time_after_sp_push = datetime.now()
                time_required_for_sharepoint_push = time_after_sp_push - time_before_sp_push
                output_str = f"{time_required_for_sharepoint_push.days} Tage, {time_required_for_sharepoint_push.seconds//3600} Std, {(time_required_for_sharepoint_push.seconds//60)%60} Min, {time_required_for_sharepoint_push.seconds%60} Sek"
                print(f"Time needed to synchronize Data to Sharepoint: {output_str}", end = "\n\n")

                # Erfolg: Timestamp aktualisieren
                self.SETTINGS["last_updated"] = datetime.now()
                self.save_settings()
                ts = self.SETTINGS["last_updated"].strftime("%d.%m.%Y %H:%M")
                self.gui.root.after(0, lambda: self.gui.timer_lbl.config(text=f"Letztes Update: {ts}"))

            except Exception as e:
                err = str(e)
                def write_error():
                    self.gui.error_msg.config(state="normal")
                    self.gui.error_msg.insert("end", err)
                    self.gui.error_msg.config(state="disabled")
                self.gui.root.after(0, write_error)

            finally:
                # --- 4) Button wieder aktivieren & Endmeldung ausgeben ---
                self.gui.root.after(0, lambda: self.gui.force_update_btn.config(state="normal"))
                self.gui.root.after(0, lambda: self.gui.finished_lbl.config(text = "Prozess Beendet."))

        Thread(target=worker, daemon=True).start()