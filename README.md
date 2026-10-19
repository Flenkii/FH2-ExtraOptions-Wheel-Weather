# Forza Horizon 2 – Extra Options + Lenkrad, Verkehr & Wetter (inoffizieller Fork)

Dies ist ein **inoffizieller Fork** von [RokkuDayo/ForzaHorizon2_ExtraOptions](https://github.com/RokkuDayo/ForzaHorizon2_ExtraOptions)
(Version 0.2.98) für die Xbox-One-Version von Forza Horizon 2 mit dem Wrapper **Azimuth**.
Alle Funktionen des Originals sind unverändert enthalten – die Beschreibung dazu steht in
[README_ORIGINAL.md](README_ORIGINAL.md). Dieser Fork ergänzt:

| Funktion | Kurz erklärt |
|---|---|
| **Lenkrad-Brücke (Logitech G920)** | Das Lenkrad wird dem Spiel als Xbox-Lenkrad gemeldet: Lenkung, Pedale, Kupplung, H-Schaltung, Tasten. |
| **Force Feedback** | Eigene FFB-Berechnung über DirectInput (Kraft aus dem Fahrverhalten, Vibration, Dämpfung, Reibung, Zentrierung …) mit 5 Profilen. |
| **Freie Lenkrad-Tasten** | RSB, LSB und Xbox-Taste frei belegbar (Blick zurück/links/rechts, Kamera, Handbremse, Radio, Schalten …). |
| **Menü „Lenkrad & Verkehr“ im Spiel** | Optionen › HUD › ganz unten. Alle Werte wirken sofort und werden gespeichert. |
| **Mehr Verkehr** | Verkehrsgrenzen bis 100 Autos, Rushhour rund um die Uhr, Voreinstellungen Original/Ruhig/Lebhaft/Rushhour/Chaos. |
| **Festes Wetter** | Sonnig, Bewölkt, Gewitterwolken, Regen oder Nebel – über die spieleigene Wetter-Steuerung, ohne Spieldateien zu ändern. |
| **Werkzeuge** (`tools/`) | Skripte für Cockpit-Lenkrad, More-Traffic-Dateien und „Verkehrs-Vielfalt“ (20 zusätzliche Verkehrsmodelle). |

> 🚨 **Sicherheit:** Siehe die Warnung des Original-Autors in [README_ORIGINAL.md](README_ORIGINAL.md):
> Betrüger verbreiten unter dem Namen dieser Mod Keylogger. **Dieser Fork verlangt nie, Befehle in PowerShell
> einzufügen oder ein „All-in-One“-Installationsprogramm auszuführen.** Die Mod besteht nur aus `winmm.dll` und INI-Dateien.
> Lade Dateien nur von den Releases dieses Repositorys oder baue sie selbst aus dem Quellcode.

> ⚠️ **Inoffiziell.** Weder der Autor von Extra Options noch der Entwickler von Azimuth unterstützen diesen Fork.
> Bitte meldet Fehler, die mit diesem Fork auftreten, **nicht** bei ihnen. Azimuth-Fehler nur ohne Mods melden.

## Was hier NICHT enthalten ist
- Keine Spieldateien von Forza Horizon 2 (keine EXE, keine Datenbank, keine Grafiken/XAML).
- Kein Azimuth. Den gibt es nur beim Entwickler: <https://almost-there-games.itch.io/azimuth>
- Die Skripte in `tools/` erzeugen ihre Dateien **auf deinem PC aus deinen eigenen Spieldateien**.

## Installation (Azimuth)
1. Azimuth installieren und das Spiel einmal normal starten.
2. Aus dem Release `winmm.dll` und `FH2_ExtraOptions.ini` in den Azimuth-Ordner kopieren (neben `azimuth.exe`).
   Vorher die alte `winmm.dll` sichern.
3. Lenkrad: In G HUB 900° lassen. Einstellungen stehen in `FH2_Lenkrad.ini` (wird beim ersten Start angelegt)
   und im Spiel unter Optionen › HUD › ganz unten.

Neue INI-Schlüssel dieses Forks in `FH2_ExtraOptions.ini`, Abschnitt `[Traffic]`:
`TrafficLevel` (0–5), `RushHourAllDay` (0/1), `Wetter` (0 Original, 1 Sonnig, 2 Bewölkt, 3 Gewitterwolken, 4 Regen, 5 Nebel).

## Selbst bauen
Wie im Original (siehe [BUILD.md](BUILD.md)): `python build.py /pfad/zu/zig --azimuth`.
Tests (Emulator, brauchen `unicorn` und `pefile` sowie lokal entpackte Spieldateien in `FH2_GAME`):
```
python build.py /pfad/zu/zig --azimuth --test --output tests/winmm_test.dll
cd tests && python test_menu.py winmm_test.dll && python test_buttons.py winmm_test.dll && python test_weather.py winmm_test.dll
```

## Lizenz
GPL-3.0 wie das Original (siehe [LICENSE](LICENSE)). Änderungen gegenüber dem Original sind in
[CHANGES_FORK.md](CHANGES_FORK.md) aufgelistet.

## KI-Hinweis
Wie beim Original: Der Code dieses Forks wurde mit Hilfe einer KI (Claude von Anthropic) geschrieben und
im Emulator sowie im Spiel getestet.

---

### English summary
Unofficial fork of Forza Horizon 2 Extra Options 0.2.98 (Azimuth). Adds a Logitech G920 wheel bridge with
DirectInput force feedback and profiles, free wheel buttons, an in-game "Wheel & Traffic" page (HUD options),
higher traffic limits with presets and fixed weather via the game's own weather control. No game files or Azimuth binaries are included. GPL-3.0.
Not supported by the original authors – please don't report fork issues to them.
