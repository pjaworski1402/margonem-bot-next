# -*- coding: utf-8 -*-
"""Zapis i odczyt loginu oraz hasła w katalogu AppData (Windows)."""
import json
import os

APP_NAME = "MargonemBot"
CREDENTIALS_FILENAME = "credentials.json"


def _get_appdata_path():
    """Ścieżka do katalogu aplikacji w AppData (Local)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_credentials_path():
    """Pełna ścieżka do pliku z danymi logowania."""
    return os.path.join(_get_appdata_path(), CREDENTIALS_FILENAME)


def load_credentials():
    """
    Wczytuje zapisany login i hasło.
    Zwraca dict z kluczami 'login', 'password' lub None jeśli brak pliku/niepoprawny.
    """
    path = get_credentials_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("login"), str) and isinstance(data.get("password"), str):
            return {"login": data["login"], "password": data["password"]}
    except (json.JSONDecodeError, IOError):
        pass
    return None


def save_credentials(login: str, password: str):
    """Zapisuje login i hasło do pliku w AppData."""
    path = get_credentials_path()
    data = {"login": login, "password": password}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
