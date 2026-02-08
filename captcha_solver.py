# -*- coding: utf-8 -*-
"""
Anty-captcha: wykrywanie i rozwiązywanie zagadki (gwiazdka) w Margonem.
- Przycisk „Rozwiąż teraz” (pre-captcha) – gdy widać, klik żeby szybko otworzyć zagadkę.
- Okno zagadki (captcha-layer): zaznacz przyciski z * w etykiecie, potem „Potwierdzam”.
- W szczególnych wypadkach captcha-layer może wyskoczyć BEZ wcześniejszego pre-captcha;
  wtedy bot od razu rozwiązuje zagadkę (bez klikania „Rozwiąż teraz”).
- Gdy „Liczba pozostałych prób” < 2 – nie rozwiązujemy, zostawiamy grę.
Wszystkie sprawdzenia w default_content (zagadka jest w głównym dokumencie).
"""
import re
import time


MIN_TRIES_TO_SOLVE = 2  # jeśli pozostałe próby < 2, nie rozwiązuj – zostaw grę

# Pre-captcha: przycisk „Rozwiąż teraz”
CSS_ROZWIĄŻ_TERAZ = "div.captcha-pre-info__button"
XPATH_ROZWIĄŻ_TERAZ = "//div[contains(@class,'captcha-pre-info__button')]"
XPATH_ROZWIĄŻ_LABEL = "//div[contains(@class,'label') and normalize-space(text())='Rozwiąż teraz']"

# Okno zagadki: captcha-layer jest często pusty gdy nie ma zagadki – sprawdzamy zawartość
CSS_CAPTCHA_LAYER = "div.captcha-layer"
CSS_CAPTCHA_WINDOW = "div.captcha-layer div.captcha-window"
CSS_CAPTCHA_LAYER_WITH_CONTENT = "div.captcha-layer div.captcha-window"  # warstwa z prawdziwym oknem
CSS_CAPTCHA_TRIES = "div.captcha__triesleft"
CSS_CAPTCHA_BUTTONS = "div.captcha__buttons div.button.small.green"
CSS_CAPTCHA_CONFIRM = "div.captcha__confirm div.button"
CHAR_TO_SELECT = "*"


def _switch_default(driver):
    try:
        driver.switch_to.default_content()
    except Exception:
        pass


def is_pre_captcha_visible(driver):
    """Czy widać przycisk „Rozwiąż teraz” (niedługo zagadka)."""
    _switch_default(driver)
    for selector, by in [
        (CSS_ROZWIĄŻ_TERAZ, "css selector"),
        (XPATH_ROZWIĄŻ_TERAZ, "xpath"),
    ]:
        try:
            el = driver.find_element(by, selector)
            return el.is_displayed()
        except Exception:
            continue
    return False


def is_captcha_window_visible(driver):
    """
    Czy widać okno zagadki. captcha-layer bywa pusty w DOM gdy nie ma captchy –
    uznajemy tylko gdy wewnątrz jest faktyczne okno (np. .captcha-window lub .captcha__triesleft).
    """
    _switch_default(driver)
    for selector in (CSS_CAPTCHA_LAYER_WITH_CONTENT, "div.captcha-layer .captcha__triesleft"):
        try:
            el = driver.find_element("css selector", selector)
            return el.is_displayed()
        except Exception:
            continue
    return False


def get_captcha_tries_left(driver):
    """
    Odczyt „Liczba pozostałych prób: N” z .captcha__triesleft.
    Zwraca int lub None gdy nie znaleziono / błąd parsowania.
    """
    _switch_default(driver)
    try:
        el = driver.find_element("css selector", CSS_CAPTCHA_TRIES)
        text = (el.text or "").strip()
        # np. "Liczba pozostałych prób: 3"
        m = re.search(r"(\d+)\s*$", text)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def click_rozwiaz_teraz(driver, log_callback=None):
    """Klika „Rozwiąż teraz”. Zwraca True jeśli kliknięto."""
    def log(msg):
        if log_callback:
            log_callback(msg)
    _switch_default(driver)
    for selector, by in [
        (CSS_ROZWIĄŻ_TERAZ, "css selector"),
        (XPATH_ROZWIĄŻ_TERAZ, "xpath"),
        (XPATH_ROZWIĄŻ_LABEL + "/ancestor::div[contains(@class,'button')]", "xpath"),
    ]:
        try:
            el = driver.find_element(by, selector)
            if el.is_displayed():
                el.click()
                log("Kliknięto „Rozwiąż teraz”.")
                return True
        except Exception:
            continue
    return False


