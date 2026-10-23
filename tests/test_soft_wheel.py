"""Test of the mod's own wheel object (features/wheel_soft.c), used when a game copy has no
Microsoft.Xbox.Input.Wheel.dll, with the real compiled test DLL.

The game's view is replayed: QueryInterface on the controller, the IWheel calls the game makes
(found with the diagnostic build: slots 10, 12, 13, 26, 30, 33, 36, 38, 41, 42) and the
IWheelReading / IWheelStaticConfiguration getters, with reports built by the bridge itself."""
import os, shutil, struct, sys, tempfile, uuid
from unicorn.x86_const import UC_X86_REG_XMM2
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


class SEmu(Emu):
    def k_VirtualProtect(self):
        if self.arg(3):
            self.wd(self.arg(3), 0x04)
        return 1

    def k_GetSystemTimeAsFileTime(self):
        self.wq(self.arg(0), 133_000_000_000_000_000)

    def k_FileTimeToLocalFileTime(self):
        self.wq(self.arg(1), self.rq(self.arg(0)) + 2 * 36_000_000_000)  # UTC+2
        return 1


root = tempfile.mkdtemp(prefix='eo-soft-')
for name in ('FH2_Lenkrad.ini', 'FH2_ExtraOptions.ini'):
    shutil.copy(os.path.join(HERE, 'fixture', name), os.path.join(root, name))
e = SEmu(DLL, root)
e.call('Fh2TestRigStart', 0x140000000, e.put_wstr('C:\\test\\game\\forza_durango_release_final.exe'),
       e.put_wstr('C:\\test'))

strings = {}
def raw_buffer():
    s = e.wstr(e.arg(0))
    if e.arg(1):
        e.wd(e.arg(1), len(s))
    return e.arg(0)
def create_string():
    p = e.put_wstr(e.mu.mem_read(e.arg(0), 2 * e.arg(1)).decode('utf-16le'))
    e.wq(e.arg(2), p)
    return 0
outer = e.call('Fh2TestSoftWheelCreate', e.stub('raw', raw_buffer), e.stub('create', create_string))
check(outer != 0, 'eigenes Wheel-Objekt erstellt, Spiel-FFB eingehängt')

def guid(text):
    return e.put_bytes(uuid.UUID(text).bytes_le)
IID_WHEEL = guid('646979cf-6b71-4e96-8df9-59e398d7420c')
IID_GAMEPAD = guid('1a2b3c4d-0000-0000-0000-000000000000')
IID_NAV = guid('b8f31fe7-7386-40e9-a9f8-2f21263acfb7')
IID_READING = guid('15198dca-a85c-455d-a2ab-d1cb907fc6d0')
IID_CONFIG = guid('d45f6e0b-ffb6-425f-b1d9-336dd5f8aebb')
out = e.alloc(32)
U32 = lambda v: v & 0xffffffff
vt = lambda obj, i: e.rq(e.rq(obj) + 8 * i)
def method(obj, i, *args):
    return U32(e.call(vt(obj, i), obj, *args))

def qi(obj, iid):
    e.wq(out, 0)
    hr = method(obj, 0, iid, out)
    return hr, e.rq(out)

hr, wheel = qi(outer, IID_WHEEL)
check(hr == 0 and wheel, 'Spiel bekommt IWheel vom Controller')
hr, _ = qi(outer, IID_GAMEPAD)
check(hr == 0x80004002, 'andere Schnittstellen (z.B. IGamepad) gibt es nicht, wie bei Microsoft')
hr, back = qi(wheel, guid('9776ff56-9bfd-4581-ad45-b645bba526d6'))
check(hr == 0 and back == outer, 'IWheel liefert über QueryInterface wieder den Controller (COM-Identität)')

# slot 10: VID/PID from the controller's device info
check(method(wheel, 10, out) == 0 and e.rd(out) == 0x046dc261, f'Slot 10: Geräte-ID 046D:C261 ({e.rd(out):#x})')

# ---- force feedback: the game's calls reach the FFB of the mod
img = open(EXE_IMG, 'rb').read()
def wstr(at):
    end = at
    while img[end:end + 2] != b'\0\0':
        end += 2
    return img[at:end].decode('utf-16le')
for n in ('PauseHeartbeat', 'Torque', 'InRaceSpringScale'):
    check(method(wheel, 36, e.put_wstr(n)) == 0, f'Slot 36 AddParameter {n}')
