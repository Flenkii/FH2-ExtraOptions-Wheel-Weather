GRIPLINE V4 – wheel, keyboard, traffic & weather for Forza Horizon 2 (Azimuth)
=============================================================================
Based on Extra Options 0.2.98 by RokkuDayo.

Source code: https://github.com/Flenkii/Gripline
Original:    https://github.com/RokkuDayo/ForzaHorizon2_ExtraOptions (GPL-3.0)

No game files and no Azimuth included. Never paste commands into PowerShell to install
this mod – anything like that is a scam.
Not supported by the Extra Options author or the Azimuth developer.


1. INSTALLATION
---------------
Copy the files from the "Azimuth" folder into your Azimuth folder (next to azimuth.exe).
Back up your old winmm.dll and FH2_ExtraOptions.ini first.

On the first start the mod creates FH2_Wheel.ini (wheel) and FH2_Keyboard.ini (keyboard).
Everything important can be set in the game: Options > HUD > bottom.
Updating from fork1-fork3: your old FH2_Lenkrad.ini / FH2_Tastatur.ini are taken over
automatically into the new English files; the old files go into the folder
FH2_Settings_Backup.

Without any further steps everything is automatic:
  - The controller works as always.
  - The keyboard works right away, bindings: see Keybindings.txt (change them in
    FH2_Keyboard.ini).
  - A Logitech G920 wheel is detected. Force feedback = the game's original force feedback,
    like on the Xbox.
    Works even if your game copy has no Microsoft.Xbox.Input.Wheel.dll (the mod then uses
    its own version of it).
  - While a wheel is plugged in, the game drives with the wheel only. To drive with keyboard
    or controller anyway: set "Wheel: Use Wheel In Game" to Off in the game and restart
    (or unplug the wheel).
  - G920 brake pedal too stiff? Use the clutch pedal as brake: in the game
    "Wheel: Clutch Pedal as Brake" = On (or ClutchAsBrake=1 in FH2_Wheel.ini).
    Idea: Lancaster.


1b. PLAYING ONLINE WITH FH2MP  (folder "With FH2MP (online)")
-------------------------------------------------------------
Same mod, other place. FH2MP (github.com/Charelene/FH2MP) puts its own winmm.dll next to
azimuth.exe and loads Extra Options from the folder fh2extra:
  - Install FH2MP with its launcher first.
  - In the FH2MP launcher settings turn OFF the automatic Extra Options install
    (otherwise it puts the original Extra Options back).
  - Copy the folder "fh2extra" from "With FH2MP (online)" into your Azimuth folder
    (replace the files). Your FH2_Wheel.ini / FH2_Keyboard.ini go into fh2extra too.
Online, traffic and weather come from the session (your settings only apply offline).
Wheel, keyboard and force feedback work online.


2. OPTIONAL: READY-MADE PROFILES  (folder Optional\Profiles)
-----------------------------------------------------------
Only needed if you don't want to use the in-game menu. Copy both INI files of a profile
into your Azimuth folder (replaces your FH2_Wheel.ini and FH2_Keyboard.ini):

  Controller   – controller only: wheel and keyboard off
  Keyboard     – keyboard (+ controller), wheel off
  Wheel        – wheel with the game's original force feedback, keyboard stays on (default)
  Wheel_ClutchAsBrake – like Wheel, but the clutch pedal brakes (stiff G920 brake pedal)


PROBLEMS? Please report them on GitHub Issues:
  https://github.com/Flenkii/Gripline/issues
Attach these files from your Azimuth folder (next to azimuth.exe):
  - FH2_ExtraOptions.log                    (always)
  - FH2_Wheel.log                           (wheel problems)
  - FH2_Wheel.ini and FH2_Keyboard.ini      (your settings)
Start the game, reproduce the problem, close the game, then attach the files.

Known issues:
  - Traffic settings only apply after restarting Azimuth.
  - Fog only exists on Storm Island, everywhere else it is sunny.
  - No H-pattern shifter: FH2 only knows shift up / shift down (paddles or E/Q).

----------------------------------------------------------------------------------------
DEUTSCH (kurz)
Die Dateien aus "Azimuth" neben azimuth.exe kopieren (vorher die alte winmm.dll sichern).
Mit FH2MP (online): Ordner "fh2extra" aus "With FH2MP (online)" in den Azimuth-Ordner kopieren
und im FH2MP-Launcher die automatische Extra-Options-Installation ausschalten.
Einstellungen: im Spiel unter Optionen > HUD > ganz unten, oder FH2_Wheel.ini /
FH2_Keyboard.ini. Alte FH2_Lenkrad.ini/FH2_Tastatur.ini werden automatisch übernommen
(Originale im Ordner FH2_Settings_Backup). Die Tastatur funktioniert sofort, Belegung siehe
Keybindings.txt. Kupplung als Bremse: im Spiel "Lenkrad: Kupplung als Bremse" auf An
(oder ClutchAsBrake=1 in FH2_Wheel.ini, oder Profil Wheel_ClutchAsBrake). Idee: Lancaster.
Das Lenkrad nutzt das originale Force Feedback des Spiels. Ist ein Lenkrad eingesteckt,
fährt das Spiel nur damit; zum Fahren mit Tastatur/Controller "Lenkrad: Lenkrad im Spiel"
auf Aus stellen und neu starten. Optional\Profiles: fertige INI-Paare (nur Controller /
Tastatur / Lenkrad). Keine H-Schaltung: FH2 kennt nur Hoch- und Runterschalten.
Probleme bitte auf GitHub unter "Issues" melden und FH2_ExtraOptions.log, FH2_Wheel.log
(bei Lenkrad-Problemen), FH2_Wheel.ini und FH2_Keyboard.ini anhängen (neben azimuth.exe).
