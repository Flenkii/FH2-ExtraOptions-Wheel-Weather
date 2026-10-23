# Changes in this fork compared to Extra Options 0.2.98

Fork of https://github.com/RokkuDayo/ForzaHorizon2_ExtraOptions – modified in October 2026 by Flenkii.

## New files
- `features/wheel_bridge.c` – G920 wheel as an Xbox wheel, force feedback (the game's own wheel programs; the old own FFB only as fallback), reconnect, log
- `features/wheel_soft.c/.h` - own implementation of the Xbox wheel class, used when the game copy has no `Microsoft.Xbox.Input.Wheel.dll`
- `features/ffb_vm.c/.h` – runs FH2's own Xbox wheel force-feedback programs on the PC
- `features/keyboard_pad.c/.h` – keyboard as a gamepad (merged with real gamepads)
- `features/wheel_buttons.c/.h` – assignable wheel buttons
- `features/rig_settings.c/.h` – in-game "Wheel & Traffic" page, traffic presets, saving to the INIs
- `features/traffic_tunables.c` – higher traffic limits, rush hour all day (live)
- `features/weather.c/.h` – fixed weather through the game's own weather control
- `features/ini_edit.c/.h` – edit INI lines without losing comments
- `adapters/azimuth_guard.c` – guard against a null pointer while loading under Azimuth
- `tools/` – Python scripts for the cockpit wheel, More Traffic and traffic variety, `make_release.py`
- `release/` – `FH2_ExtraOptions.ini`, `README.txt` and `Keybindings.txt` for the release ZIP
- `tests/` – emulator tests (unicorn)

## Changed files
- `video_options*.c/.h` – extra menu rows and choice lists on the HUD page
- `settings.c/.h`, `extra_options.h` – new INI keys `[Traffic] TrafficLevel, RushHourAllDay, Wetter`
- `vehicle_controls.c` – calls the weather control once per frame
- `adapters/azimuth.c` – hooks Azimuth's gamepad import for the keyboard
- `runtime.c`, `dllmain.c`, `features.h`, `build.py`, `kernel32.def`, `adapters/azimuth_host.h` – wiring for the new parts
- `README.md` – new; the original README is kept unchanged in `README_ORIGINAL.md`
