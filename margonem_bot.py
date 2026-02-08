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

import config_credentials as creds
from margonem_api import MargonemAPI
from maps_graph import find_map_ids_by_name, bfs_path, get_map_name_by_id
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
    global _captcha_gave_up, _captcha_log_callback
    import time
    while not stop_event.wait(timeout=2.5):
        if _captcha_gave_up:
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

        # Wspólny log na dole
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._log = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 9))
        self._log.pack(fill=tk.BOTH, expand=True)

    def _build_debug_tab(self, parent):
        # Status (odśwież)
        status_f = ttk.LabelFrame(parent, text="Status gry", padding=8)
        status_f.pack(fill=tk.X, pady=(0, 8))
        self._debug_status_text = tk.StringVar(value="Kliknij 'Odśwież status', gdy postać jest w grze.")
        ttk.Label(status_f, textvariable=self._debug_status_text).pack(anchor=tk.W)
        ttk.Button(status_f, text="Odśwież status", command=self._debug_refresh_status).pack(anchor=tk.W, pady=(4, 0))

        # Idź do (x, y)
        go_f = ttk.LabelFrame(parent, text="Idź do pozycji (x, y)", padding=8)
        go_f.pack(fill=tk.X, pady=(0, 8))
        row = ttk.Frame(go_f)
        row.pack(anchor=tk.W)
        ttk.Label(row, text="X:").pack(side=tk.LEFT, padx=(0, 4))
        self._debug_x_var = tk.StringVar(value="0")
        ttk.Entry(row, textvariable=self._debug_x_var, width=6).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row, text="Y:").pack(side=tk.LEFT, padx=(0, 4))
        self._debug_y_var = tk.StringVar(value="0")
        ttk.Entry(row, textvariable=self._debug_y_var, width=6).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(row, text="Idź", command=self._debug_go_xy).pack(side=tk.LEFT)

        # Atakuj NPC po nazwie
        atk_f = ttk.LabelFrame(parent, text="Atakuj postać/NPC (po nazwie)", padding=8)
        atk_f.pack(fill=tk.X, pady=(0, 8))
        row_atk = ttk.Frame(atk_f)
        row_atk.pack(anchor=tk.W)
        self._debug_attack_name_var = tk.StringVar(value="Szczur")
        ttk.Entry(row_atk, textvariable=self._debug_attack_name_var, width=24).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row_atk, text="Atakuj (podejdź i atakuj)", command=self._debug_attack_by_name).pack(side=tk.LEFT)

        # Rozmawiaj z NPC po nazwie
        talk_f = ttk.LabelFrame(parent, text="Rozmawiaj z NPC (po nazwie)", padding=8)
        talk_f.pack(fill=tk.X, pady=(0, 8))
        row_talk = ttk.Frame(talk_f)
        row_talk.pack(anchor=tk.W)
        self._debug_talk_name_var = tk.StringVar(value="")
        ttk.Entry(row_talk, textvariable=self._debug_talk_name_var, width=24).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row_talk, text="Podejdź i rozmawiaj", command=self._debug_talk_by_name).pack(side=tk.LEFT)

        # Idź na mapę (BFS)
        nav_f = ttk.LabelFrame(parent, text="Idź na mapę (ścieżka BFS)", padding=8)
        nav_f.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        ttk.Label(nav_f, text="Obecna mapa odczytana przy starcie nawigacji.").pack(anchor=tk.W)
        row_search = ttk.Frame(nav_f)
        row_search.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(row_search, text="Szukaj mapy:").pack(side=tk.LEFT, padx=(0, 6))
        self._debug_map_search_var = tk.StringVar(value="")
        self._debug_map_search_var.trace_add("write", lambda *a: self._debug_filter_maps())
        ttk.Entry(row_search, textvariable=self._debug_map_search_var, width=30).pack(side=tk.LEFT, padx=(0, 8))
        list_frame = ttk.Frame(nav_f)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        scroll = ttk.Scrollbar(list_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._debug_maps_listbox = tk.Listbox(list_frame, height=8, yscrollcommand=scroll.set, font=("Consolas", 9))
        self._debug_maps_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self._debug_maps_listbox.yview)
        self._debug_maps_filtered = []  # lista (map_id, name)
        row_btn = ttk.Frame(nav_f)
        row_btn.pack(anchor=tk.W)
        ttk.Button(row_btn, text="Idź na mapę", command=self._debug_navigate_to_map).pack(side=tk.LEFT, padx=(0, 8))
        self._debug_filter_maps()

        # Lista NPC
        list_f = ttk.LabelFrame(parent, text="Mapa / NPC", padding=8)
        list_f.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(list_f, text="Wylistuj wszystkich NPC na mapie", command=self._debug_list_npcs).pack(anchor=tk.W)

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

    def _debug_attack_by_name(self):
        name = (self._debug_attack_name_var.get() or "").strip()
        if not name:
            self._log_append("Debug: Podaj nazwę postaci do ataku.")
            return
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        self._log_append("--- Atakuj: '{}' ---".format(name))
        def work():
            def log(m):
                self.root.after(0, lambda msg=m: self._log_append(msg))
            api = MargonemAPI(
                driver,
                log_callback=log,
                captcha_check=lambda d: check_and_solve_captcha_once(d, log_callback=log),
            )
            api.ensure_context()
            ok = api.attack_entity_by_name(name, timeout_sec=45)
            self.root.after(0, lambda: self._log_append("--- Koniec ataku (sukces={}) ---".format(ok)))
        threading.Thread(target=work, daemon=True).start()

    def _debug_talk_by_name(self):
        name = (self._debug_talk_name_var.get() or "").strip()
        if not name:
            self._log_append("Debug: Podaj nazwę NPC do rozmowy.")
            return
        driver = get_driver()
        if not driver:
            messagebox.showwarning("Uwaga", "Najpierw uruchom przeglądarkę i wejdź do gry.", parent=self.root)
            return
        self._log_append("--- Rozmowa z: '{}' ---".format(name))
        def work():
            def log(m):
                self.root.after(0, lambda msg=m: self._log_append(msg))
            api = MargonemAPI(
                driver,
                log_callback=log,
                captcha_check=lambda d: check_and_solve_captcha_once(d, log_callback=log),
            )
            api.ensure_context()
            ok = api.talk_to_entity_by_name(name, timeout_sec=45)
            self.root.after(0, lambda: self._log_append("--- Koniec rozmowy (sukces={}) ---".format(ok)))
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
