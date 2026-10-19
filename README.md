# Forza Horizon 2 – Extra Options + Wheel, Traffic & Weather (unofficial fork)

This is an **unofficial fork** of [RokkuDayo/ForzaHorizon2_ExtraOptions](https://github.com/RokkuDayo/ForzaHorizon2_ExtraOptions)
(version 0.2.98) for the Xbox One version of Forza Horizon 2 running on the **Azimuth** wrapper.
All features of the original are included unchanged – see [README_ORIGINAL.md](README_ORIGINAL.md). This fork adds:

| Feature | In short |
|---|---|
| **Wheel bridge (Logitech G920)** | The wheel is reported to the game as an Xbox wheel: steering, pedals, clutch, H-shifter, buttons. |
| **Force feedback** | Own FFB through DirectInput (forces from the car's handling, rumble, damping, friction, centering …) with 5 profiles. |
| **Free wheel buttons** | RSB, LSB and the Xbox button can be assigned (look back/left/right, camera, handbrake, radio, shifting …). |
| **In-game "Wheel & Traffic" page** | Options › HUD › bottom. All values apply instantly and are saved. |
| **More traffic** | Traffic limits up to 100 cars, rush hour all day, presets Original/Calm/Busy/Rush Hour/Chaos. |
| **Fixed weather** | Sunny, Cloudy, Storm Clouds, Rain or Fog – through the game's own weather control, no game files changed. |
| **Tools** (`tools/`) | Python scripts for the cockpit wheel, More Traffic files and "traffic variety" (20 extra traffic car models). |

> 🚨 **Security:** See the original author's warning in [README_ORIGINAL.md](README_ORIGINAL.md): scammers spread
> keyloggers using this mod's name. **This fork never asks you to paste commands into PowerShell or to run an
> "All-in-One" installer.** The mod is only `winmm.dll` plus INI files. Only download from this repository's
> releases or build it yourself from source.

> ⚠️ **Unofficial.** Neither the Extra Options author nor the Azimuth developer supports this fork.
> Please do **not** report issues with this fork to them. Report Azimuth bugs only without mods.

## Compatibility
Tested only with this combination – other versions may not work:

| Part | Version |
|---|---|
| Azimuth | **0.9.10** |
| Extra Options (base) | **0.2.98** |
| Forza Horizon 2 | Xbox One version 1.0.0.64 (`forza_durango_release_final.exe`) |
| Wheel | Logitech G920 (other wheels untested) |

A new Azimuth release may break this mod. If Extra Options detects a mismatch it disables itself.
Updates will follow when possible.

## Credits
- **[RokkuDayo](https://github.com/RokkuDayo)** – [Extra Options](https://github.com/RokkuDayo/ForzaHorizon2_ExtraOptions), the base of this fork
- **[Almost There Games](https://almost-there-games.itch.io/azimuth)** – Azimuth wrapper (not included)
- **[Flenkii](https://github.com/Flenkii)** – idea, testing, maintainer of this fork
- **Claude (Anthropic)** – wrote most of the new code in this fork together with Flenkii

## Not included
- No Forza Horizon 2 game files (no EXE, no database, no graphics/XAML).
- No Azimuth – get it from the developer: <https://almost-there-games.itch.io/azimuth>
- The scripts in `tools/` create their files **on your PC from your own game files**.

## Installation (Azimuth)
1. Install Azimuth and start the game once normally.
2. From the [release](../../releases), copy `winmm.dll` and `FH2_ExtraOptions.ini` into the Azimuth folder (next to `azimuth.exe`).
   Back up your old `winmm.dll` first.
3. Wheel: keep 900° in G HUB. Settings are in `FH2_Lenkrad.ini` (created on first start)
   and in-game under Options › HUD › bottom.

New INI keys of this fork in `FH2_ExtraOptions.ini`, section `[Traffic]`:
`TrafficLevel` (0–5), `RushHourAllDay` (0/1), `Wetter` (weather: 0 original, 1 sunny, 2 cloudy, 3 storm clouds, 4 rain, 5 fog).
The wheel INI (`FH2_Lenkrad.ini`) uses German key names.

## Building
Same as the original (see [BUILD.md](BUILD.md)): `python build.py /path/to/zig --azimuth`.
Tests (emulator, need `unicorn` and `pefile` plus locally extracted game files in `FH2_GAME`):
```
python build.py /path/to/zig --azimuth --test --output tests/winmm_test.dll
cd tests && python test_menu.py winmm_test.dll && python test_buttons.py winmm_test.dll && python test_weather.py winmm_test.dll
```

## License
GPL-3.0 like the original (see [LICENSE](LICENSE)). Changes compared to the original are listed in
[CHANGES_FORK.md](CHANGES_FORK.md).

## AI disclosure
Like the original: the code of this fork was written with the help of an AI (Claude by Anthropic) and tested
in an emulator and in the game.
