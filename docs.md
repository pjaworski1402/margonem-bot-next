# Dokumentacja API Margonem

Kompletna dokumentacja komend i funkcji dostępnych w konsoli gry Margonem (F12). Wszystkie komendy można używać bezpośrednio w konsoli przeglądarki lub przez WebSocket w botach.

---

## 1. Komendy akcji (_g)

Komendy wysyłane do serwera przez funkcję `_g(taskString, callback, payload)`.

**Funkcja:** `_g(taskString, callback, payload)`
- `taskString` - ciąg komendy w formacie `ZADANIE&param1=wartość&param2=wartość`
- `callback` - opcjonalna funkcja zwrotna, otrzymuje odpowiedź z serwera
- `payload` - opcjonalny obiekt JSON wysyłany jako `p` w wiadomości WebSocket

### Rozmowa i dialogi

```javascript
_g("talk&id=ID")                    // Rozpoczęcie rozmowy z NPC o danym ID
_g("talk&id=ID&c=N")                // Wybór opcji dialogowej o numerze c
_g("talk&action=cancel")            // Zamknięcie okna dialogu
```

**Schemat odpowiedzi:**
- Odpowiedź zawiera strukturę dialogów w pakiecie WebSocket
- Parsuj przez `getFullDataPackage()` po wywołaniu
- Może zawierać opcje wyboru, informacje o handlu, questy

### Walka

```javascript
_g("fight&a=attack&id=ID")          // Atak na potwora/gracza o danym ID
_g("fight&a=f")                     // Szybka walka (auto-wynik)
_g("f")                             // Skrót dla szybkiej walki
```

**Schemat odpowiedzi:**
- Pakiet zawiera wynik walki (obrażenia, HP przeciwnika)
- Po zakończeniu walki dostępny loot przez `loot&quality=N`
- Sprawdzaj `Engine.lock.check("battle")` aby wiedzieć kiedy walka się kończy

### Przedmioty i loot

```javascript
_g("loot&quality=N")                // Podniesienie przedmiotów po walce (N = jakość)
_g("takeitem&id=ID")                // Podniesienie przedmiotu leżącego na ziemi
_g("moveitem&id=ID&st=N")           // Przeniesienie przedmiotu do slotu/plecaka (st = slot)
```

**Schemat odpowiedzi:**
- `takeitem` - potwierdzenie podniesienia lub błąd
- `loot` - lista podniesionych przedmiotów
- `moveitem` - potwierdzenie przeniesienia lub błąd (np. pełny plecak)

**Przydatne dla bota:**
- Użyj `quality` w `loot` do filtrowania jakości (0=wszystko, wyższe=lepsze)
- Sprawdzaj odpowiedź aby upewnić się że przedmiot został podniesiony
- `st` w `moveitem` to numer slotu w plecaku (0-N)

### Poczta

```javascript
_g("mail&a=send&to=NICK&subj=T&body=B")  // Wysyłanie poczty (to = odbiorca, subj = temat, body = treść)
```

**Schemat odpowiedzi:**
- Potwierdzenie wysłania lub błąd (np. nieprawidłowy odbiorca)
- Parsuj `getFullDataPackage()` aby sprawdzić status

### Sklep

```javascript
_g("shop&buy=ID")                   // Zakup przedmiotu (ID z Engine.shop.items)
_g("shop&buy=&sell=ID")             // Sprzedaż przedmiotu (buy=puste, sell=ID przedmiotu)
```

**Schemat odpowiedzi:**
- Potwierdzenie transakcji lub błąd (np. brak złota, pełny plecak)
- Aktualizacja `Engine.hero.d.gold` po transakcji
- Sprawdzaj odpowiedź aby upewnić się że transakcja się powiodła

---

## 2. Bohater (Engine.hero)

### Właściwości statystyk

