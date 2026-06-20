import pystray
from   pystray      import MenuItem as item, Menu
from   PIL          import Image
import tkinter      as tk
import tkinter.font as tkfont
from   tkinter      import scrolledtext
from   tkinter      import ttk
from   tkinter      import filedialog
import ctypes
from   ctypes       import wintypes
from   datetime     import datetime
import os
import sys

class GUI:

    def __init__(
        self,
        controller,
        width: int = 250
    ):
        self.controller = controller

        self.width = width

        self._build_root()
        self._build_body()
        self._build_progress_frame()
        self._build_footer()
        self._build_tray_icon()

        # Fenstergröße/-position erst nach dem Aufbau am echten Platzbedarf ausrichten
        self._apply_geometry()

        self.root.withdraw()
        self.window_visible = False

    def _store_setting(self, key: str, value: str):
        self.controller.SETTINGS[key] = value
        self.controller.save_settings()

    def _build_root(self):

        def get_taskbar_height():
            # Windows RECT-Struktur
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            SPI_GETWORKAREA = 0x0030
            rect = RECT()

            # Work-Area von Windows holen
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETWORKAREA,
                0,
                ctypes.byref(rect),
                0
            )

            # Bildschirmgröße
            screen_w = ctypes.windll.user32.GetSystemMetrics(0)
            screen_h = ctypes.windll.user32.GetSystemMetrics(1)

            work_w = rect.right - rect.left
            work_h = rect.bottom - rect.top

            # Differenzen bestimmen
            taskbar_height = screen_h - work_h
            taskbar_width  = screen_w - work_w

            return taskbar_height

        self.root = tk.Tk()

        self.root.config(bg="white")

        # Breite ist fix; Höhe und Position werden in _apply_geometry aus dem
        # tatsächlichen Platzbedarf der Inhalte abgeleitet (vorerst nur Platzhalter).
        self._taskbar_height = get_taskbar_height()
        self.root.geometry(f"{self.width}x1")
        self.root.overrideredirect(True)

        self.root.bind("<FocusOut>", self._on_focus_out)

        self.root.rowconfigure(0, weight = 100)
        self.root.columnconfigure(0, weight = 1)

    def _apply_geometry(self):
        """Richtet Höhe und Position am tatsächlichen Platzbedarf der Inhalte aus.

        Die Höhe wird inklusive eingeblendeter Progressbar (Worst Case) gemessen,
        damit das spätere Ein-/Ausblenden das Layout nicht sprengt.
        """
        # Worst-Case-Layout für die Messung herstellen (Balken sichtbar)
        self.progress_bar.grid()
        self.progress_pct_lbl.grid()

        self.root.update_idletasks()
        needed_height = self.root.winfo_reqheight()

        # Zurück in den Ausgangszustand (Balken wieder ausgeblendet)
        self.progress_bar.grid_remove()
        self.progress_pct_lbl.grid_remove()

        screenwidth  = self.root.winfo_screenwidth()
        screenheight = self.root.winfo_screenheight()

        x = screenwidth  - self.width        - 10
        y = screenheight - needed_height     - self._taskbar_height - 10

        self.root.geometry(f"{self.width}x{needed_height}+{x}+{y}")

        # Größe fixieren, damit das Ein-/Ausblenden des Balkens keine Sprünge erzeugt
        self.root.update_idletasks()
        self.body.grid_propagate(False)

    def _build_credentials_frame(self):
        self.credentials_frame = tk.Frame(
            self.body,
            bg="white"
        )
        self.credentials_frame.grid(
            column=0,
            row=0,
            sticky="n",
            padx=10,
            pady=(10, 5)
        )

        # ---------- Titel ----------
        tk.Label(
            self.credentials_frame,
            text="Zugangsdaten",
            bg="white",
            fg="black",
            font=("Arial", 11, "bold")
        ).grid(column=0, row=0, columnspan=2, pady=(0, 10))

        tk.Label(
            self.credentials_frame,
            text="Benutzername / E-Mail",
            bg="white",
            anchor="w"
        ).grid(column=0, row=1, sticky="w")

        self.tk_username = tk.StringVar(
            value=self.controller.get_credential("username")
        )
        self.tk_username.trace_add(
            "write",
            lambda *_: self.controller.set_credential("username", self.tk_username.get())
        )

        self.username_entry = tk.Entry(
            self.credentials_frame,
            textvariable=self.tk_username,
            width=28,
            bg="#575757",
            fg="white",
            disabledbackground="#3a3a3a",
            disabledforeground="#aaaaaa",
            insertbackground="white",
            bd = 2,
            relief="sunken"
        )
        self.username_entry.grid(column=0, row=2, columnspan=2, pady=(0, 8))

        tk.Label(
            self.credentials_frame,
            text="Passwort",
            bg="white",
            anchor="w"
        ).grid(column=0, row=3, sticky="w")

        self.tk_password = tk.StringVar(
            value=self.controller.get_credential("password")
        )
        self.tk_password.trace_add(
            "write",
            lambda *_: self.controller.set_credential("password", self.tk_password.get())
        )

        self.password_entry = tk.Entry(
            self.credentials_frame,
            textvariable=self.tk_password,
            width=28,
            bg="#575757",
            fg="white",
            disabledbackground="#3a3a3a",
            disabledforeground="#aaaaaa",
            insertbackground="white",
            bd = 2,
            relief="sunken",
            show="*"
        )
        self.password_entry.grid(column=0, row=4, columnspan=2, pady=(0, 8))

        tk.Label(
            self.credentials_frame,
            text="Organisation / Mandant",
            bg="white",
            anchor="w"
        ).grid(column=0, row=5, sticky="w")

        self.tk_organisation = tk.StringVar(
            value=self.controller.SETTINGS.get("organisation", "")
        )
        self.tk_organisation.trace_add(
            "write",
            lambda *_: self._store_setting("organisation", self.tk_organisation.get())
        )

        self.organisation_entry = tk.Entry(
            self.credentials_frame,
            textvariable=self.tk_organisation,
            width=28,
            bg="#575757",
            fg="white",
            disabledbackground="#3a3a3a",
            disabledforeground="#aaaaaa",
            insertbackground="white",
            bd = 2,
            relief="sunken"
        )
        self.organisation_entry.grid(column=0, row=6, columnspan=2)

    def _build_body(self):

        self.body = tk.Frame(self.root, bg="white", bd=2, relief="raised", highlightthickness=2 ,highlightbackground= "#575757")
        self.body.grid(column=0,row=0,sticky="nsew")

        self.body.columnconfigure(0, weight=100)
        # Bei zusätzlichem vertikalem Platz wächst der Log (Zeile 3), nicht der
        # ansonsten fast leere Fortschritts-Bereich.
        self.body.rowconfigure(3, weight=100)

        self._build_credentials_frame()
        self._build_db_options_frame()

        self.force_update_btn = tk.Button(self.body, bg = "#40FF40",activebackground = "#40FF40", text = "Jetzt Updaten", command = self.controller.update_now)
        self.force_update_btn.grid(column=0,row=2,sticky="n", pady=(10, 0),padx=10)

        def _on_mousewheel(event):
            event.widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.error_msg = tk.Text(self.body, height = 4, fg = "red", font = tkfont.Font(family="Arial", size=10, slant="italic"), wrap="word", bd = 0)
        self.error_msg.config(state="disabled")

        self.error_msg.bind("<MouseWheel>", _on_mousewheel)       # Windows & Linux
        self.error_msg.bind("<Button-4>", lambda e: self.error_msg.yview_scroll(-1, "units"))  # Linux
        self.error_msg.bind("<Button-5>", lambda e: self.error_msg.yview_scroll(1, "units"))   # Linux

        # ~20 px über und unter dem Log trennen ihn sauber von Button und Fortschritt.
        # sticky="nsew" + Zeilengewicht: der Log nimmt zusätzlichen Platz auf.
        self.error_msg.grid(column=0, row=3, sticky="nsew", pady=20, padx=10)

    def _build_db_options_frame(self):
        """Optionaler lokaler Datenbank-Abzug: Checkbox + frei wählbarer Ablageort."""
        self.db_frame = tk.Frame(self.body, bg="white")
        self.db_frame.grid(column=0, row=1, sticky="n", padx=10, pady=(8, 0))
        self.db_frame.columnconfigure(0, weight=1)

        self.tk_db_enabled = tk.BooleanVar(
            value=bool(self.controller.SETTINGS.get("db_enabled", False))
        )
        self.tk_db_enabled.trace_add("write", lambda *_: self._on_db_enabled_changed())

        self.db_check = tk.Checkbutton(
            self.db_frame,
            text="Lokalen Datenbank-Abzug speichern",
            variable=self.tk_db_enabled,
            bg="white",
            activebackground="white",
            anchor="w",
        )
        self.db_check.grid(column=0, row=0, sticky="w")

        self.db_path_lbl = tk.Label(
            self.db_frame,
            bg="white",
            fg="#555555",
            anchor="w",
            justify="left",
            wraplength=210,
        )
        self.db_path_lbl.grid(column=0, row=1, sticky="w", pady=(4, 0))

        self.db_path_btn = tk.Button(
            self.db_frame,
            text="Ablageort wählen…",
            command=self._choose_db_path,
        )
        self.db_path_btn.grid(column=0, row=2, sticky="w", pady=(4, 0))

        self._refresh_db_path_label()
        self._update_db_widgets_state()

    def _on_db_enabled_changed(self):
        self.controller.SETTINGS["db_enabled"] = bool(self.tk_db_enabled.get())
        self.controller.save_settings()
        self._update_db_widgets_state()

    def _choose_db_path(self):
        path = filedialog.askdirectory(
            title="Ablageort für den Datenbank-Abzug wählen"
        )
        if path:
            self.controller.SETTINGS["db_path"] = path
            self.controller.save_settings()
            self._refresh_db_path_label()

    def _refresh_db_path_label(self):
        path = self.controller.SETTINGS.get("db_path", "")
        self.db_path_lbl.config(
            text=f"Ablageort: {path}" if path else "Kein Ablageort gewählt"
        )

    def _update_db_widgets_state(self):
        state = "normal" if self.tk_db_enabled.get() else "disabled"
        self.db_path_btn.config(state=state)

    def _build_progress_frame(self):

        # Container
        self.progress_frame = tk.Frame(self.body, bg = "white")
        self.progress_frame.grid(column = 0, row = 4, sticky = "nsew", padx = 10, pady = (0, 10))
        self.progress_frame.columnconfigure(0, weight = 1)

        # Aktueller Zwischenschritt
        self.status_lbl = tk.Label(
            self.progress_frame, bg = "white", fg = "black",
            text = "", anchor = "w", justify = "left", wraplength = 210
        )
        self.status_lbl.grid(column = 0, row = 0, columnspan = 2, sticky = "w", padx = 2, pady = (2, 6))

        # Fortschrittsbalken (nur während Down-/Upload sichtbar)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, orient = "horizontal",
            length = 180, mode = "determinate", maximum = 100
        )
        self.progress_bar.grid(column = 0, row = 1, sticky = "we", padx = 2, pady = 2)

        self.progress_pct_lbl = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.progress_pct_lbl.grid(column = 1, row = 1, sticky = "w", padx = (6, 2), pady = 2)

        # Initial ausgeblendet
        self.progress_bar.grid_remove()
        self.progress_pct_lbl.grid_remove()

        # Endmeldung
        self.finished_lbl = tk.Label(self.progress_frame, bg = "white", fg = "grey", text = "")
        self.finished_lbl.grid(column = 0, columnspan = 2, row = 2, sticky = "w", padx = 2, pady = 10)

    # -----------------------------------------------------------------------------
    # Thread-sichere Fortschritts-/Status-API (aus Worker-Threads aufrufbar)
    # -----------------------------------------------------------------------------

    def _ui(self, fn):
        """Führt fn thread-sicher im Tk-Mainloop aus."""
        self.root.after(0, fn)

    def set_status(self, text: str):
        self._ui(lambda: self.status_lbl.config(text = text))

    def set_finished(self, text: str):
        self._ui(lambda: self.finished_lbl.config(text = text))

    def set_progress(self, current: int, total: int):
        def _do():
            if total <= 0:
                return
            pct = max(0, min(100, int(100 * current / total)))
            self.progress_bar.grid()
            self.progress_pct_lbl.grid()
            self.progress_bar.config(value = pct)
            self.progress_pct_lbl.config(text = f"{pct}%")
        self._ui(_do)

    def hide_progress(self):
        def _do():
            self.progress_bar.config(value = 0)
            self.progress_pct_lbl.config(text = "")
            self.progress_bar.grid_remove()
            self.progress_pct_lbl.grid_remove()
        self._ui(_do)

    def show_error(self, message: str):
        """Ersetzt den Inhalt der Fehleranzeige."""
        def _do():
            self.error_msg.config(state = "normal")
            self.error_msg.delete("1.0", "end")
            self.error_msg.insert("end", message)
            self.error_msg.config(state = "disabled")
        self._ui(_do)

    def append_error(self, message: str):
        """Hängt eine Zeile an die Fehler-/Loganzeige an."""
        def _do():
            self.error_msg.config(state = "normal")
            self.error_msg.insert("end", message + "\n")
            self.error_msg.see("end")
            self.error_msg.config(state = "disabled")
        self._ui(_do)

    def clear_error(self):
        def _do():
            self.error_msg.config(state = "normal")
            self.error_msg.delete("1.0", "end")
            self.error_msg.config(state = "disabled")
        self._ui(_do)

    def set_busy(self, busy: bool):
        """Sperrt/entsperrt Update-Button und Eingabefelder während des Syncs."""
        state = "disabled" if busy else "normal"
        def _do():
            self.force_update_btn.config(state = state)
            for entry in (self.username_entry, self.password_entry, self.organisation_entry):
                entry.config(state = state)
            self.db_check.config(state = state)
            if busy:
                self.db_path_btn.config(state = "disabled")
            else:
                self._update_db_widgets_state()
        self._ui(_do)

    def reset_progress(self):
        def _do():
            self.status_lbl.config(text = "")
            self.finished_lbl.config(text = "")
            self.progress_bar.config(value = 0)
            self.progress_pct_lbl.config(text = "")
            self.progress_bar.grid_remove()
            self.progress_pct_lbl.grid_remove()
        self._ui(_do)

    def _build_footer(self):

        self.footer = tk.Frame(self.body, bg="#575757", bd=2, relief = "sunken")
        self.footer.grid(column=0,row=5,sticky="nsew", padx = 0, pady = 0)

        last_updated = self.controller.SETTINGS["last_updated"]
        if not last_updated:
            last_update_str = ""
        elif isinstance(last_updated, datetime):
            last_update_str = last_updated.strftime("%d.%m.%Y | %H:%M")

        self.timer_lbl = tk.Label(self.footer,bg ="#575757", fg = "white", text = f"Letztes Update: {last_update_str}", font = ("Arial", 10))
        self.timer_lbl.grid(column=0,row=0,sticky="s", padx=2)

    def _build_tray_icon(self):

        def resource_path(relative_path):
            if hasattr(sys, "_MEIPASS"):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_path, relative_path)

        image = Image.open(resource_path(r"ico.ico"))

        self.tray_icon = pystray.Icon(
            "AlldayCare_API",
            image,
            "AlldayCare API",
            menu = Menu(
                item("Anzeigen", self._on_show, default=True),
                item("Beenden", self._on_quit)))

    def _on_show(self, icon = None, menu_item = None):
        self.root.after(0, self._show_window_safe)

    def _show_window_safe(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.window_visible = True

    def _on_focus_out(self, event):
        focused = self.root.focus_get()

        # Fall 1: Fenster ist sichtbar & Fokus ist noch irgendwo im Fenster
        if focused is not None and str(focused).startswith(str(self.root)):
            return  # NICHT schließen

        # Fall 2: Fokus liegt außerhalb → Fenster schließen
        if self.window_visible:
            self.root.withdraw()
            self.window_visible = False

    def _on_quit(self, icon, menu_item):
        def _quit():
            icon.stop()
            self.root.destroy()
            self.controller.running = False
        self.root.after(0, _quit)