size = e.alloc(8)
check(method(wheel, 26, 1, e.put_wstr(wstr(0x201d0d0)), 0, size) == 0, 'Slot 26 SetProgram angenommen')
check(e.call('Fh2TestGameFfbLoaded') == 1, 'Programm des Spiels läuft im FFB der Mod')
check(method(wheel, 30, 1) == 0 and method(wheel, 33) == 0 and method(wheel, 42) == 0, 'Slots 30/33/42 ok')
e.mu.reg_write(UC_X86_REG_XMM2, struct.unpack('<I', struct.pack('<f', 0.25))[0])
check(method(wheel, 38, e.put_wstr('Torque')) == 0, 'Slot 38 SetParameter ok')
e.wd(out, 0xff)
check(method(wheel, 41, 4, out) == 0 and e.rd(out) & 0xff == 0, 'Slot 41: nichts in der Warteschlange')
check(method(wheel, 26, 16, e.put_wstr('END'), 0, size) == 0x80070057, 'Slot 26: Programmplatz 16 ungültig')

# ---- static configuration + reading
check(method(wheel, 13, out) == 0x8007139f, 'Slot 13 vor der ersten Konfiguration: noch nicht da (wie Microsoft)')
e.call('Fh2TestSoftWheelInput', 1 | 1 << 4, 65535, 32768)  # A + right paddle, full right, half throttle
check(method(wheel, 13, out) == 0, 'Slot 13: statische Konfiguration')
config = e.rq(out)
def get(obj, slot, kind):
    e.wq(out, 0)
    hr = method(obj, slot, out)
    v = {'b': e.mu.mem_read(out, 1)[0], 'u': e.rd(out), 'f': round(e.rf(out), 3), 'q': e.rq(out)}[kind]
    return hr, v
check(get(config, 6, 'b') == (0, 16), 'Lenkung 16 Bit')
check(get(config, 12, 'u') == (0, 180), 'max. Drehwinkel = Drehwinkel aus der INI (180)')
check(get(config, 20, 'b') == (0, 1), 'Force Feedback vorhanden')
check(qi(config, IID_CONFIG)[0] == 0, 'Konfiguration: IWheelStaticConfiguration')
method(config, 2)

check(method(wheel, 12, out) == 0, 'Slot 12: aktueller Zustand (IWheelReading)')
reading = e.rq(out)
check(qi(reading, IID_READING)[0] == 0, 'Zustand: IWheelReading')
check(get(reading, 6, 'b') == (0, 1), 'A gedrückt')
check(get(reading, 7, 'b') == (0, 0), 'B nicht gedrückt')
check(get(reading, 29, 'b') == (0, 1), 'rechte Wippe gedrückt')
check(get(reading, 16, 'f') == (0, 1.0), f'Lenkung ganz rechts = 1,0 ({get(reading, 16, "f")})')
hr, throttle = get(reading, 18, 'f')
check(hr == 0 and 0.49 < throttle < 0.51, f'Gas halb ({throttle})')
check(get(reading, 19, 'f') == (0, 0.0), 'Bremse 0')
check(get(reading, 17, 'u') == (0, 180), 'Drehwinkel 180')
check(get(reading, 32, 'b') == (0, 0), 'Gang 0 (kein Schaltknauf)')
check(get(reading, 33, 'q') == (0, 133_000_000_000_000_000 + 72_000_000_000), 'Zeitstempel in Ortszeit')
e.wq(out, 0)
method(wheel, 12, out)
check(e.rq(out) == reading, 'gleicher Zustand bis zum nächsten Bericht')
method(reading, 2)
method(reading, 2)
e.call('Fh2TestSoftWheelInput', 0, 0, 0)
method(wheel, 12, out)
reading = e.rq(out)
check(get(reading, 6, 'b') == (0, 0) and get(reading, 16, 'f') == (0, -1.0), 'neuer Bericht: A los, ganz links')
method(reading, 2)

hr, nav = qi(outer, IID_NAV)
check(hr == 0 and nav, 'INavigationController vorhanden')
e.call('Fh2TestSoftWheelInput', 1 << 1, 32768, 0)  # B
check(method(nav, 7, out) == 0 and e.rd(out + 8) == 0x20, f'Navigation: B ({e.rd(out + 8):#x})')

print()
print('ALLE TESTS OK (%d Pruefungen)' % checks[0] if not fails else '%d FEHLER' % len(fails))
sys.exit(1 if fails else 0)
