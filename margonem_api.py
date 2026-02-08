# -*- coding: utf-8 -*-
"""
API Margonem – mapa komend i obiektów z docs.md na klasę Pythona.
Użycie: api = MargonemAPI(driver); api.ensure_context(); api.hero.get_position()
Wszystkie metody przyjmują driver (Selenium) i wykonują execute_script w kontekście gry.
"""
import time
from game_context import ensure_game_context, is_engine_ready


class MargonemAPI:
    """
    Jednolity dostęp do Engine w grze Margonem.
    Przed wywołaniem metod upewnij się, że kontekst jest ustawiony (ensure_context).
    """

    def __init__(self, driver, log_callback=None, captcha_check=None):
        self.driver = driver
        self.log = log_callback or (lambda msg: None)
        self.captcha_check = captcha_check  # callable(driver) -> "skipped_tries" | None; po wywołaniu przywracamy kontekst gry

    def ensure_context(self):
        """Przełącza na iframe z grą i zwraca True jeśli Engine jest gotowy."""
        return ensure_game_context(self.driver)

    def is_ready(self):
        """Czy Engine jest dostępny (jesteśmy w grze)."""
        return is_engine_ready(self.driver)

    # --- Akcje (_g) ---

    def _g(self, task_string):
        """Wysłanie komendy do serwera: _g(taskString)."""
        self.ensure_context()
        self.driver.execute_script(
            "if (typeof _g === 'function') _g(arguments[0]);",
            task_string,
        )

    def talk_start(self, npc_id):
        """Rozpoczęcie rozmowy z NPC: talk&id=ID."""
        self._g("talk&id=" + str(int(npc_id)))

    def talk_option(self, npc_id, option_c):
        """Wybór opcji dialogowej: talk&id=ID&c=N."""
        c_str = "" if option_c is None else str(option_c)
        self.driver.execute_script(
            "if (typeof _g === 'function') _g('talk&id=' + arguments[0] + '&c=' + encodeURIComponent(arguments[1]));",
            int(npc_id), c_str,
        )

    def talk_cancel(self):
        """Zamknięcie okna dialogu: talk&action=cancel."""
        self._g("talk&action=cancel")

    def fight_attack(self, target_id, fast_fight=True):
        """
        Atak na potwora/gracza: fight&a=attack&id=ID[&ff=1].
        Dla potworów/NPC serwer oczekuje ujemnego ID. Z ff=1 walka jest od razu szybka,
        bez okna lootu i zamykania – postać musi stać przy NPC.
        """
        aid = int(target_id)
        if aid > 0:
            aid = -aid
        cmd = "fight&a=attack&id=" + str(aid)
        if fast_fight:
            cmd += "&ff=1"
        self._g(cmd)

    def fight_fast(self):
        """Szybka walka: fight&a=f&enabled=1 (jak w socket)."""
        self._g("fight&a=f&enabled=1")

    def fight_exit(self):
        """Zamknięcie okna walki po zakończeniu: fight&a=exit."""
        self._g("fight&a=exit")

    def loot(self, quality=0):
        """Podniesienie lootu po walce. quality=0 wszystko, wyższe=lepsze."""
        self._g("loot&quality=" + str(int(quality)))

    def take_item(self, item_id):
        """Podniesienie przedmiotu z ziemi: takeitem&id=ID."""
        self._g("takeitem&id=" + str(item_id))

    def move_item(self, item_id, slot):
        """Przeniesienie przedmiotu do slotu: moveitem&id=ID&st=N."""
        self._g("moveitem&id=" + str(item_id) + "&st=" + str(int(slot)))

    def mail_send(self, to_nick, subject, body):
        """Wysłanie poczty: mail&a=send&to=NICK&subj=T&body=B."""
        self._g("mail&a=send&to=" + str(to_nick) + "&subj=" + str(subject) + "&body=" + str(body))

    def shop_buy(self, item_id):
        """Zakup przedmiotu: shop&buy=ID."""
        self._g("shop&buy=" + str(item_id))

    def shop_sell(self, item_id):
        """Sprzedaż przedmiotu: shop&buy=&sell=ID."""
        self._g("shop&buy=&sell=" + str(item_id))

    # --- Hero (Engine.hero) ---

    def get_hero_position(self):
        """Zwraca (x, y) bohatera lub None."""
        self.ensure_context()
        try:
            r = self.driver.execute_script(
                "return (Engine && Engine.hero && Engine.hero.d) "
                "? { x: Engine.hero.d.x, y: Engine.hero.d.y } : null;"
            )
            return (r["x"], r["y"]) if r else None
        except Exception:
            return None

    def get_hero_stats(self):
        """Zwraca dict: hp, maxhp, lvl, gold, nick, id, dir, prof (lub częściowo None)."""
        self.ensure_context()
        try:
            return self.driver.execute_script(
                """
                if (!Engine || !Engine.hero || !Engine.hero.d) return null;
                var d = Engine.hero.d, ws = d.warrior_stats || {};
                return {
                    hp: ws.hp, maxhp: ws.maxhp, lvl: d.lvl, gold: d.gold,
                    nick: d.nick, id: d.id, dir: d.dir, prof: d.prof
                };
                """
            ) or {}
        except Exception:
            return {}

    def hero_auto_go_to(self, x, y):
        """Wysyła bohatera do kratki (x, y). Nie czeka na dojście."""
        self.ensure_context()
        self.driver.execute_script(
            "if (Engine && Engine.hero && Engine.hero.autoGoTo) "
            "Engine.hero.autoGoTo({ x: arguments[0], y: arguments[1] });",
            int(x), int(y),
        )
        self.log("Ruch do ({}, {}) rozpoczęty.".format(x, y))

    # --- Map (Engine.map) ---

    def get_map_info(self):
        """Zwraca dict: id, name, size_x, size_y lub pusty dict."""
        self.ensure_context()
        try:
            return self.driver.execute_script(
                """
                if (!Engine || !Engine.map) return {};
                var m = Engine.map;
                return {
                    id: m.d && m.d.id, name: m.d && m.d.name,
                    size_x: m.size && m.size.x, size_y: m.size && m.size.y
                };
                """
            ) or {}
        except Exception:
            return {}

    def get_ground_items(self):
        """Lista przedmiotów na ziemi: [{id, x, y, name}, ...]."""
        self.ensure_context()
        try:
            raw = self.driver.execute_script(
                """
                var raw = Engine && Engine.map && Engine.map.groundItems
                    ? Engine.map.groundItems.getDrawableItems() : [];
                var out = [];
                for (var i = 0; i < raw.length; i++) {
                    var o = raw[i];
                    if (o && o.i) out.push({ id: String(o.i.id), x: o.i.x, y: o.i.y, name: (o.i.name || '') });
                }
                return out;
                """
            )
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    def get_gateways(self):
        """Lista bram: [{id, x, y}, ...]."""
        self.ensure_context()
        try:
            raw = self.driver.execute_script(
                """
                var gates = Engine && Engine.map && Engine.map.gateways ? Engine.map.gateways.getList() : [];
                var out = [];
                for (var j = 0; j < gates.length; j++) {
                    var g = gates[j];
                    if (g && g.d) out.push({ id: g.d.id, x: g.d.x, y: g.d.y });
                }
                return out;
                """
            )
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    def get_float_objects(self):
        """Lista float objects (rośliny, zbieralne): [{id, x, y}, ...]."""
        self.ensure_context()
        try:
            raw = self.driver.execute_script(
                """
                var list = Engine && Engine.floatObjectManager
                    ? Engine.floatObjectManager.getDrawableList() : [];
                var out = [];
                for (var k = 0; k < list.length; k++) {
                    var o = list[k];
                    if (o && o.id != null && (o.x != null || (o.d && o.d.x != null))) {
                        out.push({ id: o.id, x: o.x != null ? o.x : o.d.x, y: o.y != null ? o.y : o.d.y });
                    }
                }
                return out;
                """
            )
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    # --- NPC (Engine.npcs) ---

    def get_npcs_list(self):
        """Lista wszystkich NPC na mapie: [{id, x, y, nick}, ...]."""
        self.ensure_context()
        try:
            raw = self.driver.execute_script(
                """
                var npcs = Engine && Engine.npcs ? Engine.npcs.check() : {};
                var list = [];
                for (var id in npcs) {
                    var n = npcs[id];
                    if (n && n.d) list.push({ id: n.d.id, x: n.d.x, y: n.d.y, nick: (n.d.nick || '') });
                }
                return list;
                """
            )
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    def get_npc_by_id(self, npc_id):
        """Zwraca {id, x, y, nick} dla NPC o danym ID lub None."""
        self.ensure_context()
        try:
            return self.driver.execute_script(
                """
                var id = arguments[0];
                var npc = (Engine && Engine.npcs && Engine.npcs.getById) ? Engine.npcs.getById(id) : null;
                if (!npc || !npc.d) return null;
                return { id: npc.d.id, x: npc.d.x, y: npc.d.y, nick: (npc.d.nick || '') };
                """,
                int(npc_id),
            )
        except Exception:
            return None

    def find_npcs_by_name(self, name_substring):
        """
        Zwraca listę NPC (i potworów) których nick zawiera name_substring (bez rozróżniania wielkości).
        Każdy element: {id, x, y, nick}.
        """
        part = (name_substring or "").strip().lower()
        if not part:
            return []
        all_npcs = self.get_npcs_list()
        return [n for n in all_npcs if part in (n.get("nick") or "").lower()]

    def find_nearest_npc_by_name(self, name_substring):
        """
        Znajduje najbliższego NPC/potwora o nazwie zawierającej name_substring.
        Zwraca {id, x, y, nick} lub None. Odległość w metryce Manhattan (kratki).
        """
        pos = self.get_hero_position()
        if pos is None:
            return None
        hx, hy = pos
        candidates = self.find_npcs_by_name(name_substring)
        if not candidates:
            return None
        best = None
        best_dist = float("inf")
        for n in candidates:
            dx = abs(n["x"] - hx)
            dy = abs(n["y"] - hy)
            d = dx + dy
            if d < best_dist:
                best_dist = d
                best = n
        return best

    # --- Locks (Engine.lock) ---

    def is_locked(self, lock_type=None):
        """
        lock_type=None: True jeśli jakakolwiek blokada.
        lock_type="battle"|"npcdialog"|"change_location"|"logoff": sprawdza konkretną blokadę.
        """
        self.ensure_context()
        try:
            if lock_type is None:
                return self.driver.execute_script("return Engine && Engine.lock && Engine.lock.check();")
            return self.driver.execute_script(
                "return Engine && Engine.lock && Engine.lock.check(arguments[0]);",
                lock_type,
            )
        except Exception:
            return False

    def can_act(self):
        """True jeśli nie ma blokady walki ani dialogu (można iść / atakować / rozmawiać)."""
        return not self.is_locked("battle") and not self.is_locked("npcdialog")

    def wait_until_battle_ends(self, timeout_sec=60, check_interval=0.4):
        """Czeka aż blokada walki (Engine.lock.check('battle')) zniknie. Zwraca True jeśli walka się skończyła."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if not self.is_locked("battle"):
                self.log("Walka zakończona.")
                return True
            time.sleep(check_interval)
        self.log("Timeout oczekiwania na zakończenie walki.")
        return False

    # --- Communication ---

    def get_full_data_package(self):
        """Ostatni pakiet JSON z serwera (do parsowania dialogów, lootu, błędów)."""
        self.ensure_context()
        try:
            return self.driver.execute_script(
                "return (Engine && Engine.communication && Engine.communication.getFullDataPackage) "
                "? Engine.communication.getFullDataPackage() : null;"
            )
        except Exception:
            return None

    def send2(self, task_string):
        """Wysłanie komendy z pominięciem kolejki: Engine.communication.send2(task)."""
        self.ensure_context()
        self.driver.execute_script(
            "if (Engine && Engine.communication && Engine.communication.send2) "
            "Engine.communication.send2(arguments[0]);",
            task_string,
        )

    # --- High-level: nawigacja i akcje po nazwie (DRY) ---

    def _distance_manhattan(self, x1, y1, x2, y2):
        return abs(x2 - x1) + abs(y2 - y1)

    def _maybe_solve_captcha(self):
        """Jeśli captcha_check ustawione: wywołaj, przywróć kontekst gry. Zwraca True jeśli należy przerwać (skipped_tries)."""
        if not self.captcha_check:
            return False
        try:
            r = self.captcha_check(self.driver)
            self.ensure_context()
            return r == "skipped_tries"
        except Exception:
            self.ensure_context()
            return False

    def go_to_xy(self, x, y):
        """Wysyła bohatera do (x, y). Nie czeka."""
        self.hero_auto_go_to(int(x), int(y))

    def wait_until_near(self, target_x, target_y, distance=1, timeout_sec=20, check_interval=0.4):
        """
        Czeka aż bohater będzie w odległości <= distance (Manhattan) od (target_x, target_y).
        Zwraca True jeśli dojdzie, False przy timeout.
        """
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self._maybe_solve_captcha():
                self.log("Przerwano (zagadka – za mało prób).")
                return False
            pos = self.get_hero_position()
            if pos is None:
                time.sleep(check_interval)
                continue
            if self._distance_manhattan(pos[0], pos[1], target_x, target_y) <= distance:
                self.log("Dojście do ({}, {}) – pozycja ({}, {}).".format(target_x, target_y, pos[0], pos[1]))
                return True
            time.sleep(check_interval)
        self.log("Timeout: bohater nie dojrzał do celu.")
        return False

    def _normalize_map_id(self, mid):
        """ID mapy do porównania (int lub string)."""
        if mid is None:
            return None
        try:
            return int(mid)
        except (TypeError, ValueError):
            return mid

    def get_current_map_id(self):
        """Aktualne ID mapy z Engine (int lub None)."""
        mi = self.get_map_info()
        if not mi:
            return None
        return mi.get("id")

    def wait_for_map_change(self, target_map_id, timeout_sec=15, check_interval=0.4):
        """
        Czeka aż postać zmieni mapę na target_map_id (porównanie po id).
        Zwraca True gdy mapa się zmieni, False przy timeout.
        """
        target = self._normalize_map_id(target_map_id)
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self._maybe_solve_captcha():
                self.log("Przerwano (zagadka – za mało prób).")
                return False
            current = self._normalize_map_id(self.get_current_map_id())
            if current is not None and target is not None and int(current) == int(target):
                self.log("Zmiana mapy – jesteśmy na docelowej mapie (ID: {}).".format(target))
                return True
            time.sleep(check_interval)
        self.log("Timeout: brak zmiany mapy na ID {}.".format(target_map_id))
        return False

    def go_to_gateway_and_enter(self, gateway_id, target_map_id, move_timeout_sec=25, map_change_timeout_sec=15):
        """
        Idzie do bramy o danym ID na aktualnej mapie, wchodzi (kratka od bramy) i czeka na zmianę mapy.
        gateway_id: id bramy z Engine.map.gateways (może int lub string).
        target_map_id: oczekiwane ID mapy po wejściu.
        Zwraca True jeśli udało się wejść na docelową mapę.
        """
        gateways = self.get_gateways()
        gw_id_norm = int(gateway_id) if gateway_id is not None else None
        gate = None
        for g in gateways:
            gid = g.get("id")
            if gid is not None and int(gid) == gw_id_norm:
                gate = g
                break
        if not gate:
            self.log("Brak bramy o ID {} na obecnej mapie.".format(gateway_id))
            return False
        gx, gy = gate.get("x"), gate.get("y")
        self.log("Przejście przez bramę {} do mapy {} – idę do ({}, {}).".format(gateway_id, target_map_id, gx, gy))
        self.hero_auto_go_to(gx, gy)
        if not self.wait_until_near(gx, gy, distance=1, timeout_sec=move_timeout_sec):
            return False
        return self.wait_for_map_change(target_map_id, timeout_sec=map_change_timeout_sec)

    def navigate_to_map(self, path, move_timeout_sec=25, map_change_timeout_sec=15):
        """
        Wykonuje ścieżkę między mapami. path = [(gateway_id, target_map_id), ...] (wynik BFS).
        Dla każdego kroku: sprawdza aktualną mapę; jeśli już na docelowej – koniec;
        w przeciwnym razie idzie do bramy, wchodzi i czeka na zmianę mapy.
        Zwraca True jeśli dotarł do ostatniej mapy z path.
        """
        for i, (gateway_id, target_map_id) in enumerate(path):
            current = self._normalize_map_id(self.get_current_map_id())
            target = self._normalize_map_id(target_map_id)
            if current is not None and target is not None and int(current) == int(target):
                self.log("Już na mapie docelowej (krok {}/{}).".format(i + 1, len(path)))
                continue
            if not self.go_to_gateway_and_enter(
                gateway_id, target_map_id,
                move_timeout_sec=move_timeout_sec,
                map_change_timeout_sec=map_change_timeout_sec,
            ):
                self.log("Nawigacja przerwana na kroku {} (brama {} -> mapa {}).".format(i + 1, gateway_id, target_map_id))
                return False
        return True

    def _go_to_entity_and_do(self, name_substring, action_name, do_callback, timeout_sec=30, check_interval=0.5):
        """
        Wspólna logika: znajdź najbliższego NPC po nazwie, idź do niego sprawdzając co chwilę pozycję,
        gdy postać będzie kratkę od celu – wykonaj do_callback(npc_dict).
        do_callback dostaje {id, x, y, nick}.
        """
        self.ensure_context()
        target = self.find_nearest_npc_by_name(name_substring)
        if not target:
            self.log("Nie znaleziono postaci o nazwie zawierającej: '{}'.".format(name_substring))
            return False
        tx, ty = target["x"], target["y"]
        self.log("Cel: {} (id={}) na ({}, {}). {}".format(target.get("nick"), target["id"], tx, ty, action_name))
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self._maybe_solve_captcha():
                self.log("Przerwano (zagadka – za mało prób).")
                return False
            if not self.can_act():
                time.sleep(check_interval)
                continue
            pos = self.get_hero_position()
            if pos is None:
                time.sleep(check_interval)
                continue
            if self._distance_manhattan(pos[0], pos[1], tx, ty) <= 1:
                self.log("W zasięgu – wykonuję: {}.".format(action_name))
                do_callback(target)
                return True
            # Odśwież pozycję celu (NPC może się ruszyć)
            t = self.get_npc_by_id(target["id"])
            if t:
                tx, ty = t["x"], t["y"]
            self.hero_auto_go_to(tx, ty)
            time.sleep(check_interval)
        self.log("Timeout przed wykonaniem: {}.".format(action_name))
        return False

    def attack_entity_by_name(self, name_substring, timeout_sec=30, fast_fight=True):
        """
        Znajdź najbliższą postać o nazwie zawierającej name_substring, podejdź na kratkę;
        gdy w zasięgu – atak z ff=1 (szybka walka bez okna lootu i zamykania).
        """
        def do_attack(npc):
            self.fight_attack(npc["id"], fast_fight=fast_fight)
        return self._go_to_entity_and_do(
            name_substring, "atak", do_attack,
            timeout_sec=timeout_sec,
        )

    def talk_to_entity_by_name(self, name_substring, timeout_sec=30):
        """
        Jak wyżej, ale gdy kratka od celu – rozpocznij rozmowę (talk&id=ID).
        """
        def do_talk(npc):
            self.talk_start(npc["id"])
        return self._go_to_entity_and_do(
            name_substring, "rozmowa", do_talk,
            timeout_sec=timeout_sec,
        )
