# -*- coding: utf-8 -*-
"""
Bot Margonem – aplikacja okienkowa do zarządzania botem.
- Logowanie z zapisem i automatycznym loginem (AppData).
- Zakładka Debug: sterowanie postacią z poziomu Pythona (idź, atakuj po nazwie, rozmawiaj).
"""
import random
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import uuid

import config_credentials as creds
from margonem_api import MargonemAPI
from maps_graph import (
    find_map_ids_by_name,
    bfs_path,
    get_map_name_by_id,
    get_maps_with_npc,
    get_maps_with_npc_by_distance,
    get_neighbor_map_ids,
)
from captcha_solver import check_and_solve_captcha_once, ensure_no_captcha

# Import przeglądarki dopiero przy uruchomieniu
_driver = None
_captcha_watcher_stop = None
_captcha_gave_up = False

MARGONEM_URL = "https://www.margonem.pl/"
XPATH_LINK_LOGOWANIE = "/html/body/div[3]/div[4]/div/p[2]/a"
XPATH_INPUT_LOGIN = "/html/body/div[3]/div/div[1]/div/div[2]/div[1]/form/div[1]/input"
XPATH_INPUT_HASLO = "/html/body/div[3]/div/div[1]/div/div[2]/div[1]/form/div[2]/input"
XPATH_BUTTON_ZALOGUJ = "/html/body/div[3]/div/div[1]/div/div[2]/div[1]/form/button"


def _human_delay(min_s=0.3, max_s=0.8):
    time.sleep(random.uniform(min_s, max_s))


def _create_browser():
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options, version_main=144)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        })
    except Exception:
        pass
    return driver


def run_login_flow(driver, login: str, password: str, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
    try:
        log("Otwieram Margonem...")
        driver.get(MARGONEM_URL)
        _human_delay(1.2, 2.0)
        log("Klikam link logowania...")
        link = driver.find_element("xpath", XPATH_LINK_LOGOWANIE)
        link.click()
        _human_delay(0.8, 1.5)
        log("Wpisuję login...")
        inp_login = driver.find_element("xpath", XPATH_INPUT_LOGIN)
        inp_login.clear()
        for c in login:
            inp_login.send_keys(c)
            _human_delay(0.03, 0.08)
        _human_delay(0.2, 0.5)
        log("Wpisuję hasło...")
        inp_haslo = driver.find_element("xpath", XPATH_INPUT_HASLO)
        inp_haslo.clear()
        for c in password:
            inp_haslo.send_keys(c)
            _human_delay(0.03, 0.08)
        _human_delay(0.2, 0.5)
        log("Klikam Zaloguj...")
        btn = driver.find_element("xpath", XPATH_BUTTON_ZALOGUJ)
        btn.click()
        log("Zalogowano. Możesz przełączyć się do przeglądarki i dołączyć do gry.")
    except Exception as e:
        log("Błąd: " + str(e))
        raise


def get_driver():
    return _driver


_captcha_log_callback = None
_auto_captcha_enabled = True  # włącz/wyłącz w zakładce Auto


def set_driver(d, log_callback=None):
    global _driver, _captcha_watcher_stop, _captcha_gave_up, _captcha_log_callback
    _driver = d
    _captcha_gave_up = False
    _captcha_log_callback = log_callback
    if d and _captcha_watcher_stop is not None:
        _captcha_watcher_stop.set()
    if d:
        _start_captcha_watcher(d)


def _captcha_watcher_loop(driver, stop_event):
    """W tle co 2.5 s sprawdza captcha; gdy „próby” < 2 – przestaje próbować."""
    global _captcha_gave_up, _captcha_log_callback, _auto_captcha_enabled
    import time
    while not stop_event.wait(timeout=2.5):
        if _captcha_gave_up or not _auto_captcha_enabled:
            continue
        try:
            def log_cb(msg):
                if _captcha_log_callback:
                    _captcha_log_callback(msg)
            r = ensure_no_captcha(driver, log_callback=log_cb)
            if r == "skipped_tries":
                _captcha_gave_up = True
                if _captcha_log_callback:
                    _captcha_log_callback("Anty-captcha: pozostało < 2 prób – dalsze rozwiązywanie wyłączone.")
        except Exception as e:
            if _captcha_log_callback:
                _captcha_log_callback("Captcha watcher: " + str(e))


def _start_captcha_watcher(driver):
    """Uruchamia wątek pilnujący captchy (wywoływane po ustawieniu drivera)."""
    global _captcha_watcher_stop
    _captcha_watcher_stop = threading.Event()
    t = threading.Thread(
        target=_captcha_watcher_loop,
        args=(driver, _captcha_watcher_stop),
        daemon=True,
    )
    t.start()


# --- Okno logowania ---

class LoginDialog:
    def __init__(self, parent=None):
        self.result = None
        self.root = tk.Tk() if parent is None else tk.Toplevel(parent)
        self.root.title("Logowanie – Margonem Bot")
        self.root.resizable(False, False)
        self._build()
        self._load_saved()
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build(self):
        f = ttk.Frame(self.root, padding=12)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="Login:").grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self._login_var = tk.StringVar()
        self._login_entry = ttk.Entry(f, textvariable=self._login_var, width=28)
        self._login_entry.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        ttk.Label(f, text="Hasło:").grid(row=2, column=0, sticky=tk.W, pady=(0, 4))
        self._password_var = tk.StringVar()
        self._password_entry = ttk.Entry(f, textvariable=self._password_var, width=28, show="*")
        self._password_entry.grid(row=3, column=0, sticky=tk.EW, pady=(0, 10))
        self._save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Zapamiętaj login i hasło (zapis w AppData)", variable=self._save_var).grid(
            row=4, column=0, sticky=tk.W, pady=(0, 12)
        )
        btn_f = ttk.Frame(f)
        btn_f.grid(row=5, column=0, sticky=tk.EW)
        ttk.Button(btn_f, text="Anuluj", command=self._on_cancel).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_f, text="Zaloguj", command=self._on_ok).pack(side=tk.RIGHT)
        f.columnconfigure(0, weight=1)
        self.root.geometry("320x200")
        self._password_entry.bind("<Return>", lambda e: self._on_ok())
        self._login_entry.bind("<Return>", lambda e: self._password_entry.focus())

    def _load_saved(self):
        saved = creds.load_credentials()
        if saved:
            self._login_var.set(saved["login"])
            self._password_var.set(saved["password"])

    def _on_ok(self):
        login = (self._login_var.get() or "").strip()
        password = self._password_var.get() or ""
        if not login:
            messagebox.showwarning("Uwaga", "Podaj login.", parent=self.root)
            return
        if not password:
            messagebox.showwarning("Uwaga", "Podaj hasło.", parent=self.root)
            return
        self.result = (login, password, self._save_var.get())
        if self._save_var.get():
            creds.save_credentials(login, password)
        self.root.destroy()

    def _on_cancel(self):
        self.result = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.result


