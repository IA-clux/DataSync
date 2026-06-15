import pystray
from   pystray      import MenuItem as item, Menu
from   PIL          import Image
import tkinter      as tk
import tkinter.font as tkfont
from   tkinter      import scrolledtext
from   tkinter      import ttk
import ctypes
from   ctypes       import wintypes
from   datetime     import datetime
import os
import sys

class GUI:

    def __init__(
        self,
        controller,
        height: int = 600,
        width: int  = 250
    ):
        self.controller = controller

        self.height = height
        self.width  = width

        self._build_root()
        self._build_body()
        self._build_progress_frame()
        self._build_footer()
        self._build_tray_icon()

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

        # Root Geometry Settings
        screenwidth  = self.root.winfo_screenwidth()
        screenheight = self.root.winfo_screenheight()
        taskbar_height = get_taskbar_height()
        self.root.geometry(f"{self.width}x{self.height}+{screenwidth-self.width-10}+{screenheight - self.height - taskbar_height - 10}")
        self.root.overrideredirect(True)

        self.root.bind("<FocusOut>", self._on_focus_out)

        self.root.rowconfigure(0, weight = 100)
        self.root.columnconfigure(0, weight = 1)
        
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
            value=self.controller.SETTINGS.get("username", "")
        )
        self.tk_username.trace_add(
            "write",
            lambda *_: self._store_setting("username", self.tk_username.get())
        )

        tk.Entry(
            self.credentials_frame,
            textvariable=self.tk_username,
            width=28,
            bg="#575757",
            fg="white",
            insertbackground="white",
            bd = 2,
            relief="sunken"
        ).grid(column=0, row=2, columnspan=2, pady=(0, 8))

        tk.Label(
            self.credentials_frame,
            text="Passwort",
            bg="white",
            anchor="w"
        ).grid(column=0, row=3, sticky="w")

        self.tk_password = tk.StringVar(
            value=self.controller.SETTINGS.get("password", "")
        )
        self.tk_password.trace_add(
            "write",
            lambda *_: self._store_setting("password", self.tk_password.get())
        )

        tk.Entry(
            self.credentials_frame,
            textvariable=self.tk_password,
            width=28,
            bg="#575757",
            fg="white",
            insertbackground="white",
            bd = 2,
            relief="sunken",
            show="*"
        ).grid(column=0, row=4, columnspan=2, pady=(0, 8))

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

        tk.Entry(
            self.credentials_frame,
            textvariable=self.tk_organisation,
            width=28,
            bg="#575757",
            fg="white",
            insertbackground="white",
            bd = 2,
            relief="sunken"
        ).grid(column=0, row=6, columnspan=2)

    def _build_body(self):

        self.body = tk.Frame(self.root, bg="white", bd=2, relief="raised", highlightthickness=2 ,highlightbackground= "#575757")
        self.body.grid(column=0,row=0,sticky="nsew")
        self.body.grid_propagate(False)

        self.body.columnconfigure(0, weight=100)
        self.body.rowconfigure(3, weight=100)

        self._build_credentials_frame()

        self.force_update_btn = tk.Button(self.body, bg = "#40FF40",activebackground = "#40FF40", text = "Jetzt Updaten", command = self.controller.update_now)
        self.force_update_btn.grid(column=0,row=1,sticky="n", pady=10,padx=10)

        def _on_mousewheel(event):
            event.widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.error_msg = tk.Text(self.body, height = 4, fg = "red", font = tkfont.Font(family="Arial", size=10, slant="italic"), wrap="word", bd = 0)
        self.error_msg.config(state="disabled")

        self.error_msg.bind("<MouseWheel>", _on_mousewheel)       # Windows & Linux
        self.error_msg.bind("<Button-4>", lambda e: self.error_msg.yview_scroll(-1, "units"))  # Linux
        self.error_msg.bind("<Button-5>", lambda e: self.error_msg.yview_scroll(1, "units"))   # Linux

        self.error_msg.grid(column=0, row=2, sticky="n", pady=10, padx=10)

    def _build_progress_frame(self):

        # Container
        self.progress_frame = tk.Frame(self.body, bg = "white")
        self.progress_frame.grid(column = 0, row = 3, sticky = "nsew", padx = 10, pady = 10)

        # Customer Data Progress Announcement
        self.customer_progress_lbl = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.customer_progress_lbl.grid(column = 0, row = 0, sticky = "w", padx = 2, pady = 2)
        self.customer_progress = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.customer_progress.grid(column = 1, row = 0, sticky = "w", padx = 2, pady = 2)

        # Employees Data Progress Announcement
        self.employees_progress_lbl = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.employees_progress_lbl.grid(column = 0, row = 1, sticky = "w", padx = 2, pady = 2)
        self.employees_progress = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.employees_progress.grid(column = 1, row = 1, sticky = "w", padx = 2, pady = 2)

        # Insurances Data Progress Announcement
        self.insurances_progress_lbl = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.insurances_progress_lbl.grid(column = 0, row = 2, sticky = "w", padx = 2, pady = 2)
        self.insurances_progress = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.insurances_progress.grid(column = 1, row = 2, sticky = "w", padx = 2, pady = 2)

        # Receipts Data Progress Announcement
        self.receipts_progress_lbl = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.receipts_progress_lbl.grid(column = 0, row = 3, sticky = "w", padx = 2, pady = 2)
        self.receipts_progress = tk.Label(self.progress_frame, bg = "white", fg = "black", text = "")
        self.receipts_progress.grid(column = 1, row = 3, sticky = "w", padx = 2, pady = 2)

        self.finished_lbl = tk.Label(self.progress_frame, bg = "white", fg = "grey", text = "")
        self.finished_lbl.grid(column = 0, columnspan=2, row = 4, sticky = "w", padx = 2, pady= 10)

    def _build_footer(self):

        self.footer = tk.Frame(self.body, bg="#575757", bd=2, relief = "sunken")
        self.footer.grid(column=0,row=4,sticky="nsew", padx = 0, pady = 0)

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
