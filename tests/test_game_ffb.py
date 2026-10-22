"""Test of the real game force feedback path in the wheel bridge (features/wheel_bridge.c +
features/ffb_vm.c) with the real compiled test DLL.

A fake Microsoft.Xbox.Input.Wheel.dll image provides the IWheel method table; the bridge patches
slots 26 (SetProgram), 36 (AddParameter) and 38 (SetParameter). The game's calls are replayed with
FH2's real program texts from exe.img and must reach both the original methods and the PC copy of
the programs."""
import os, shutil, struct, sys, tempfile
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_XMM0, UC_X86_REG_XMM2
from emu import Emu

DLL = sys.argv[1] if len(sys.argv) > 1 else 'winmm_test.dll'
EXE_IMG = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get('FH2_GAME', 'game'), 'exe.img')
HERE = os.path.dirname(os.path.abspath(__file__))
fails = []
checks = [0]


def check(cond, text):
    checks[0] += 1
    print(('  ok   ' if cond else '  FAIL ') + text)
    if not cond:
        fails.append(text)


class FEmu(Emu):
    def k_VirtualProtect(self):
        if self.arg(3):
            self.wd(self.arg(3), 0x02)
        return 1


root = tempfile.mkdtemp(prefix='eo-ffb-')
for name in ('FH2_Lenkrad.ini', 'FH2_ExtraOptions.ini'):
    shutil.copy(os.path.join(HERE, 'fixture', name), os.path.join(root, name))
e = FEmu(DLL, root)
log_path = e.put_wstr('C:\\test')
e.call('Fh2TestRigStart', 0x140000000, e.put_wstr('C:\\test\\game\\forza_durango_release_final.exe'), log_path)

img = open(EXE_IMG, 'rb').read()
def wstr(at):
    end = at
    while img[end:end + 2] != b'\0\0':
        end += 2
    return img[at:end].decode('utf-16le')

# ---- fake Wheel DLL image (own region, with the stub hook like the other stubs)
image = 0x50000000
e.mu.mem_map(image, 0x20000)
e.mu.hook_add(UC_HOOK_CODE, e.on_code, begin=image, end=image + 0x20000)
originals = []
def original(name):
    def f():
        originals.append((name, e.arg(1), e.arg(2)))
        return 0
    return f
table = image + 0x15760
for i in range(50):
    e.wq(table + 8 * i, e.stub('slot%d' % i, lambda: 0))
for slot, rva, name in ((26, 0x8540, 'SetProgram'), (36, 0x8ab0, 'AddParameter'), (38, 0x8c10, 'SetParameter')):
    e.stub(name, original(name), image + rva)
    e.wq(table + 8 * slot, image + rva)
def raw_buffer():
    s = e.wstr(e.arg(0))
    if e.arg(1):
        e.wd(e.arg(1), len(s))
    return e.arg(0)
e.wq(image + 0x14198, e.stub('WindowsGetStringRawBuffer', raw_buffer))
wheel = e.alloc(16)
e.wq(wheel, table)
def inner_qi():
    e.wq(e.arg(2), wheel)
    return 0
inner_vt = e.alloc(16 * 8)
e.wq(inner_vt, e.stub('inner_qi', inner_qi))
inner = e.alloc(16)
e.wq(inner, inner_vt)

check(e.call('Fh2TestGameFfbHook', image, inner) == 1, 'IWheel-Methoden 26/36/38 in der Wheel-DLL eingehängt')
slot = lambda i: e.rq(table + 8 * i)
check(all(slot(i) != image + r for i, r in ((26, 0x8540), (36, 0x8ab0), (38, 0x8c10))), 'Tabelle zeigt auf die Bridge')
check(slot(25) == e.rq(table + 8 * 25) and slot(37) != image + 0x8540, 'andere Methoden unverändert')

def game_call(i, *args):
    return e.call(slot(i), wheel, *args) & 0xffffffff

def set_param(name, value):
    e.mu.reg_write(UC_X86_REG_XMM2, struct.unpack('<I', struct.pack('<f', value))[0])
    return game_call(38, e.put_wstr(name))

ORDER = ['PauseHeartbeat', 'Torque', 'InMenuSpringScale', 'InRaceSpringScale', 'InRaceSpringMaxForce',
         'InRaceDampingMaxForce', 'InRaceDampingScale', 'LeftAmplitude', 'LeftWavelength', 'RightAmplitude',
         'RightWavelength']
for n in ORDER:
    game_call(36, e.put_wstr(n))
