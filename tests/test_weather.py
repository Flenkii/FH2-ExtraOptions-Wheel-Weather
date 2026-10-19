"""Weather menu: the real compiled code against a fake WeatherManager laid out like the real one
(layout taken from the game's code and a crash dump of the running game)."""
import os, struct, sys, tempfile
from emu import Emu, GAME

DLL = sys.argv[1]
fails = []
def check(cond, text):
    print(('  ok   ' if cond else '  FAIL ') + text)
    if not cond:
        fails.append(text)

root = tempfile.mkdtemp(prefix='eo-weather-')
e = Emu(DLL, root)
VT, ROOT, SET, REL = 0x2f64920, 0x34aba60, 0x1981860, 0x1981c80
MAINLAND = ['Clear', 'CloudyA', 'CloudyB', 'ThreateningStormACloudyA', 'ThreateningStormACloudyB',
            'ThreateningStormCCloudyA', 'ThreateningStormCCloudyB', 'StormBCloudyA', 'StormBCloudyB']
ISLAND = ['Clear', 'CloudyA', 'CloudyB', 'CloudyFog', 'ThreateningStormACloudyA',
          'ThreateningStormACloudyB', 'ThreateningStormCCloudyA', 'ThreateningStormCCloudyB',
          'ThreateningFog', 'StormBCloudyA', 'StormBCloudyB', 'StormTropicalCloudyA',
          'StormTropicalCloudyB', 'StormTropicalFog']

def put_string(at, text):
    b = text.encode()
    if len(b) < 16:
        e.mu.mem_write(at, b + b'\0' * (16 - len(b)))
        e.wq(at + 0x10, len(b)); e.wq(at + 0x18, 15)
    else:
        p = e.put_bytes(b)
        e.wq(at, p); e.wq(at + 0x10, len(b)); e.wq(at + 0x18, len(b))

def presets(names):
    begin = e.alloc(0xc8 * len(names))
    for i, n in enumerate(names):
        put_string(begin + i * 0xc8, n)
        e.wd(begin + i * 0xc8 + 0x60, i)
    obj = e.alloc(0x40)
    e.wq(obj, begin); e.wq(obj + 8, begin + 0xc8 * len(names))
    return obj

mgr = e.alloc(0x400)
e.wq(mgr, GAME + VT)
e.wq(mgr + 0x158, presets(MAINLAND))
e.wd(mgr + 0x11c, 0)
def link(target):
    r, w, s = e.alloc(0x100), e.alloc(0x100), e.alloc(0x500)
    e.wq(GAME + ROOT, r); e.wq(r + 0x48, w); e.wq(w + 0x98, s); e.wq(s + 0x488, target)
link(mgr)

calls = []
def on_set():
    m, p = e.arg(0), e.arg(1)
    raw = bytes(e.mu.mem_read(p, 0x3c))
    calls.append(('set', m, raw))
    e.mu.mem_write(m + 0xe0, raw)
def on_release():
    m = e.arg(0)
    calls.append(('release', m, None))
    raw = bytearray(0x3c); raw[0x32] = 1; raw[0x34:0x38] = struct.pack('<f', 1.0); raw[0x38] = 1
    e.mu.mem_write(m + 0xe0, bytes(raw))
e.stub('SetControl', on_set, at=GAME + SET)
e.stub('ReleaseControl', on_release, at=GAME + REL)

def decode(raw):
    f = lambda o: struct.unpack_from('<f', raw, o)[0]
    return dict(has_preset=raw[0], preset=struct.unpack_from('<i', raw, 4)[0], has_env=raw[0x18],
                env=f(0x1c), has_rain=raw[0x20], rain=f(0x24), f32=raw[0x32], blend=round(f(0x34), 3),
                f38=raw[0x38], sev=raw[8], atm=raw[0x10])

def tick(ms=0):
    e.tick += ms
    n = len(calls)
    e.call('Fh2TestWeatherTick')
    return calls[n:]

print('Start')
e.call('Fh2TestWeatherStart', GAME, 0)
check(e.call('Fh2TestWeatherManager') == mgr, 'WeatherManager über die Kette gefunden (vtable geprüft)')
check(tick() == [], 'Original beim Start: nichts angefasst')

print('Sonnig')
e.call('Fh2TestWeatherSet', 1)
c = tick()
d = decode(c[0][2]) if c else {}
check(len(c) == 1 and c[0][0] == 'set' and c[0][1] == mgr, 'Wahl wird sofort angewendet (1 Aufruf)')
check(d.get('has_preset') == 1 and d.get('preset') == 0 and d.get('has_rain') == 1 and d.get('rain') == 0.0
      and d.get('has_env') == 1 and d.get('env') == 0.0, f'Sonnig = Preset Clear (#0), trocken: {d}')
