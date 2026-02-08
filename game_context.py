# -*- coding: utf-8 -*-
"""
Kontekst gry – przełączanie na iframe z Engine, sprawdzanie czy silnik jest gotowy.
"""
# (brak zewnętrznych zależności)


def is_engine_ready(driver):
    """Czy silnik gry (Engine) jest załadowany – np. czy jesteśmy w grze."""
    try:
        return driver.execute_script(
            "return typeof Engine !== 'undefined' && Engine.map && Engine.hero && Engine.npcs;"
        )
    except Exception:
        return False


def ensure_game_context(driver):
    """
    Przełącza na kontekst, w którym działa Engine (główna strona lub iframe z grą).
    Zwraca True jeśli Engine jest gotowy po przełączeniu.
    """
    if is_engine_ready(driver):
        return True
    try:
        frames = driver.find_elements("tag name", "iframe")
        for _ in frames:
            driver.switch_to.default_content()
            for i, _ in enumerate(frames):
                try:
                    driver.switch_to.frame(i)
                    if is_engine_ready(driver):
                        return True
                except Exception:
                    pass
        driver.switch_to.default_content()
    except Exception:
        pass
    return False
