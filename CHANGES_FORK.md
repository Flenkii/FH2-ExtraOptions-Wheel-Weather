# Änderungen dieses Forks gegenüber Extra Options 0.2.98

Fork von https://github.com/RokkuDayo/ForzaHorizon2_ExtraOptions – geändert im Oktober 2026 von Flenkii.

## Neue Dateien
- `features/wheel_bridge.c` – G920-Lenkrad als Xbox-Lenkrad, DirectInput-Force-Feedback, Wiederverbinden, Protokoll
- `features/wheel_buttons.c/.h` – frei belegbare Lenkrad-Tasten
- `features/rig_settings.c/.h` – Menüseite „Lenkrad & Verkehr“, FFB-Profile, Verkehrs-Voreinstellungen, Speichern in die INIs
- `features/traffic_tunables.c` – höhere Verkehrsgrenzen, Rushhour rund um die Uhr (live)
- `features/weather.c/.h` – festes Wetter über die spieleigene Wetter-Steuerung
- `features/ini_edit.c/.h` – INI-Zeilen ändern, ohne Kommentare zu verlieren
- `adapters/azimuth_guard.c` – Schutz gegen einen Null-Zeiger beim Laden unter Azimuth
- `tools/` – Python-Skripte für Cockpit-Lenkrad, More Traffic und Verkehrs-Vielfalt
- `tests/` – Emulator-Tests (unicorn)

## Geänderte Dateien
- `video_options*.c/.h` – zusätzliche Menüzeilen und Auswahllisten auf der HUD-Seite
- `settings.c/.h`, `extra_options.h` – neue INI-Schlüssel `[Traffic] TrafficLevel, RushHourAllDay, Wetter`
- `vehicle_controls.c` – ruft pro Bild die Wetter-Steuerung auf
- `runtime.c`, `dllmain.c`, `features.h`, `build.py`, `kernel32.def`, `adapters/azimuth_host.h` – Einbindung der neuen Teile
- `README.md` – neu; das Original-README liegt unverändert in `README_ORIGINAL.md`
