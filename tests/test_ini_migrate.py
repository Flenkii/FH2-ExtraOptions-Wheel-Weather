"""Test of features/ini_migrate.c with the real compiled test DLL: the German settings files of
fork1-fork3 (FH2_Lenkrad.ini, FH2_Tastatur.ini, [Traffic] Wetter=) become the English ones of
fork4 with the user's values, and the old files end up unchanged in FH2_Settings_Backup."""
import os, shutil, sys, tempfile
from emu import Emu

DLL = sys.argv[1] if len(sys.argv) > 1 else 'winmm_test.dll'
HERE = os.path.dirname(os.path.abspath(__file__))
fails = []
checks = [0]


def check(cond, text):
    checks[0] += 1
    print(('  ok   ' if cond else '  FAIL ') + text)
    if not cond:
        fails.append(text)


GERMAN_KEYBOARD = (b'; FH2 Tastatur (inoffiziell) - Einstellungen\r\n[Tastatur]\r\nAktiv=1\r\nLenkzeit=200\r\n'
                   b'Rueckstellzeit=90\r\nPedalzeit=60\r\nGas=W,Hoch\r\nBremse=S\r\nHandbremse=Leertaste\r\n'
                   b'Zurueck=Rueck\r\nTabLinks=BildHoch\r\nBlickZurueck=C,Num2\r\nLicht=-\r\n')


def setup():
    root = tempfile.mkdtemp(prefix='eo-migrate-')
    for name in ('FH2_Lenkrad.ini', 'FH2_ExtraOptions.ini'):
        shutil.copy(os.path.join(HERE, 'fixture', name), os.path.join(root, name))
    open(os.path.join(root, 'FH2_Tastatur.ini'), 'wb').write(GERMAN_KEYBOARD)
    for name in ('FH2_Lenkrad.log', 'FH2_Lenkrad_vorher.log', 'FH2_Lenkrad_ffb.csv'):
        open(os.path.join(root, name), 'wb').write(b'old ' + name.encode())
    return root


def read(root, *name):
    return open(os.path.join(root, *name), 'rb').read()


print('Deutsche Dateien von fork1-fork3')
root = setup()
german_wheel, german_eo = read(root, 'FH2_Lenkrad.ini'), read(root, 'FH2_ExtraOptions.ini')
e = Emu(DLL, root)
e.call('Fh2TestIniMigrate', e.put_wstr('C:\\test'))
report = bytes(e.mu.mem_read(e.call('Fh2TestIniMigrateReport'), 600)).split(b'\0')[0].decode()
print('   ' + report.replace('\r\n', '\n   ').rstrip())

wheel = read(root, 'FH2_Wheel.ini').decode('ascii')
check(wheel.startswith('; FH2 wheel bridge (unofficial) - settings') and '[Wheel]' in wheel, 'FH2_Wheel.ini: englische Datei')
for line in ('Enabled=1', 'Rotation=180', 'FFBStrength=75', 'Rumble=50', 'BrakeAxis=Rz', 'ClutchAxis=Slider0',
             'Shifter=0', 'Gear6=17', 'Reverse=18', 'Lock=450', 'Centering=20', 'Damping=6', 'Curve=30',
             'MinimumForce=2', 'Log=1', 'ExtraButton1=8', 'ExtraFunction1=2'):
    check(('\r\n' + line + '\r\n') in wheel, f'Wert übernommen bzw. Standard: {line}')
check(not any(w in wheel for w in ('Aktiv', 'Drehwinkel', 'Lenkrad]', 'Staerke', 'Zusatz')), 'keine deutschen Schlüssel mehr')
check(wheel.count('Rotation=') == 1 and wheel.count('Curve=') == 1, 'jeder Schlüssel genau einmal')

kb = read(root, 'FH2_Keyboard.ini').decode('ascii')
for line in ('Enabled=1', 'SteerTime=200', 'ReturnTime=90', 'Throttle=W,Up', 'Brake=S', 'Handbrake=Space',
             'Back=Backspace', 'TabLeft=PageUp', 'LookBack=C,Num2', 'Lights=-', 'ShiftUp=E', 'ArrowUp=Up'):
    check(('\r\n' + line + '\r\n') in kb, f'Tastatur: {line}')
check('[Keyboard]' in kb and 'Tastatur]' not in kb and 'Gas=' not in kb, 'FH2_Keyboard.ini: englisch')

eo = read(root, 'FH2_ExtraOptions.ini')
check(eo == german_eo.replace(b'\nWetter=0', b'\nWeather=0'), 'FH2_ExtraOptions.ini: nur Wetter= -> Weather=, sonst Byte für Byte gleich')

backup = os.path.join(root, 'FH2_Settings_Backup')
check(read(backup, 'FH2_Lenkrad.ini') == german_wheel and read(backup, 'FH2_Tastatur.ini') == GERMAN_KEYBOARD and
      read(backup, 'FH2_ExtraOptions.ini') == german_eo, 'Originale unverändert in FH2_Settings_Backup')
check(not any(os.path.exists(os.path.join(root, n)) for n in
              ('FH2_Lenkrad.ini', 'FH2_Tastatur.ini', 'FH2_Lenkrad.log', 'FH2_Lenkrad_vorher.log', 'FH2_Lenkrad_ffb.csv')),
      'alte Dateien und alte Lenkrad-Logs nicht mehr im Azimuth-Ordner')
check(read(backup, 'FH2_Lenkrad.log') == b'old FH2_Lenkrad.log', 'alte Logs im Backup')
check('FH2_Lenkrad.ini' in report and 'FH2_Tastatur.ini' in report and 'Weather=' in report, 'FH2_ExtraOptions.log erklärt es')

print('Zweiter Start: nichts mehr zu tun')
before = {n: read(root, n) for n in os.listdir(root) if n.endswith('.ini')}
e.call('Fh2TestIniMigrate', e.put_wstr('C:\\test'))
check({n: read(root, n) for n in os.listdir(root) if n.endswith('.ini')} == before, 'keine Datei geändert')
check(bytes(e.mu.mem_read(e.call('Fh2TestIniMigrateReport'), 4)).split(b'\0')[0] == b'', 'kein Log-Eintrag')

print('Englische Datei gibt es schon (z. B. aus dem Release-ZIP kopiert)')
root = setup()
open(os.path.join(root, 'FH2_Wheel.ini'), 'wb').write(b'[Wheel]\r\nEnabled=0\r\n')
e = Emu(DLL, root)
e.call('Fh2TestIniMigrate', e.put_wstr('C:\\test'))
check(read(root, 'FH2_Wheel.ini') == b'[Wheel]\r\nEnabled=0\r\n', 'vorhandene FH2_Wheel.ini bleibt wie sie ist')
check(read(root, 'FH2_Lenkrad.ini') == german_wheel and os.path.exists(os.path.join(root, 'FH2_Lenkrad.log')),
      'alte FH2_Lenkrad.ini und Logs bleiben dann liegen')
check(os.path.exists(os.path.join(root, 'FH2_Keyboard.ini')), 'Tastatur wird trotzdem übernommen')

print('Neue Installation ohne alte Dateien')
root = tempfile.mkdtemp(prefix='eo-migrate-new-')
e = Emu(DLL, root)
e.call('Fh2TestIniMigrate', e.put_wstr('C:\\test'))
check(os.listdir(root) == [], 'nichts angelegt (die Module legen ihre englischen Dateien selbst an)')

print()
print('ALLE TESTS OK (%d Pruefungen)' % checks[0] if not fails else '%d FEHLER' % len(fails))
sys.exit(1 if fails else 0)