# --- Główne okno z zakładkami ---

class MainWindow:
    def __init__(self, login: str, password: str):
        self.login = login
        self.password = password
        self.root = tk.Tk()
        self.root.title("Margonem Bot – zarządzanie")
        self.root.minsize(500, 400)
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _log_append(self, msg):
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, msg + "\n")
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    def _build(self):
        # Pasek górny – przeglądarka
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)
        self._btn_run = ttk.Button(
            top, text="Uruchom przeglądarkę i zaloguj na Margonem", command=self._run_browser
        )
        self._btn_run.pack(side=tk.LEFT, padx=(0, 8))
        self._status = ttk.Label(top, text="Gotowy.")
        self._status.pack(side=tk.LEFT)

        # Zakładki
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Zakładka: Główna
        tab_main = ttk.Frame(self._notebook, padding=10)
        self._notebook.add(tab_main, text="Główna")
        ttk.Label(tab_main, text="Uruchom przeglądarkę powyżej, zaloguj się, wejdź na postać w grze. Potem użyj zakładki Debug.").pack(anchor=tk.W)
        self._state_label = ttk.Label(tab_main, text="(Stan gry sprawdzisz w zakładce Debug.)")
        self._state_label.pack(anchor=tk.W, pady=(8, 0))

        # Zakładka: Debug
        tab_debug = ttk.Frame(self._notebook, padding=10)
        self._notebook.add(tab_debug, text="Debug")
        self._build_debug_tab(tab_debug)

        # Zakładka: Auto (captcha + autoheal)
        tab_auto = ttk.Frame(self._notebook, padding=10)
        self._notebook.add(tab_auto, text="Auto")
        self._build_auto_tab(tab_auto)

        # Wspólny log na dole
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._log = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 9))
        self._log.pack(fill=tk.BOTH, expand=True)

    def _debug_accordion_toggle(self, index):
        """Rozwija sekcję o danym indeksie, zwija pozostałe. Klik w rozwiniętą zwija ją."""
        titles = self._debug_accordion_titles
        if index == self._debug_accordion_expanded:
            # Klik w już rozwiniętą – zwiń
            self._debug_accordion_sections[index][1].pack_forget()
            self._debug_accordion_sections[index][0].config(text="▶ " + titles[index])
            self._debug_accordion_expanded = -1
            return
        for i, (btn, body) in enumerate(self._debug_accordion_sections):
            if i == index:
                body.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
                btn.config(text="▼ " + titles[i])
            else:
                body.pack_forget()
                btn.config(text="▶ " + titles[i])
        self._debug_accordion_expanded = index

    def _build_debug_tab(self, parent):
        self._processes = {}  # process_id -> {name, cancel, pause, target_map_id, target_map_name, enemy_name, attack_loop}
        self._process_queue = []  # kolejka process_id (tylko ataki)
        self._current_process_id = None  # aktualnie wykonywany (gwiazdka)

        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        left_f = ttk.Frame(paned, padding=(0, 0, 8, 0))
        paned.add(left_f, weight=1)
        right_f = ttk.Frame(paned, width=220)
        paned.add(right_f, weight=0)

        # === Lewa kolumna: accordion (rozwijane sekcje, tylko jedna na raz) ===
        accordion_root = ttk.Frame(left_f)
        accordion_root.pack(fill=tk.BOTH, expand=True)
        self._debug_accordion_titles = [
            "Status gry",
            "Idź do (x, y)",
            "Atak – mapy z przeciwnikami",
            "Rozmawiaj z NPC",
            "Idź na mapę (BFS)",
            "Mapa / NPC",
        ]
        self._debug_accordion_sections = []
        self._debug_accordion_expanded = 0

        # --- 1. Status gry ---
        sec1_f = ttk.Frame(accordion_root)
        sec1_f.pack(fill=tk.X, pady=(0, 2))
        btn1 = ttk.Button(sec1_f, text="▼ " + self._debug_accordion_titles[0], command=lambda: self._debug_accordion_toggle(0))
        btn1.pack(fill=tk.X)
        body1 = ttk.LabelFrame(sec1_f, text="", padding=8)
        self._debug_status_text = tk.StringVar(value="Kliknij 'Odśwież status', gdy postać jest w grze.")
        ttk.Label(body1, textvariable=self._debug_status_text).pack(anchor=tk.W)
        ttk.Button(body1, text="Odśwież status", command=self._debug_refresh_status).pack(anchor=tk.W, pady=(4, 0))
        self._debug_accordion_sections.append((btn1, body1))

        # --- 2. Idź do (x, y) ---
        sec2_f = ttk.Frame(accordion_root)
        sec2_f.pack(fill=tk.X, pady=(0, 2))
        btn2 = ttk.Button(sec2_f, text="▶ " + self._debug_accordion_titles[1], command=lambda: self._debug_accordion_toggle(1))
        btn2.pack(fill=tk.X)
        body2 = ttk.Frame(sec2_f, padding=8)
        row = ttk.Frame(body2)
        row.pack(anchor=tk.W)
        ttk.Label(row, text="X:").pack(side=tk.LEFT, padx=(0, 4))
        self._debug_x_var = tk.StringVar(value="0")
        ttk.Entry(row, textvariable=self._debug_x_var, width=6).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row, text="Y:").pack(side=tk.LEFT, padx=(0, 4))
        self._debug_y_var = tk.StringVar(value="0")
        ttk.Entry(row, textvariable=self._debug_y_var, width=6).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(row, text="Idź", command=self._debug_go_xy).pack(side=tk.LEFT)
        self._debug_accordion_sections.append((btn2, body2))

        # --- 3. Atak – mapy z przeciwnikami ---
        sec3_f = ttk.Frame(accordion_root)
        sec3_f.pack(fill=tk.X, pady=(0, 2))
        btn3 = ttk.Button(sec3_f, text="▶ " + self._debug_accordion_titles[2], command=lambda: self._debug_accordion_toggle(2))
        btn3.pack(fill=tk.X)
        body3 = ttk.Frame(sec3_f, padding=8)
        row_atk = ttk.Frame(body3)
        row_atk.pack(fill=tk.X)
        ttk.Label(row_atk, text="Nazwa przeciwnika:").pack(side=tk.LEFT, padx=(0, 6))
        self._debug_attack_name_var = tk.StringVar(value="Szczur")
        ttk.Entry(row_atk, textvariable=self._debug_attack_name_var, width=20).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row_atk, text="Szukaj map", command=self._debug_attack_search_maps).pack(side=tk.LEFT, padx=(0, 12))
        self._debug_attack_loop_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(body3, text="Bij w pętli", variable=self._debug_attack_loop_var).pack(anchor=tk.W, pady=(4, 0))
        atk_scroll_f = ttk.Frame(body3)
        atk_scroll_f.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self._attack_maps_scrollbar = ttk.Scrollbar(atk_scroll_f)
        self._attack_maps_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._attack_maps_canvas = tk.Canvas(atk_scroll_f, yscrollcommand=self._attack_maps_scrollbar.set, highlightthickness=0)
        self._attack_maps_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._attack_maps_scrollbar.config(command=self._attack_maps_canvas.yview)
        self._attack_maps_container = ttk.Frame(self._attack_maps_canvas)
        self._attack_maps_canvas_window = self._attack_maps_canvas.create_window((0, 0), window=self._attack_maps_container, anchor=tk.NW)
        def _on_attack_maps_frame_configure(e):
            self._attack_maps_canvas.configure(scrollregion=self._attack_maps_canvas.bbox("all"))
        def _on_attack_maps_canvas_configure(e):
            self._attack_maps_canvas.itemconfig(self._attack_maps_canvas_window, width=e.width)
        self._attack_maps_container.bind("<Configure>", _on_attack_maps_frame_configure)
        self._attack_maps_canvas.bind("<Configure>", _on_attack_maps_canvas_configure)
        self._attack_maps_canvas.bind("<MouseWheel>", lambda e: self._attack_maps_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        ttk.Label(self._attack_maps_container, text="Wpisz nazwę i „Szukaj map” – klik w mapę: idź i atakuj.").pack(anchor=tk.W)
        self._debug_accordion_sections.append((btn3, body3))

        # --- 4. Rozmawiaj z NPC ---
        sec4_f = ttk.Frame(accordion_root)
        sec4_f.pack(fill=tk.X, pady=(0, 2))
        btn4 = ttk.Button(sec4_f, text="▶ " + self._debug_accordion_titles[3], command=lambda: self._debug_accordion_toggle(3))
        btn4.pack(fill=tk.X)
        body4 = ttk.Frame(sec4_f, padding=8)
        row_talk = ttk.Frame(body4)
        row_talk.pack(anchor=tk.W)
        self._debug_talk_name_var = tk.StringVar(value="")
        ttk.Entry(row_talk, textvariable=self._debug_talk_name_var, width=24).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row_talk, text="Podejdź i rozmawiaj", command=self._debug_talk_by_name).pack(side=tk.LEFT)
        self._debug_accordion_sections.append((btn4, body4))

        # --- 5. Idź na mapę (BFS) ---
        sec5_f = ttk.Frame(accordion_root)
        sec5_f.pack(fill=tk.X, pady=(0, 2))
        btn5 = ttk.Button(sec5_f, text="▶ " + self._debug_accordion_titles[4], command=lambda: self._debug_accordion_toggle(4))
        btn5.pack(fill=tk.X)
        body5 = ttk.Frame(sec5_f, padding=8)
        ttk.Label(body5, text="Obecna mapa odczytana przy starcie nawigacji.").pack(anchor=tk.W)
        row_search = ttk.Frame(body5)
        row_search.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(row_search, text="Szukaj mapy:").pack(side=tk.LEFT, padx=(0, 6))
        self._debug_map_search_var = tk.StringVar(value="")
        self._debug_map_search_var.trace_add("write", lambda *a: self._debug_filter_maps())
        ttk.Entry(row_search, textvariable=self._debug_map_search_var, width=30).pack(side=tk.LEFT, padx=(0, 8))
        list_frame = ttk.Frame(body5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        scroll = ttk.Scrollbar(list_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._debug_maps_listbox = tk.Listbox(list_frame, height=8, yscrollcommand=scroll.set, font=("Consolas", 9))
        self._debug_maps_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self._debug_maps_listbox.yview)
        self._debug_maps_filtered = []
        row_btn = ttk.Frame(body5)
        row_btn.pack(anchor=tk.W)
        ttk.Button(row_btn, text="Idź na mapę", command=self._debug_navigate_to_map).pack(side=tk.LEFT, padx=(0, 8))
        self._debug_filter_maps()
        self._debug_accordion_sections.append((btn5, body5))

        # --- 6. Mapa / NPC ---
        sec6_f = ttk.Frame(accordion_root)
        sec6_f.pack(fill=tk.X, pady=(0, 2))
        btn6 = ttk.Button(sec6_f, text="▶ " + self._debug_accordion_titles[5], command=lambda: self._debug_accordion_toggle(5))
        btn6.pack(fill=tk.X)
        body6 = ttk.Frame(sec6_f, padding=8)
        ttk.Button(body6, text="Wylistuj wszystkich NPC na mapie", command=self._debug_list_npcs).pack(anchor=tk.W)
        self._debug_accordion_sections.append((btn6, body6))

        # Zwijamy wszystkie oprócz pierwszej i pokazujemy tylko pierwszą
        for i in range(len(self._debug_accordion_sections)):
            btn, body = self._debug_accordion_sections[i]
            body.pack_forget()
            btn.config(text=("▼ " if i == 0 else "▶ ") + self._debug_accordion_titles[i])
        self._debug_accordion_sections[0][1].pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        # === Prawa kolumna: Procesy ===
        proc_f = ttk.LabelFrame(right_f, text="Procesy", padding=8)
        proc_f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(proc_f, text="* = wykonywany. Kolejka: najbliższa mapa pierwsza.").pack(anchor=tk.W)
        proc_list_frame = ttk.Frame(proc_f)
        proc_list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        self._process_listbox = tk.Listbox(proc_list_frame, height=12, font=("Consolas", 9), selectmode=tk.SINGLE)
        self._process_listbox.pack(fill=tk.BOTH, expand=True)
        proc_btn_f = ttk.Frame(proc_f)
        proc_btn_f.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(proc_btn_f, text="Wykonaj teraz", command=self._process_run_now).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(proc_btn_f, text="Pauzuj", command=self._process_pause_toggle).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(proc_btn_f, text="Anuluj", command=self._process_cancel).pack(side=tk.LEFT)

    def _build_auto_tab(self, parent):
        """Zakładka Auto: autorozwiązywanie captchy + autoheal z zakresami %."""
        global _auto_captcha_enabled
        main_f = ttk.LabelFrame(parent, text="Automaty", padding=10)
        main_f.pack(fill=tk.X, pady=(0, 10))
        self._auto_captcha_var = tk.BooleanVar(value=_auto_captcha_enabled)
        def on_captcha_toggle():
            global _auto_captcha_enabled
            _auto_captcha_enabled = self._auto_captcha_var.get()
        ttk.Checkbutton(
            main_f,
            text="Autorozwiązywanie zagadek (captcha) – sprawdzanie co ~2.5 s",
            variable=self._auto_captcha_var,
            command=on_captcha_toggle,
        ).pack(anchor=tk.W)
        heal_f = ttk.LabelFrame(parent, text="Autoheal (mikstury z ekwipunku)", padding=10)
        heal_f.pack(fill=tk.X, pady=(0, 10))
        self._autoheal_var = tk.BooleanVar(value=False)
        self._autoheal_stop = threading.Event()
        self._autoheal_thread = None
        row1 = ttk.Frame(heal_f)
        row1.pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(row1, text="Lecz gdy HP poniżej:").pack(side=tk.LEFT, padx=(0, 8))
        self._heal_below_var = tk.StringVar(value="60")
        ttk.Spinbox(row1, from_=1, to=99, width=5, textvariable=self._heal_below_var).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(row1, text="%").pack(side=tk.LEFT)
        row2 = ttk.Frame(heal_f)
        row2.pack(anchor=tk.W, pady=(2, 0))
        ttk.Label(row2, text="Zatrzymaj leczenie gdy HP w zakresie:").pack(side=tk.LEFT, padx=(0, 8))
        self._stop_heal_min_var = tk.StringVar(value="90")
        ttk.Spinbox(row2, from_=1, to=100, width=5, textvariable=self._stop_heal_min_var).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(row2, text="%").pack(side=tk.LEFT)
        ttk.Label(row2, text="–").pack(side=tk.LEFT, padx=(4, 4))
        self._stop_heal_max_var = tk.StringVar(value="100")
        ttk.Spinbox(row2, from_=1, to=100, width=5, textvariable=self._stop_heal_max_var).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(row2, text="%").pack(side=tk.LEFT)
        def on_autoheal_toggle():
            if self._autoheal_var.get():
                self._autoheal_stop.clear()
                def loop():
                    while not self._autoheal_stop.wait(timeout=0.6):
                        driver = get_driver()
                        if not driver:
                            continue
                        try:
                            heal_below = int(self._heal_below_var.get().strip() or "60")
                            stop_min = int(self._stop_heal_min_var.get().strip() or "90")
                            stop_max = int(self._stop_heal_max_var.get().strip() or "100")
                        except ValueError:
                            heal_below, stop_min, stop_max = 60, 90, 100
                        api = MargonemAPI(
                            driver,
                            log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)),
                        )
                        if api.ensure_context():
                            api.try_autoheal_tick(
                                heal_below, stop_min, stop_max,
                                log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)),
                            )
                    self.root.after(0, lambda: self._log_append("AutoHeal zatrzymany."))
                self._autoheal_thread = threading.Thread(target=loop, daemon=True)
                self._autoheal_thread.start()
                self._log_append("AutoHeal włączony (lecz < {} %, stop {}-{} %).".format(
                    self._heal_below_var.get(), self._stop_heal_min_var.get(), self._stop_heal_max_var.get()))
            else:
                self._autoheal_stop.set()
        ttk.Checkbutton(
            heal_f, text="Włącz autoheal (sprawdzanie co 0.6 s)",
            variable=self._autoheal_var, command=on_autoheal_toggle,
        ).pack(anchor=tk.W, pady=(8, 0))

    def _debug_refresh_status(self):
        driver = get_driver()
        if not driver:
            self._debug_status_text.set("Brak przeglądarki – uruchom ją najpierw.")
            self._log_append("Debug: brak drivera.")
            return
        api = MargonemAPI(driver, log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)))
        if not api.ensure_context():
            self._debug_status_text.set("Engine niedostępny – wejdź na postać w grze.")
            self._log_append("Debug: Engine nie jest gotowy (wejdz w grę).")
            return
        pos = api.get_hero_position()
        stats = api.get_hero_stats()
        mi = api.get_map_info()
        if pos is None:
            self._debug_status_text.set("Mapa: {} (ID: {}). Pozycja: nie odczytano.".format(
                mi.get("name") or "?", mi.get("id") or "?"))
        else:
            hp = stats.get("hp"), stats.get("maxhp")
            hp_str = "{}/{}".format(hp[0], hp[1]) if hp[0] is not None and hp[1] else "?"
            self._debug_status_text.set(
                "Pozycja: ({}, {}) | HP: {} | Mapa: {} (ID: {})".format(
                    pos[0], pos[1], hp_str, mi.get("name") or "?", mi.get("id") or "?"
                )
            )
        self._log_append("Status odświeżony.")

    def _debug_go_xy(self):
        try:
            x = int(self._debug_x_var.get().strip())
            y = int(self._debug_y_var.get().strip())
        except ValueError:
            self._log_append("Debug: Podaj poprawne liczby X i Y.")
            return
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        api = MargonemAPI(driver, log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)))
        api.ensure_context()
        api.go_to_xy(x, y)
        self._log_append("Wysłano: Idź do ({}, {}).".format(x, y))

    def _debug_attack_search_maps(self):
        name = (self._debug_attack_name_var.get() or "").strip()
        if not name:
            self._log_append("Debug: Podaj nazwę przeciwnika.")
            return
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        self._log_append("Szukam map z przeciwnikiem '{}'...".format(name))
        def work():
            api = MargonemAPI(driver, log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)))
            if not api.ensure_context():
                self.root.after(0, lambda: self._log_append("Engine niedostępny – wejdź na postać."))
                return
            current_id = api.get_current_map_id()
            current_norm = str(current_id) if current_id is not None else None
            groups = get_maps_with_npc_by_distance(name, current_id)
            self.root.after(0, lambda: self._fill_attack_maps(current_norm, groups, name))
        threading.Thread(target=work, daemon=True).start()

    def _fill_attack_maps(self, current_map_id, groups, enemy_name):
        """Wypełnia kontener przyciskami map pogrupowanymi wg odległości."""
        for w in self._attack_maps_container.winfo_children():
            w.destroy()
        if not groups:
            ttk.Label(self._attack_maps_container, text="Brak map z tym przeciwnikiem.").pack(anchor=tk.W)
            return
        for label, maps_list in groups:
            grp_f = ttk.LabelFrame(self._attack_maps_container, text=label, padding=4)
            grp_f.pack(fill=tk.X, pady=(0, 6))
            row = ttk.Frame(grp_f)
            row.pack(anchor=tk.W)
            for map_id, map_name, count in maps_list:
                is_current = (str(map_id) == current_map_id)
                btn_text = "{} ({}) [TU JESTEŚ]".format(map_name, count) if is_current else "{} ({})".format(map_name, count)
                btn = ttk.Button(
                    row,
                    text=btn_text,
                    command=lambda mid=map_id, mname=map_name, ename=enemy_name: self._debug_attack_go_to_map(mid, mname, ename),
                )
                btn.pack(side=tk.LEFT, padx=(0, 6), pady=2)
        self._attack_maps_canvas.update_idletasks()
        self._attack_maps_canvas.configure(scrollregion=self._attack_maps_canvas.bbox("all"))

    def _process_refresh_listbox(self):
        """Lista: najpierw aktualny (z *), potem kolejka."""
        self._process_listbox.delete(0, tk.END)
        if self._current_process_id and self._current_process_id in self._processes:
            self._process_listbox.insert(tk.END, "* " + self._processes[self._current_process_id]["name"])
        for pid in self._process_queue:
            if pid in self._processes:
                self._process_listbox.insert(tk.END, "  " + self._processes[pid]["name"])

    def _process_get_selected_id(self):
        sel = self._process_listbox.curselection()
        if not sel:
            return None
        i = sel[0]
        if self._current_process_id is not None:
            if i == 0:
                return self._current_process_id
            i -= 1
        if i < len(self._process_queue):
            return self._process_queue[i]
        return None

    def _process_remove(self, process_id):
        """Usuwa proces (z kolejki i słownika)."""
        if process_id in self._process_queue:
            self._process_queue.remove(process_id)
        if process_id == self._current_process_id:
            self._current_process_id = None
        if process_id in self._processes:
            del self._processes[process_id]
        self.root.after(0, self._process_refresh_listbox)

    def _process_on_finished(self, process_id):
        """Wywołane gdy wątek procesu się kończy."""
        if process_id == self._current_process_id:
            self._current_process_id = None
        if process_id in self._processes:
            del self._processes[process_id]
        self.root.after(0, self._process_refresh_listbox)
        self._process_worker_pick_next()

    def _process_worker_pick_next(self):
        """Wybiera z kolejki proces z najbliższą mapą i uruchamia go."""
        if self._current_process_id is not None or not self._process_queue:
            self.root.after(0, self._process_refresh_listbox)
            return
        def pick_and_run():
            driver = get_driver()
            if not driver:
                self.root.after(0, self._process_refresh_listbox)
                return
            api = MargonemAPI(driver, log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)))
            if not api.ensure_context():
                self.root.after(0, self._process_refresh_listbox)
                return
            current_map_id = api.get_current_map_id()
            best_pid, best_dist = None, 9999
            for pid in self._process_queue:
                if pid not in self._processes:
                    continue
                tid = self._processes[pid].get("target_map_id")
                path = bfs_path(current_map_id, tid) if tid else None
                d = len(path) if path is not None else 9999
                if d < best_dist:
                    best_dist = d
                    best_pid = pid
            if best_pid is None:
                self.root.after(0, self._process_refresh_listbox)
                return
            self._process_queue.remove(best_pid)
            self._current_process_id = best_pid
            self.root.after(0, self._process_refresh_listbox)
            self._run_attack_process(best_pid)
        threading.Thread(target=pick_and_run, daemon=True).start()

    def _run_attack_process(self, process_id):
        """Wykonuje jeden proces ataku (nawigacja + pętla ataków)."""
        if process_id not in self._processes:
            return
        p = self._processes[process_id]
        driver = get_driver()
        if not driver:
            self._process_on_finished(process_id)
            return
        target_map_id = p["target_map_id"]
        target_map_name = p["target_map_name"]
        enemy_name = p["enemy_name"]
        attack_loop = p["attack_loop"]
        cancel_ev = p["cancel"]
        pause_ev = p["pause"]

        def work():
            def log(m):
                self.root.after(0, lambda msg=m: self._log_append(msg))
            try:
                if cancel_ev.is_set():
                    return
                api = MargonemAPI(
                    driver,
                    log_callback=log,
                    captcha_check=lambda d: check_and_solve_captcha_once(d, log_callback=log),
                )
                if not api.ensure_context():
                    self.root.after(0, lambda: self._log_append("Engine niedostępny."))
                    return
                if cancel_ev.is_set():
                    return
                current_id = api.get_current_map_id()
                if current_id is not None and str(current_id) != str(target_map_id):
                    path = bfs_path(current_id, target_map_id)
                    if path is None:
                        self.root.after(0, lambda: self._log_append("Brak ścieżki do mapy {}.".format(target_map_name)))
                        return
                    ok = api.navigate_to_map(path)
                    self.root.after(0, lambda: self._log_append("Dojście na mapę (sukces={}).".format(ok)))
                    if not ok:
                        return
                count = 0
                while True:
                    if cancel_ev.is_set():
                        log("Atak anulowany.")
                        break
                    while pause_ev.is_set():
                        time.sleep(0.3)
                        if cancel_ev.is_set():
                            break
                    if cancel_ev.is_set():
                        break
                    log("Atakuję najbliższego '{}'...".format(enemy_name))
                    ok = api.attack_entity_by_name(enemy_name, timeout_sec=45)
                    if ok:
                        count += 1
                    if not attack_loop:
                        break
                    if not ok:
                        # W trybie pętli: brak mobków – najpierw sąsiednie mapy z tym mobem, potem 15s wander, w kółko
                        if not self._wait_for_mobs_or_visit_neighbors(
                            api, enemy_name,
                            cancel_ev=cancel_ev, pause_ev=pause_ev, log=log,
                        ):
                            break
                    # ok albo po respawnie/odwiedzeniu sąsiada – kontynuuj pętlę
                self.root.after(0, lambda: self._log_append("--- Koniec ataku (pokonano: {}) ---".format(count)))
            finally:
                self._process_on_finished(process_id)
        threading.Thread(target=work, daemon=True).start()

    def _wait_for_mobs_or_visit_neighbors(self, api, enemy_name, cancel_ev, pause_ev, log):
        """
        Gdy brak mobków na mapie: jeśli sąsiednie mapy mają ten mob – idź tam, bij lub chodź 15s i szukaj dalej.
        Jeśli żaden sąsiad nie ma moba – chodź losowo na obecnej mapie (respawn). Zwraca True gdy moby są.
        """
        import random as _random
        last_visited_map_id = None
        while True:
            if cancel_ev.is_set():
                return False
            while pause_ev.is_set():
                time.sleep(0.3)
                if cancel_ev.is_set():
                    return False
            if api.find_npcs_by_name(enemy_name):
                return True
            maps_with_mob = get_maps_with_npc(enemy_name)
            current_id = api.get_current_map_id()
            if current_id is None:
                return api.wait_for_entity_respawn_while_wandering(
                    enemy_name,
                    cancel_check=lambda: cancel_ev.is_set(),
                    pause_check=lambda: pause_ev.is_set(),
                )
            neighbor_ids = set(str(mid) for mid in get_neighbor_map_ids(current_id))
            neighbors_with_mob = [m for m in maps_with_mob if str(m[0]) in neighbor_ids]
            # Opcjonalnie pomiń mapę, z której właśnie przyszliśmy
            if last_visited_map_id is not None:
                neighbors_with_mob = [m for m in neighbors_with_mob if str(m[0]) != str(last_visited_map_id)]
            if not neighbors_with_mob:
                log("Brak mobków na sąsiednich mapach – chodzę losowo na tej mapie, czekam na respawn.")
                return api.wait_for_entity_respawn_while_wandering(
                    enemy_name,
                    cancel_check=lambda: cancel_ev.is_set(),
                    pause_check=lambda: pause_ev.is_set(),
                )
            next_map = _random.choice(neighbors_with_mob)
            next_map_id, next_map_name, _ = next_map[0], next_map[1], next_map[2]
            path = bfs_path(current_id, next_map_id)
            if not path:
                continue
            log("Idę na sąsiednią mapę {} – tam są mobki.".format(next_map_name))
            if not api.navigate_to_map(path):
                continue
            if cancel_ev.is_set():
                return False
            last_visited_map_id = current_id
            if api.find_npcs_by_name(enemy_name):
                return True
            log("Na mapie {} brak mobków – chodzę 15 s, potem spróbuję innej sąsiedniej.".format(next_map_name))
            api.wander_randomly_for_seconds(
                15,
                cancel_check=lambda: cancel_ev.is_set(),
                pause_check=lambda: pause_ev.is_set(),
            )
            if cancel_ev.is_set():
                return False

    def _process_run_now(self):
        """Wykonaj teraz: przerwij bieżący i uruchom zaznaczony proces."""
        pid = self._process_get_selected_id()
        if not pid or pid not in self._processes:
            return
        if pid == self._current_process_id:
            self._log_append("Ten proces już jest wykonywany.")
            return
        if self._current_process_id:
            self._processes[self._current_process_id]["cancel"].set()
            self._log_append("Przerwano bieżący proces.")
        if pid in self._process_queue:
            self._process_queue.remove(pid)
        self._current_process_id = pid
        self._process_refresh_listbox()
        self._run_attack_process(pid)

    def _process_pause_toggle(self):
        pid = self._process_get_selected_id()
        if not pid or pid not in self._processes:
            return
        p = self._processes[pid]
        if p["pause"].is_set():
            p["pause"].clear()
            self._log_append("Proces wznowiony.")
        else:
            p["pause"].set()
            self._log_append("Proces wstrzymany (pauza).")

    def _process_cancel(self):
        pid = self._process_get_selected_id()
        if not pid or pid not in self._processes:
            return
        if pid in self._process_queue:
            self._process_queue.remove(pid)
            self._process_remove(pid)
            self._log_append("Usunięto z kolejki.")
        else:
            self._processes[pid]["cancel"].set()
            self._log_append("Anulowano (zakończy się przy najbliższej okazji).")

    def _debug_attack_go_to_map(self, target_map_id, target_map_name, enemy_name):
        """Dodaje atak do kolejki procesów (najbliższa mapa wykonywana pierwsza)."""
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        attack_loop = self._debug_attack_loop_var.get()
        display_name = "Atak: {} na {}".format(enemy_name, target_map_name)
        if attack_loop:
            display_name += " [pętla]"
        process_id = str(uuid.uuid4())[:8]
        cancel_ev = threading.Event()
        pause_ev = threading.Event()
        self._processes[process_id] = {
            "name": display_name,
            "cancel": cancel_ev,
            "pause": pause_ev,
            "target_map_id": target_map_id,
            "target_map_name": target_map_name,
            "enemy_name": enemy_name,
            "attack_loop": attack_loop,
        }
        self._process_queue.append(process_id)
        self._process_refresh_listbox()
        self._log_append("Dodano do kolejki: {}.".format(display_name))
        self._process_worker_pick_next()

    def _debug_talk_by_name(self):
        name = (self._debug_talk_name_var.get() or "").strip()
        if not name:
            self._log_append("Debug: Podaj nazwę NPC do rozmowy.")
            return
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        maps_with_npc = get_maps_with_npc(name)
        if not maps_with_npc:
            self._log_append("Brak NPC o nazwie zawierającej '{}' na żadnej mapie.".format(name))
            return
        if self._current_process_id:
            self._log_append("Zakończ lub anuluj bieżący proces (atak/rozmowa), potem spróbuj ponownie.")
            return
        process_id = str(uuid.uuid4())[:8]
        cancel_ev = threading.Event()
        pause_ev = threading.Event()
        display_name = "Rozmowa: {}".format(name)
        self._processes[process_id] = {"name": display_name, "cancel": cancel_ev, "pause": pause_ev}
        self._current_process_id = process_id
        self._process_refresh_listbox()
        self._log_append("--- Rozmowa z: '{}' (znaleziono na {} mapach) ---".format(name, len(maps_with_npc)))
        def work():
            def log(m):
                self.root.after(0, lambda msg=m: self._log_append(msg))
            try:
                if cancel_ev.is_set():
                    return
                api = MargonemAPI(
                    driver,
                    log_callback=log,
                    captcha_check=lambda d: check_and_solve_captcha_once(d, log_callback=log),
                )
                if not api.ensure_context():
                    self.root.after(0, lambda: self._log_append("Debug: Engine niedostępny – wejdź na postać."))
                    return
                while pause_ev.is_set() and not cancel_ev.is_set():
                    time.sleep(0.3)
                if cancel_ev.is_set():
                    return
                current_id = api.get_current_map_id()
                current_norm = str(current_id) if current_id is not None else None
                map_ids = [str(m[0]) for m in maps_with_npc]
                if current_norm in map_ids:
                    log("Jesteś na mapie z tym NPC – rozmawiam.")
                    api.talk_to_entity_by_name(name, timeout_sec=45)
                    self.root.after(0, lambda: self._log_append("--- Koniec rozmowy ---"))
                    return
                best_map_id, best_name, _ = None, None, None
                best_len = 9999
                for map_id, map_name, _ in maps_with_npc:
                    path = bfs_path(current_id, map_id)
                    if path is not None and len(path) < best_len:
                        best_len = len(path)
                        best_map_id, best_name = map_id, map_name
                if best_map_id is None:
                    self.root.after(0, lambda: self._log_append("Brak ścieżki do żadnej mapy z tym NPC."))
                    return
                log("Idę na mapę {} ({} przejść), potem rozmowa.".format(best_name, best_len))
                path = bfs_path(current_id, best_map_id)
                if cancel_ev.is_set():
                    return
                if not api.navigate_to_map(path):
                    self.root.after(0, lambda: self._log_append("--- Nie udało się dojść na mapę ---"))
                    return
                if cancel_ev.is_set():
                    return
                api.talk_to_entity_by_name(name, timeout_sec=45)
                self.root.after(0, lambda: self._log_append("--- Koniec rozmowy ---"))
            finally:
                self._process_on_finished(process_id)
        threading.Thread(target=work, daemon=True).start()

    def _debug_filter_maps(self):
        search = (self._debug_map_search_var.get() or "").strip()
        self._debug_maps_filtered = find_map_ids_by_name(search)
        self._debug_maps_listbox.delete(0, tk.END)
        for _mid, name in self._debug_maps_filtered:
            self._debug_maps_listbox.insert(tk.END, name)

    def _debug_navigate_to_map(self):
        sel = self._debug_maps_listbox.curselection()
        if not sel:
            self._log_append("Debug: Zaznacz mapę docelową na liście.")
            return
        idx = int(sel[0])
        if idx >= len(self._debug_maps_filtered):
            return
        target_map_id, target_name = self._debug_maps_filtered[idx]
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        self._log_append("--- Nawigacja do mapy: {} (ID: {}) ---".format(target_name, target_map_id))

        def work():
            def log(m):
                self.root.after(0, lambda msg=m: self._log_append(msg))
            api = MargonemAPI(
                driver,
                log_callback=log,
                captcha_check=lambda d: check_and_solve_captcha_once(d, log_callback=log),
            )
            if not api.ensure_context():
                self.root.after(0, lambda: self._log_append("Debug: Engine niedostępny – wejdź na postać."))
                return
            current_id = api.get_current_map_id()
            if current_id is None:
                self.root.after(0, lambda: self._log_append("Debug: Nie odczytano obecnej mapy."))
                return
            path = bfs_path(current_id, target_map_id)
            if path is None:
                self.root.after(0, lambda: self._log_append("Brak ścieżki BFS z mapy {} do {}.".format(
                    get_map_name_by_id(current_id) or current_id, target_name)))
                return
            if not path:
                self.root.after(0, lambda: self._log_append("Już jesteś na mapie {}.".format(target_name)))
                return
            self.root.after(0, lambda: self._log_append("Ścieżka ({} kroków): {} -> ... -> {}.".format(
                len(path), get_map_name_by_id(current_id) or current_id, target_name)))
            ok = api.navigate_to_map(path)
            self.root.after(0, lambda: self._log_append("--- Koniec nawigacji (sukces={}) ---".format(ok)))

        threading.Thread(target=work, daemon=True).start()

    def _debug_list_npcs(self):
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        api = MargonemAPI(driver, log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)))
        if not api.ensure_context():
            self._log_append("Debug: Engine niedostępny.")
            return
        npcs = api.get_npcs_list()
        self._log_append("--- NPC na mapie ({}): ---".format(len(npcs)))
        for n in npcs[:50]:
            self._log_append("  id={} nick='{}' x={} y={}".format(n.get("id"), n.get("nick"), n.get("x"), n.get("y")))
        if len(npcs) > 50:
            self._log_append("  ... i {} więcej.".format(len(npcs) - 50))
        self._log_append("---")

    def _run_browser(self):
        self._btn_run.config(state=tk.DISABLED)
        self._status.config(text="Uruchamiam przeglądarkę...")
        self._log_append("Uruchamiam przeglądarkę (Chrome)...")

        def work():
            try:
                driver = _create_browser()
                set_driver(driver, log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)))
                self.root.after(0, lambda: self._status.config(text="Przeglądarka otwarta. Logowanie..."))
                self.root.after(0, lambda: self._log_append("Przeglądarka otwarta. Wykonuję logowanie..."))
                run_login_flow(
                    driver, self.login, self.password,
                    log_callback=lambda m: self.root.after(0, lambda msg=m: self._log_append(msg)),
                )
                self.root.after(0, lambda: self._status.config(text="Zalogowano. Wejdź na postać, potem użyj Debug."))
            except Exception as e:
                self.root.after(0, lambda: self._status.config(text="Błąd."))
                self.root.after(0, lambda: self._log_append("Błąd: " + str(e)))
                self.root.after(0, lambda: messagebox.showerror("Błąd", str(e), parent=self.root))
            finally:
                self.root.after(0, lambda: self._btn_run.config(state=tk.NORMAL))

        threading.Thread(target=work, daemon=True).start()

    def _on_close(self):
        driver = get_driver()
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    result = LoginDialog().run()
    if result is None:
        return
    login, password, _ = result
    MainWindow(login, password).run()


if __name__ == "__main__":
    main()