check(d.get('f32') == 1 and d.get('blend') == 0.999 and d.get('f38') == 1 and d.get('sev') == 0 and d.get('atm') == 0,
      'übrige Felder wie beim Spiel-Befehl SetWeatherControl')
check(tick(100) == [] and tick(1100) == [], 'danach kein Dauerfeuer (bleibt gesetzt)')

print('Spiel übernimmt (Rennen/Treffen)')
raw = bytearray(e.mu.mem_read(mgr + 0xe0, 0x3c)); raw[0] = 1; raw[4:8] = struct.pack('<i', 2); raw[0x20] = 0
e.mu.mem_write(mgr + 0xe0, bytes(raw))
check(tick(1100) == [], 'Spiel-Wetter bleibt während des Events')
check(tick(1100) == [], 'auch später kein Eingriff')
on_release_raw = bytearray(0x3c); on_release_raw[0x32] = 1; on_release_raw[0x38] = 1
e.mu.mem_write(mgr + 0xe0, bytes(on_release_raw))
c = tick(1100)
check(len(c) == 1 and decode(c[0][2])['preset'] == 0, 'nach dem Event: deine Wahl kommt zurück')

print('Regen / Gewitterwolken / Nebel')
e.call('Fh2TestWeatherSet', 4); c = tick(); d = decode(c[0][2]) if c else {}
check(d.get('preset') == 7 and d.get('rain') == 1.0 and d.get('env') == 1.0, f'Regen = StormBCloudyA (#7), Regen 1, nass 1: {d}')
e.call('Fh2TestWeatherSet', 3); c = tick(); d = decode(c[0][2]) if c else {}
check(d.get('preset') == 3 and d.get('rain') == 0.0, f'Gewitterwolken = ThreateningStormACloudyA (#3, langer Name): {d}')
e.call('Fh2TestWeatherSet', 5); c = tick(); d = decode(c[0][2]) if c else {}
check(d.get('preset') == 1, f'Nebel auf dem Festland: CloudyA (#1) statt Nebel: {d}')

print('Sturm-Insel')
e.wq(mgr + 0x158, presets(ISLAND)); e.wd(mgr + 0x11c, 1)
c = tick(1100); d = decode(c[0][2]) if c else {}
check(len(c) == 1 and d.get('preset') == 3, f'Kartenwechsel: Nebel neu gesetzt = CloudyFog (#3): {d}')
e.call('Fh2TestWeatherSet', 4); c = tick(); d = decode(c[0][2]) if c else {}
check(d.get('preset') == 9, f'Regen auf der Insel = StormBCloudyA (#9): {d}')

print('Original')
e.call('Fh2TestWeatherSet', 0); c = tick()
check([x[0] for x in c] == ['release'], 'Original gibt das Wetter wieder frei (nur unser eigenes)')
check(tick(1100) == [], 'danach nichts mehr')
e.call('Fh2TestWeatherSet', 2); tick()
raw = bytearray(e.mu.mem_read(mgr + 0xe0, 0x3c)); raw[4:8] = struct.pack('<i', 5)
e.mu.mem_write(mgr + 0xe0, bytes(raw))
e.call('Fh2TestWeatherSet', 0); c = tick()
check(c == [], 'Original während eines Spiel-Events: Spiel-Wetter wird nicht freigegeben')

print('Sicherheit')
e.call('Fh2TestWeatherSet', 6)
check(e.call('Fh2TestWeatherManager') == mgr and tick(1100) == [], 'Wert 6 (gibt es nicht) ignoriert')
e.wq(mgr, GAME + VT + 8)
e.call('Fh2TestWeatherSet', 1)
check(e.call('Fh2TestWeatherManager') == 0 and tick(1100) == [], 'falsche vtable: kein Aufruf')
e.wq(mgr, GAME + VT)
e.wq(mgr + 0x158, presets(['Foo']))
c = tick(1100)
check(c == [], 'unbekannte Presets: kein Aufruf (nur Log)')
e.wq(GAME + ROOT, 0)
check(e.call('Fh2TestWeatherManager') == 0 and tick(1100) == [], 'keine Spielwelt (Ladebildschirm): nichts')
print()
print('FEHLER:' if fails else 'ALLE TESTS OK', len(fails) or '')
sys.exit(1 if fails else 0)