```javascript
Engine.hero.d.warrior_stats.hp      // Aktualne HP (liczba)
Engine.hero.d.warrior_stats.maxhp   // Maksymalne HP (liczba)
Engine.hero.d.lvl                   // Poziom postaci (liczba)
Engine.hero.d.gold                  // Ilość złota (liczba)
Engine.hero.d.credits               // Credity premium (liczba)
Engine.hero.d.prof                  // Kod profesji
Engine.hero.d.warrior_stats.profession  // Nazwa profesji (tekst)
Engine.hero.d.nick                  // Nick postaci
Engine.hero.d.id                    // ID postaci
Engine.hero.d.img                   // Ścieżka do obrazka (outfit)
```

### Współrzędne i pozycja

```javascript
Engine.hero.d.x                     // Współrzędna X bohatera (kratki mapy)
Engine.hero.d.y                     // Współrzędna Y bohatera (kratki mapy)
Engine.hero.d.dir                   // Kierunek (0-3: S=0, W=1, E=2, N=3)
Engine.hero.x                       // Współrzędna X (alternatywna)
Engine.hero.y                       // Współrzędna Y (alternatywna)
```

### Metody bohatera

```javascript
Engine.hero.getX()                  // Zwraca współrzędną X bohatera (metoda)
Engine.hero.getY()                  // Zwraca współrzędną Y bohatera (metoda)
Engine.hero.getLevel()              // Zwraca poziom postaci (metoda)
Engine.hero.autoGoTo({x, y})        // Automatyczne chodzenie do celu o współrzędnych x, y
```

**Funkcja:** `autoGoTo({x, y})`
- Automatycznie prowadzi bohatera do wskazanych współrzędnych
- Parametr: obiekt z właściwościami `x` i `y` (współrzędne w kratkach mapy)

### Schemat danych bohatera

**Struktura obiektu `Engine.hero.d`:**
```javascript
{
  warrior_stats: {
    hp: Number,              // Aktualne HP
    maxhp: Number,           // Maksymalne HP
    profession: String       // Nazwa profesji (np. "Paladyn")
  },
  lvl: Number,               // Poziom postaci
  gold: Number,              // Ilość złota
  credits: Number,            // Credity premium
  prof: String,              // Kod profesji (np. "p" dla paladyna)
  nick: String,              // Nick postaci
  id: Number,                // ID postaci
  img: String,               // Ścieżka do obrazka outfit (np. "/noob/pm.gif")
  x: Number,                 // Współrzędna X (kratki mapy)
  y: Number,                 // Współrzędna Y (kratki mapy)
  dir: Number                // Kierunek: 0=S, 1=W, 2=E, 3=N
}
```

**Przydatne dla bota:**
- `hp` i `maxhp` - sprawdzanie zdrowia przed walką
- `x`, `y` - aktualna pozycja do nawigacji
- `dir` - kierunek patrzenia (przydatne przy interakcjach)
- `gold` - sprawdzanie zasobów przed zakupami
- `lvl` - wymagania poziomu dla przedmiotów/questów

---

## 3. Mapa (Engine.map)

### Informacje o mapie

```javascript
Engine.map.d.id                     // ID mapy (liczba)
Engine.map.d.name                   // Nazwa mapy (tekst)
Engine.map.size.x                   // Szerokość mapy w kratkach
Engine.map.size.y                   // Wysokość mapy w kratkach
```

**Przykład użycia:**
```javascript
console.log("Mapa ID:", Engine.map.d.id, "Nazwa:", Engine.map.d.name, 
            "Rozmiar:", Engine.map.size.x, "x", Engine.map.size.y);
```

### Schemat danych mapy

**Struktura obiektu `Engine.map`:**
```javascript
{
  d: {
    id: Number,              // ID mapy
    name: String            // Nazwa mapy (np. "Ithan")
  },
  size: {
    x: Number,              // Szerokość mapy w kratkach
    y: Number               // Wysokość mapy w kratkach
  }
}
```

**Przydatne dla bota:**
- `size.x`, `size.y` - granice mapy do walidacji współrzędnych
- `d.id` - identyfikacja mapy (przydatne przy nawigacji między mapami)
- `d.name` - nazwa mapy do logowania/debugowania