check([o[0] for o in originals] == ['AddParameter'] * 11, 'AddParameter geht weiter an Microsofts Wheel-DLL')
rumble = wstr(0x201d780)
programs = [wstr(0x201d0d0), wstr(0x201d170), wstr(0x201d1e0), wstr(0x201d3a0), wstr(0x201d460), wstr(0x201d630),
            rumble.replace('%s', 'LeftWavelength', 2).replace('%s', 'LeftAmplitude', 2),
            rumble.replace('%s', 'RightWavelength', 2).replace('%s', 'RightAmplitude', 2)]
out = e.alloc(8)
for i, text in enumerate(programs):
    rsp_args = (e.put_wstr(text), 0, out)
    game_call(26, i, *rsp_args)
check(e.call('Fh2TestGameFfbLoaded') == 8, 'alle 8 Programme des Spiels laufen auf dem PC')
check(sum(1 for o in originals if o[0] == 'SetProgram') == 8, 'SetProgram geht weiter an die Wheel-DLL (wie vorher)')
log = open(os.path.join(root, 'FH2_Lenkrad.log'), 'rb').read().decode('latin1')
check('Spiel-FFB: Programm 1 geladen: TOFL Lt E0 GT E0 L0 E0 ENDN E0 MOV {Torque} Af+' in log, 'Log zeigt die Programme')
check('Spiel-FFB: Parameter 1 = Torque' in log, 'Log zeigt die Parameter')

def fbits(f):
    return struct.unpack('<I', struct.pack('<f', f))[0]

def af(position):
    e.mu.reg_write(UC_X86_REG_XMM0, fbits(position))
    v = e.call('Fh2TestGameFfbTick')
    return round(struct.unpack('<f', struct.pack('<I', v & 0xffffffff))[0], 4)

for n, v in (('InMenuSpringScale', 0.5), ('InRaceSpringMaxForce', 0.5), ('InRaceDampingMaxForce', 0.31),
             ('InRaceDampingScale', 0.33), ('LeftWavelength', 38), ('RightWavelength', 21)):
    set_param(n, v)
check(af(0.2) == -0.1, 'Menü (kein Herzschlag): Zentrierfeder des Spiels -0,5 x Position')
for _ in range(3):  # wheel stays at 0.2: no damping
    set_param('PauseHeartbeat', 1.0)
    set_param('Torque', 0.21)
    v = af(0.2)
check(v == 0.21, f'Fahren: Rückstellmoment des Spiels kommt direkt an (0,21 -> {v})')
set_param('PauseHeartbeat', 1.0)
set_param('InRaceSpringScale', 0.25)
set_param('Torque', 0.0)
v = af(0.2)
check(v == -0.05, f'Lenkgewicht des Spiels: Feder 0,25 x 0,2 = -0,05 ({v})')
check(sum(1 for o in originals if o[0] == 'SetParameter') >= 10, 'SetParameter geht weiter an die Wheel-DLL')

print('Kraft am Lenkrad (G920, DirectInput)')
# fixture: FFBStaerke=75, Mindestkraft=2, Anschlag=450
def force(a, x=0):
    e.mu.reg_write(UC_X86_REG_XMM0, fbits(a))
    return e.call('Fh2TestGameForce', 0, x) & 0xffffffff
signed = lambda v: v - (1 << 32) if v >= 1 << 31 else v
e.call('Fh2TestWheelSet', 2, 100)   # strength 100 %
e.call('Fh2TestWheelSet', 7, 0)     # no minimum force
check(signed(force(0.21)) == 2100, f'Stärke 100 %: Af 0,21 -> 21 % Kraft ({signed(force(0.21))})')
e.call('Fh2TestWheelSet', 2, 50)
check(signed(force(-0.4)) == -2000, 'Stärke 50 % halbiert')
e.call('Fh2TestWheelSet', 2, 200)
check(signed(force(0.8)) == 10000, 'begrenzt auf volle Kraft')
e.call('Fh2TestWheelSet', 2, 100)
check(signed(force(0.3, 980)) == 0, 'drückt nie weiter in den Endanschlag')
check(signed(force(-0.3, 980)) == -3000, 'zurück aus dem Anschlag geht')
e.call('Fh2TestWheelSet', 7, 3)
check(signed(force(0.1)) == 1000, f'nur die Spielkraft: Mindestkraft der Mod wirkt nicht ({signed(force(0.1))})')
e.call('Fh2TestWheelSet', 10, 90)   # old soft lock at 90 degrees
check(signed(force(0.0, 500)) == 0, 'kein eigener Anschlag: bei 225 Grad keine Zusatzkraft')
e.call('Fh2TestWheelSet', 1, 0)
check(signed(force(0.5)) == 0, 'Force Feedback aus: gar keine Kraft')

print()
print('ALLE TESTS OK (%d Pruefungen)' % checks[0] if not fails else '%d FEHLER' % len(fails))
sys.exit(1 if fails else 0)