def solve_captcha_window(driver, log_callback=None):
    """
    Rozwiązuje otwarte okno zagadki: zaznacza przyciski z * w etykiecie, klika Potwierdzam.
    Jeśli „Liczba pozostałych prób” < MIN_TRIES_TO_SOLVE – nie rozwiązuje, zwraca "skip".
    Zwraca "solved" | "skip" | "not_found".
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    _switch_default(driver)
    if not is_captcha_window_visible(driver):
        return "not_found"

    tries = get_captcha_tries_left(driver)
    if tries is not None and tries < MIN_TRIES_TO_SOLVE:
        log("Liczba pozostałych prób ({}) < {} – nie rozwiązuję, zostawiam grę.".format(tries, MIN_TRIES_TO_SOLVE))
        return "skip"

    # Zaznacz przyciski z gwiazdką
    clicked = 0
    try:
        buttons = driver.find_elements("css selector", CSS_CAPTCHA_BUTTONS)
        for btn in buttons:
            try:
                label_el = btn.find_element("css selector", "div.label")
                label_text = (label_el.text or "").strip()
                if CHAR_TO_SELECT in label_text:
                    btn.click()
                    clicked += 1
                    log("Zaznaczono przycisk: \"{}\"".format(label_text))
                    time.sleep(0.15)
            except Exception:
                continue
    except Exception as e:
        log("Błąd przy przyciskach zagadki: {}".format(e))

    time.sleep(0.25)
    # Potwierdź
    try:
        confirm = driver.find_element("css selector", CSS_CAPTCHA_CONFIRM)
        if confirm.is_displayed():
            confirm.click()
            log("Kliknięto „Potwierdzam”.")
    except Exception:
        for xpath in [
            "//div[contains(@class,'captcha__confirm')]//div[contains(@class,'button')]",
            "//div[contains(@class,'label') and contains(text(),'Potwierdzam')]/ancestor::div[contains(@class,'button')]",
        ]:
            try:
                btn = driver.find_element("xpath", xpath)
                if btn.is_displayed():
                    btn.click()
                    log("Kliknięto „Potwierdzam”.")
                    break
            except Exception:
                continue

    return "solved"


def is_captcha_blocking(driver):
    """True jeśli widać pre-captcha („Rozwiąż teraz”) lub okno zagadki – postać jest zablokowana."""
    return is_pre_captcha_visible(driver) or is_captcha_window_visible(driver)


def ensure_no_captcha(driver, log_callback=None):
    """
    Pętla: dopóki captcha blokuje – rozwiąż okno zagadki LUB kliknij „Rozwiąż teraz”.
    Najpierw sprawdzane jest okno (captcha-layer) – jeśli widać, od razu rozwiązujemy
    (także gdy wyskoczyło bez pre-captcha). Dopiero gdy nie ma okna, szukamy „Rozwiąż teraz”.
    Gdy „Liczba pozostałych prób” < 2 – kończy bez rozwiązywania i zwraca "skipped_tries".
    Zwraca: "not_blocking" | "solved" | "skipped_tries".
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    _switch_default(driver)
    while True:
        if not is_captcha_blocking(driver):
            return "not_blocking"

        # Najpierw okno zagadki (także gdy captcha-layer wyskoczył bez pre-captcha – od razu rozwiązujemy)
        if is_captcha_window_visible(driver):
            tries = get_captcha_tries_left(driver)
            if tries is not None and tries < MIN_TRIES_TO_SOLVE:
                log("Pozostało mniej niż {} prób (jest {}). Nie rozwiązuję zagadki, zostawiam grę.".format(
                    MIN_TRIES_TO_SOLVE, tries))
                return "skipped_tries"
            result = solve_captcha_window(driver, log_callback=log_callback)
            if result == "skip":
                return "skipped_tries"
            if result == "solved":
                time.sleep(0.6)
                continue
        elif is_pre_captcha_visible(driver):
            click_rozwiaz_teraz(driver, log_callback=log_callback)
            time.sleep(0.8)

        time.sleep(0.4)


def check_and_solve_captcha_once(driver, log_callback=None):
    """
    Jednorazowe sprawdzenie: jeśli blokuje – rozwiąż (lub skip przy próbach < 2).
    Do wywołania w pętlach bota (nawigacja, atak). Zwraca "not_blocking" | "solved" | "skipped_tries".
    """
    if not is_captcha_blocking(driver):
        return "not_blocking"
    return ensure_no_captcha(driver, log_callback=log_callback)