### Przedmioty na ziemi

```javascript
Engine.items.getOnGround()          // Pobranie listy przedmiotów na ziemi (metoda)
```

**Alternatywne metody dostępu:**
```javascript
Engine.map.groundItems.getDrawableItems()  // Zwraca tablicę przedmiotów do rysowania
Engine.map.groundItems.getGroundItemOnPosition(x, y)  // Przedmiot na konkretnych współrzędnych
Engine.map.groundItems.getItemById(itemId)  // Przedmiot po ID
```

**Funkcja:** `getDrawableItems()`
- Zwraca tablicę obiektów przedmiotów na ziemi
- Każdy element ma właściwość `.i` zawierającą dane przedmiotu (id, x, y, name)

**Funkcja:** `getGroundItemOnPosition(x, y)`
- Zwraca przedmiot znajdujący się na wskazanych współrzędnych
- Parametry: `x`, `y` - współrzędne w kratkach mapy

**Funkcja:** `getItemById(itemId)`
- Zwraca wrapper przedmiotu o danym ID
- Parametr: `itemId` - ID przedmiotu

**Przykład - lista wszystkich przedmiotów:**
```javascript
var raw = Engine.map.groundItems.getDrawableItems();
var items = [];
for (var i = 0; i < raw.length; i++) {
  var o = raw[i];
  if (o && o.i) {
    items.push({ id: o.i.id, x: o.i.x, y: o.i.y, name: o.i.name || "" });
  }
}
console.table(items);
```

### Schemat danych przedmiotów na ziemi

**Struktura elementu z `getDrawableItems()`:**
```javascript
{
  i: {
    id: String,             // ID przedmiotu (string, np. "1470652032")
    x: Number,              // Współrzędna X
    y: Number,              // Współrzędna Y
    name: String,           // Nazwa przedmiotu (np. "Kły psa")
    _cachedStats: {         // Cache statystyk przedmiotu
      amount: String,       // Ilość (np. "5")
      cansplit: String,     // Czy można podzielić ("1" lub "0")
      capacity: String,      // Pojemność (dla pojemników)
      rarity: String        // Rzadkość (np. "common", "rare", "epic")
    },
    itemType: String,       // Typ przedmiotu (np. "t-norm")
    onload: Boolean,        // Czy przedmiot jest załadowany
    // ... wiele innych właściwości i metod
  }
}
```

**Przydatne dla bota:**
- `i.id` - ID do użycia w `takeitem&id=ID`
- `i.x`, `i.y` - pozycja do nawigacji (`autoGoTo`)
- `i.name` - filtrowanie przedmiotów po nazwie
- `i._cachedStats.rarity` - priorytetyzacja lootu (rzadsze = lepsze)
- `i._cachedStats.amount` - ilość przedmiotu (przydatne przy stackach)

**Uwaga:** Struktura może się różnić w zależności od typu przedmiotu i stanu załadowania.

### Bramy (gateways)

```javascript
Engine.map.gateways.getOpenGtwAtPosition(x, y)  // Sprawdzenie otwartych przejść na pozycji
Engine.map.gateways.getList()                    // Lista wszystkich bram (tablica)
Engine.map.gateways.getGtwAtPosition(x, y)       // Brama na konkretnych współrzędnych
```

**Funkcja:** `getList()`
- Zwraca tablicę wszystkich bram na mapie
- Każda brama ma właściwości `.d.id`, `.d.x`, `.d.y`

**Funkcja:** `getGtwAtPosition(x, y)`
- Zwraca bramę znajdującą się na wskazanych współrzędnych
- Parametry: `x`, `y` - współrzędne w kratkach mapy

**Przykład - lista wszystkich bram:**
```javascript
var gates = Engine.map.gateways.getList();
var list = [];
for (var i = 0; i < gates.length; i++) {
  var g = gates[i];
  if (g && g.d) {
    list.push({ id: g.d.id, x: g.d.x, y: g.d.y });
  }
}
console.table(list);
```

