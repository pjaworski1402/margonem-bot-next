# -*- coding: utf-8 -*-
"""
Graf map Margonem z pliku margonem_maps_final.json.
BFS do wyznaczania ścieżki między mapami, wyszukiwanie po nazwie.
"""
import json
import os
from collections import deque

# Ścieżka do pliku względem tego modułu
_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_JSON_PATH = os.path.join(_DIR, "margonem_maps_final.json")

_maps_data = None
_graph = None
_name_to_ids = None
_all_names_sorted = None


def _normalize_id(mid):
    """Ujednolicenie ID mapy do stringa (klucze w JSON to stringi)."""
    if mid is None:
        return None
    return str(int(mid)) if isinstance(mid, (int, float)) else str(mid)


def _load_maps():
    global _maps_data, _graph, _name_to_ids, _all_names_sorted
    if _maps_data is not None:
        return
    with open(MAPS_JSON_PATH, "r", encoding="utf-8") as f:
        _maps_data = json.load(f)
    # name (lower) -> list of map_ids (first used when resolving exit target)
    _name_to_ids = {}
    for mid, info in _maps_data.items():
        name = (info.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key not in _name_to_ids:
            _name_to_ids[key] = []
        _name_to_ids[key].append(mid)
    # graph: map_id -> [(gateway_id, target_map_id), ...]
    # gateway_id w JSON to string (klucz w exits), target to nazwa - szukamy id po nazwie
    _graph = {}
    for mid, info in _maps_data.items():
        exits = info.get("exits") or {}
        edges = []
        for gw_id, target_name in exits.items():
            target_name = (target_name or "").strip()
            if not target_name:
                continue
            key = target_name.lower()
            candidates = _name_to_ids.get(key)
            if candidates:
                # bierzemy pierwszą mapę o danej nazwie
                target_id = candidates[0]
                edges.append((gw_id, target_id))
        _graph[mid] = edges
    _all_names_sorted = sorted(
        (info.get("name") or "").strip()
        for info in _maps_data.values()
        if (info.get("name") or "").strip()
    )


def get_all_map_names():
    """Zwraca posortowaną listę wszystkich nazw map (do listy / filtra)."""
    _load_maps()
    return list(_all_names_sorted)


def find_map_ids_by_name(name_substring):
    """
    Zwraca listę par (map_id, name) map, których nazwa zawiera name_substring (bez rozróżniania wielkości).
    """
    _load_maps()
    part = (name_substring or "").strip().lower()
    if not part:
        return [(mid, _maps_data[mid].get("name") or mid) for mid in sorted(_maps_data.keys(), key=lambda x: (_maps_data[x].get("name") or "").lower())]
    out = []
    for mid, info in _maps_data.items():
        name = (info.get("name") or "").strip()
        if part in name.lower():
            out.append((mid, name))
    return sorted(out, key=lambda x: x[1].lower())


def get_map_id_by_name(name):
    """
    Zwraca map_id (string) dla pierwszej mapy o podanej nazwie (bez rozróżniania wielkości), lub None.
    """
    _load_maps()
    name = (name or "").strip()
    if not name:
        return None
    key = name.lower()
    ids = _name_to_ids.get(key)
    if ids:
        return ids[0]
    # dopasowanie częściowe: pierwsza mapa zawierająca name
    for mid, info in _maps_data.items():
        if name.lower() in ((info.get("name") or "").lower()):
            return mid
    return None


def get_map_name_by_id(map_id):
    """Zwraca nazwę mapy o danym ID lub None."""
    _load_maps()
    mid = _normalize_id(map_id)
    if mid not in _maps_data:
        return None
    return (_maps_data[mid].get("name") or "").strip() or mid


def bfs_path(start_map_id, target_map_id):
    """
    BFS: ścieżka od start_map_id do target_map_id.
    Zwraca listę krotek (gateway_id, target_map_id) – kolejne przejścia bramą na następną mapę.
    Pusta lista jeśli start == target. None jeśli brak ścieżki.
    """
    _load_maps()
    start = _normalize_id(start_map_id)
    target = _normalize_id(target_map_id)
    if start not in _graph or target not in _maps_data:
        return None
    if start == target:
        return []
    # BFS
    queue = deque([start])
    visited = {start}
    parent = {}  # map_id -> (prev_map_id, gateway_id)
    parent[start] = (None, None)
    while queue:
        current = queue.popleft()
        for gw_id, next_id in _graph.get(current, []):
            if next_id in visited:
                continue
            visited.add(next_id)
            parent[next_id] = (current, gw_id)
            if next_id == target:
                # Odtwórz ścieżkę
                path = []
                node = target
                while node != start:
                    prev, gw = parent[node]
                    path.append((gw, node))
                    node = prev
                path.reverse()
                return path
            queue.append(next_id)
    return None


def bfs_distances(start_map_id):
    """
    BFS od start_map_id: zwraca dict map_id -> odległość (liczba przejść).
    Tylko mapy osiągalne z start.
    """
    _load_maps()
    start = _normalize_id(start_map_id)
    if start not in _graph:
        return {}
    dist = {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        d = dist[current]
        for _gw_id, next_id in _graph.get(current, []):
            if next_id not in dist:
                dist[next_id] = d + 1
                queue.append(next_id)
    return dist


def get_maps_with_npc(name_substring):
    """
    Zwraca listę map, na których występuje NPC o nazwie zawierającej name_substring.
    Każdy element: (map_id, map_name, total_count) – total_count to suma pól count
    ze wszystkich wpisów NPC na tej mapie pasujących do nazwy.
    """
    _load_maps()
    part = (name_substring or "").strip().lower()
    if not part:
        return []
    out = []
    for mid, info in _maps_data.items():
        map_name = (info.get("name") or "").strip() or mid
        npcs = info.get("npcs") or []
        total = 0
        for n in npcs:
            nname = (n.get("name") or "").strip().lower()
            if part in nname:
                total += int(n.get("count") or 0)
        if total > 0:
            out.append((mid, map_name, total))
    return sorted(out, key=lambda x: (-x[2], x[1].lower()))


def get_maps_with_npc_by_distance(name_substring, current_map_id):
    """
    Jak get_maps_with_npc, ale pogrupowane wg odległości BFS od current_map_id.
    Zwraca listę (etykieta_grupy, lista (map_id, map_name, count)):
    [ ("Na tej mapie", [(mid, name, count), ...]),
      ("1 przejście", [...]),
      ("2 przejścia", [...]), ... ]
    """
    maps_with_npc = get_maps_with_npc(name_substring)
    if not maps_with_npc:
        return []
    current = _normalize_id(current_map_id)
    dist_map = bfs_distances(current) if current else {}
    by_dist = {}  # distance -> [(map_id, map_name, count), ...]
    for mid, map_name, count in maps_with_npc:
        d = dist_map.get(mid)
        if d is None:
            d = 9999
        if d not in by_dist:
            by_dist[d] = []
        by_dist[d].append((mid, map_name, count))
    result = []
    for d in sorted(by_dist.keys()):
        if d == 0:
            label = "Na tej mapie"
        elif d == 1:
            label = "1 przejście"
        elif 2 <= d <= 4:
            label = "{} przejścia".format(d)
        else:
            label = "{} przejść".format(d)
        result.append((label, by_dist[d]))
    return result