### Schemat danych bram (gateways)

**Struktura elementu z `getList()`:**
```javascript
{
  d: {
    id: Number,             // ID bramy (np. 138, 34, 2720)
    x: Number,              // Współrzędna X
    y: Number,              // Współrzędna Y
    key: Number,            // Wymagany klucz (0 = brak wymogu)
    lvl: Number,            // Wymagany poziom (0 = brak wymogu)
    affectedId: String      // Unikalny identyfikator (np. "138x0y66")
  }
}
```

**Przydatne dla bota:**
- `d.id` - identyfikacja typu bramy (różne ID = różne przejścia)
- `d.x`, `d.y` - pozycja do nawigacji
- `d.key` - sprawdzanie wymagań klucza przed przejściem
- `d.lvl` - sprawdzanie wymagań poziomu
- `d.affectedId` - unikalny identyfikator pozycji (przydatne do cache'owania)

**Uwaga:** Bramy mogą mieć wiele pozycji na mapie (ten sam `id` na różnych `x,y`).

---

## 4. NPC (Engine.npcs)

### Pobieranie listy NPC

```javascript
Engine.npcs.check()                 // Pobranie listy wszystkich NPC na mapie
```

**Funkcja:** `check()`
- Zwraca obiekt, gdzie klucz = ID NPC, wartość = obiekt NPC
- Każdy NPC ma właściwości `.d.id`, `.d.x`, `.d.y`, `.d.nick`

**Funkcja:** `getById(npcId)`
- Zwraca NPC o danym ID
- Parametr: `npcId` - ID NPC do znalezienia

**Przykład - lista wszystkich NPC:**
```javascript
var npcs = Engine.npcs.check();
var list = [];
for (var id in npcs) {
  var n = npcs[id];
  if (n && n.d) {
    list.push({ id: n.d.id, x: n.d.x, y: n.d.y, nick: n.d.nick || "" });
  }
}
console.table(list);
```

**Przykład - pojedynczy NPC:**
```javascript
var npcId = 300543; // zmień na ID z gry
var npc = Engine.npcs.getById(npcId);
if (npc && npc.d) {
  console.log("NPC id:", npc.d.id, "x:", npc.d.x, "y:", npc.d.y, "nick:", npc.d.nick);
} else {
  console.log("Brak NPC o id", npcId);
}
```

### Schemat danych NPC

**Struktura obiektu NPC (`Engine.npcs.check()[id]` lub `getById(id)`):**
```javascript
{
  d: {
    id: Number,             // ID NPC (np. 1, 66, 5552)
    x: Number,              // Współrzędna X
    y: Number,              // Współrzędna Y
    nick: String,           // Nazwa NPC (np. "Uzdrowicielka Makatara", "Szczur")
    behavior: Object | null // Obiekt zachowania (może zawierać listę dialogów)
  }
}
```

**Przydatne dla bota:**
- `d.id` - ID do użycia w `talk&id=ID`
- `d.x`, `d.y` - pozycja do nawigacji przed rozmową
- `d.nick` - identyfikacja NPC po nazwie (np. znajdź "Sprzedawca")
- `d.behavior` - może zawierać informacje o dialogach (struktura zależy od serwera)

**Uwaga:** Niektóre NPC to potwory (mogą mieć agresywne zachowanie), inne to NPC handlowe/questowe.

### Dialogi NPC

NPC mogą mieć listę dialogów w `npc.d.behavior.list` (jeśli serwer je przysłał).

**Przykład - sprawdzenie dialogów:**
```javascript
var npcs = Engine.npcs.check();
for (var id in npcs) {
  var n = npcs[id];
  if (n && n.d && n.d.behavior && n.d.behavior.list) {
    console.log("NPC id=" + n.d.id + " ma behavior.list:", n.d.behavior.list);
  }
}
```

**Schemat odpowiedzi z `talk&id=ID`:**
Odpowiedź z serwera (przez `getFullDataPackage()` lub WebSocket) może zawierać:
- Strukturę dialogów z opcjami wyboru
- Informacje o dostępnych akcjach (handel, questy)
- Komunikaty błędów jeśli NPC nie jest dostępny

**Uwaga:** Struktura odpowiedzi zależy od typu NPC i dostępnych akcji. Parsuj `getFullDataPackage()` po wywołaniu `talk`.

---

## 5. Float Objects (obiekty na mapie)

Obiekty "pływające" (rośliny, zbieralne, dekoracje) dostępne przez `Engine.floatObjectManager`.

```javascript
Engine.floatObjectManager.getDrawableList()  // Lista wszystkich float objects
```

**Funkcja:** `getDrawableList()`
- Zwraca tablicę obiektów na mapie (rośliny, zbieralne, dekoracje)
- Każdy element ma właściwości `.id`, `.x`, `.y` (lub `.d.x`, `.d.y` w zależności od implementacji)

**Przykład - lista float objects:**
```javascript
var list = Engine.floatObjectManager.getDrawableList();
var out = [];
for (var i = 0; i < list.length; i++) {
  var o = list[i];
  if (o && (o.id !== undefined) && (o.x !== undefined)) {
    out.push({ id: o.id, x: o.x, y: o.y });
  }
}
console.table(out);
```

### Schemat danych Float Objects

**Struktura elementu z `getDrawableList()`:**
```javascript
{
  id: Number,               // ID obiektu
  x: Number,                // Współrzędna X (lub o.d.x jeśli struktura zagnieżdżona)
  y: Number,                // Współrzędna Y (lub o.d.y jeśli struktura zagnieżdżona)
  // ... inne właściwości zależne od typu obiektu
}
```

**Alternatywna struktura (zagnieżdżona):**
```javascript
{
  id: Number,
  d: {
    x: Number,
    y: Number
  }
}
```

**Przydatne dla bota:**
- `id` - identyfikacja typu obiektu (rośliny, zbieralne mają różne ID)
- `x`, `y` - pozycja do nawigacji i zbierania
- Użyj `talk&id=ID` do interakcji z zbieralnymi obiektami

**Uwaga:** Struktura może się różnić w zależności od typu obiektu. Sprawdź czy `x` jest bezpośrednio w obiekcie czy w `d.x`.

---

## 6. Komunikacja (Engine.communication)

### Odczyt danych

```javascript
Engine.communication.getFullDataPackage()  // Odczyt ostatniego surowego pakietu JSON
```

**Funkcja:** `getFullDataPackage()`
- Zwraca ostatni pełny pakiet JSON otrzymany z serwera przez WebSocket
- Zawiera m.in. `h` (hero update), `npcs_del`, `item`, `chat` - zależnie od ostatniego żądania
- Przydatne do parsowania dialogów, lootu, błędów

### Schemat danych komunikacji

**Struktura pakietu z `getFullDataPackage()`:**
```javascript
{
  ev: Number,               // Timestamp zdarzenia (Unix timestamp z mikrosekundami)
  e: String,                // Status odpowiedzi (np. "ok", "error")
  lag: Number,              // Opóźnienie w milisekundach
  other: {                  // Inne gracze na mapie
    [playerId]: {
      id: String,           // ID gracza
      x: Number,            // Współrzędna X
      y: Number,            // Współrzędna Y
      dir: Number           // Kierunek (0-3)
    }
  },
  h: Object,                // Aktualizacja bohatera (jeśli była)
  npcs_del: Array,          // Lista usuniętych NPC (jeśli były)
  item: Object,             // Informacje o przedmiocie (jeśli była akcja z przedmiotem)
  chat: Object,             // Wiadomości czatu (jeśli były)
  // ... inne pola zależne od typu odpowiedzi
}
```

**Przydatne dla bota:**
- `e` - sprawdzanie czy akcja się powiodła ("ok" vs "error")
- `h` - aktualizacja statystyk bohatera po akcji
- `other` - lista innych graczy (przydatne do unikania lub interakcji)
- `item` - informacje o przedmiotach po akcjach (loot, podniesienie)
- `lag` - monitorowanie opóźnienia sieci

**Uwaga:** Struktura pakietu różni się w zależności od typu odpowiedzi serwera. Zawsze sprawdzaj obecność pól przed użyciem.

### Wysyłanie komend

```javascript
Engine.communication.send2("TASK")  // Wysłanie komendy z pominięciem kolejki
```

**Funkcja:** `send2(task, callback, payload)`
- Wysyła komendę do serwera omijając limit czasu między requestami
- Parametry: `task` - ciąg komendy, `callback` - opcjonalna funkcja zwrotna, `payload` - opcjonalny obiekt JSON

---

## 7. Blokady i stany (Engine.lock)

```javascript
Engine.lock.check()                    // Sprawdzenie, czy postać jest zablokowana (ogólnie)
Engine.lock.check("change_location")  // Sprawdzenie blokady zmiany mapy
Engine.lock.check("npcdialog")        // Sprawdzenie blokady dialogu z NPC
Engine.lock.check("logoff")           // Sprawdzenie blokady wylogowania
Engine.lock.check("battle")           // Sprawdzenie blokady walki
```

**Funkcja:** `check(lockType)`
- Bez argumentu: zwraca `true` jeśli cokolwiek blokuje akcje
- Z argumentem: sprawdza konkretny typ blokady
- Przydatne gdy bot ma czekać, aż zamknie się dialog/walka zanim wyśle ruch lub talk

### Schemat danych blokad

**Wartości zwracane przez `Engine.lock.check()`:**
```javascript
// Ogólne sprawdzenie
Engine.lock.check()                    // Boolean - true jeśli jakakolwiek blokada aktywna

// Konkretne typy blokad
Engine.lock.check("change_location")  // Boolean - blokada zmiany mapy
Engine.lock.check("npcdialog")        // Boolean - blokada dialogu z NPC
Engine.lock.check("logoff")           // Boolean - blokada wylogowania
Engine.lock.check("battle")           // Boolean - blokada walki
```

**Przydatne dla bota:**
- Sprawdzaj `check("battle")` przed próbą ruchu podczas walki
- Sprawdzaj `check("npcdialog")` przed wysłaniem kolejnej komendy podczas dialogu
- Sprawdzaj `check("change_location")` przed próbą przejścia przez bramę
- Użyj ogólnego `check()` jako szybkiego sprawdzenia czy można wykonać akcję

**Przykład użycia:**
```javascript
if (!Engine.lock.check("battle")) {
  Engine.hero.autoGoTo({x: 10, y: 10});
} else {
  console.log("Czekam na zakończenie walki...");
}
```

---

## 8. Sklep (Engine.shop)

```javascript
Engine.shop.items                     // Tablica przedmiotów w sklepie (ma id i name)
```

**Właściwość:** `items`
- Tablica obiektów reprezentujących przedmioty dostępne w sklepie
- Każdy element ma właściwości `id` i `name`

### Schemat danych sklepu

**Struktura elementu z `Engine.shop.items`:**
```javascript
{
  id: Number,               // ID przedmiotu w sklepie
  name: String,             // Nazwa przedmiotu
  // ... inne właściwości zależne od implementacji
}
```

**Przydatne dla bota:**
- `id` - ID do użycia w `shop&buy=ID` (zakup) lub `shop&sell=ID` (sprzedaż)
- `name` - identyfikacja przedmiotu po nazwie
- Sprawdź `Engine.shop.items` tylko gdy jesteś w sklepie (otwarte okno sklepu)

**Uwaga:** Sklep może być pusty (`{}`) jeśli nie jesteś w sklepie lub sklep nie ma przedmiotów.

---

## 9. Przykład: Jednorazowy audyt mapy

Poniższy kod wypisze w konsoli wszystkie informacje o mapie: mapę, bohatera, NPC, przedmioty na ziemi, bramy, float objects.

```javascript
(function() {
  console.log("=== MAPA ===");
  console.log("ID:", Engine.map.d.id, "Nazwa:", Engine.map.d.name, 
              "Rozmiar:", Engine.map.size.x, "x", Engine.map.size.y);
  
  console.log("=== BOHATER ===");
  console.log("x:", Engine.hero.d.x, "y:", Engine.hero.d.y, "dir:", Engine.hero.d.dir);
  console.log("HP:", Engine.hero.d.warrior_stats.hp + "/" + Engine.hero.d.warrior_stats.maxhp);
  console.log("Poziom:", Engine.hero.d.lvl, "Złoto:", Engine.hero.d.gold);
  
  console.log("=== NPC ===");
  var npcs = Engine.npcs.check();
  var nList = [];
  for (var id in npcs) {
    var n = npcs[id];
    if (n && n.d) nList.push({ id: n.d.id, x: n.d.x, y: n.d.y, nick: n.d.nick || "" });
  }
  console.table(nList);
  
  console.log("=== PRZEDMIOTY NA ZIEMI ===");
  var raw = Engine.map.groundItems.getDrawableItems();
  var gList = [];
  for (var i = 0; i < raw.length; i++) {
    if (raw[i] && raw[i].i) {
      gList.push({ id: raw[i].i.id, x: raw[i].i.x, y: raw[i].i.y, name: raw[i].i.name || "" });
    }
  }
  console.table(gList);
  
  console.log("=== BRAMY ===");
  var gates = Engine.map.gateways.getList();
  var gwList = [];
  for (var j = 0; j < gates.length; j++) {
    if (gates[j] && gates[j].d) {
      gwList.push({ id: gates[j].d.id, x: gates[j].d.x, y: gates[j].d.y });
    }
  }
  console.table(gwList);
  
  console.log("=== FLOAT OBJECTS ===");
  var fl = Engine.floatObjectManager.getDrawableList();
  var flList = [];
  for (var k = 0; k < fl.length; k++) {
    var o = fl[k];
    if (o && o.id != null && (o.x != null || o.d)) {
      flList.push({ 
        id: o.id, 
        x: o.x != null ? o.x : (o.d && o.d.x), 
        y: o.y != null ? o.y : (o.d && o.d.y) 
      });
    }
  }
  console.table(flList);
  
  console.log("=== KONIEC ===");
})();
```

---

## 10. Uwagi i wskazówki

- **Wszystkie komendy** można używać w konsoli przeglądarki (F12) po załadowaniu gry
- **Format komend:** `ZADANIE&param1=wartość&param2=wartość`
- **Współrzędne** są w kratkach mapy (logiczne pozycje)
- **Struktura danych** może się różnić w zależności od wersji gry - sprawdź w konsoli strukturę obiektów przed użyciem
- **Bot przez WebSocket:** komendy `_g(...)` można wysyłać przez WebSocket (`wss://.../ws-engine`) w formacie zadań
- **Decyzje bota** powinny być oparte na danych z `Engine.*` przed wysłaniem akcji

---

## 11. Przydatne zastosowania

### Zbieranie rumianków / przedmiotów
Znajdź float objects lub ground items o wybranym typie (np. po nazwie), weź ich `x,y`, użyj `Engine.hero.autoGoTo({x,y})` i wyślij akcję zbierania (`talk` do obiektu lub `takeitem`).

### Dialogi z NPC
Dla każdego NPC masz `id`, `x`, `y`; wyślij `_g("talk&id=" + id)` i parsuj odpowiedź z `Engine.communication.getFullDataPackage()` lub odpowiedzi WebSocket.

### Automatyczna nawigacja
Użyj `Engine.map.gateways.getList()` aby znaleźć przejścia, `Engine.hero.autoGoTo()` do poruszania się, i `Engine.lock.check()` aby sprawdzić czy można wykonać akcję.

---

## 12. Wskazówki dla bota - najlepsze praktyki

### Sprawdzanie stanu przed akcją

**Zawsze sprawdzaj blokady przed akcją:**
```javascript
if (!Engine.lock.check("battle") && !Engine.lock.check("npcdialog")) {
  // Możesz wykonać akcję
  Engine.hero.autoGoTo({x: targetX, y: targetY});
}
```

**Sprawdzaj zdrowie przed walką:**
```javascript
var hpPercent = Engine.hero.d.warrior_stats.hp / Engine.hero.d.warrior_stats.maxhp;
if (hpPercent < 0.3) {
  // Uciekaj lub użyj mikstury
}
```

**Sprawdzaj zasoby przed zakupami:**
```javascript
if (Engine.hero.d.gold >= requiredGold) {
  _g("shop&buy=" + itemId);
}
```

### Parsowanie odpowiedzi z serwera

**Używaj callbacków i getFullDataPackage():**
```javascript
_g("talk&id=" + npcId, function(response) {
  var pakiet = Engine.communication.getFullDataPackage();
  if (pakiet && pakiet.e === "ok") {
    // Parsuj dialogi z pakietu
  } else {
    console.log("Błąd:", pakiet.e);
  }
});
```

### Nawigacja i znajdowanie obiektów

**Znajdź najbliższy przedmiot:**
```javascript
function znajdzNajblizszyPrzedmiot(nazwa) {
  var items = Engine.map.groundItems.getDrawableItems();
  var heroX = Engine.hero.d.x;
  var heroY = Engine.hero.d.y;
  var najblizszy = null;
  var minOdleglosc = Infinity;
  
  for (var i = 0; i < items.length; i++) {
    if (items[i] && items[i].i && items[i].i.name === nazwa) {
      var dx = items[i].i.x - heroX;
      var dy = items[i].i.y - heroY;
      var odleglosc = Math.sqrt(dx*dx + dy*dy);
      if (odleglosc < minOdleglosc) {
        minOdleglosc = odleglosc;
        najblizszy = items[i].i;
      }
    }
  }
  return najblizszy;
}
```

**Znajdź NPC po nazwie:**
```javascript
function znajdzNPC(nazwa) {
  var npcs = Engine.npcs.check();
  for (var id in npcs) {
    if (npcs[id] && npcs[id].d && npcs[id].d.nick === nazwa) {
      return npcs[id].d;
    }
  }
  return null;
}
```

### Obsługa błędów

**Zawsze sprawdzaj odpowiedzi:**
```javascript
_g("takeitem&id=" + itemId, function(response) {
  var pakiet = Engine.communication.getFullDataPackage();
  if (pakiet && pakiet.e !== "ok") {
    console.log("Nie udało się podnieść przedmiotu:", pakiet.e);
    // Spróbuj ponownie lub przejdź do następnego
  }
});
```

### Optymalizacja wydajności

- **Cache'uj dane:** Nie odświeżaj listy NPC/przedmiotów w każdej pętli
- **Używaj timeoutów:** Daj czas serwerowi na odpowiedź przed kolejną akcją
- **Sprawdzaj granice mapy:** Waliduj współrzędne przed `autoGoTo()`

**Przykład z timeoutem:**
```javascript
function wykonajAkcjeZOpóźnieniem(akcja, delay) {
  setTimeout(function() {
    if (!Engine.lock.check()) {
      _g(akcja);
    }
  }, delay || 500);
}
```

### Ważne uwagi

- **Struktury danych mogą się różnić** - zawsze sprawdzaj obecność właściwości przed użyciem
- **ID mogą być stringami lub liczbami** - sprawdzaj typ przed porównaniem
- **Niektóre obiekty mogą być null** - zawsze sprawdzaj `if (obj && obj.property)`
- **Odpowiedzi serwera są asynchroniczne** - używaj callbacków lub czekaj na `getFullDataPackage()`
