"""Native test of the wheel force feedback programs (features/ffb_vm.c).

Builds ffb_vm.c as a Linux shared library and runs FH2's real wheel programs, taken from the
game image (exe.img) exactly as the game hands them to Microsoft.Xbox.Input.Wheel.dll:
slots 0..7, the two rumble programs filled in with swprintf like the game does.

Usage: python3 test_ffb_vm.py [path/to/exe.img]"""
import ctypes, math, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, '..', 'features', 'ffb_vm.c')
EXE_IMG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('FH2_GAME', 'game'), 'exe.img')
fails = []
checks = [0]


def check(cond, text):
    checks[0] += 1
    print(('  ok   ' if cond else '  FAIL ') + text)
    if not cond:
        fails.append(text)


lib_path = os.path.join(tempfile.mkdtemp(prefix='ffbvm-'), 'ffbvm.so')
subprocess.check_call(['clang', '-O2', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', '-o', lib_path, SOURCE])
lib = ctypes.CDLL(lib_path)
lib.ffb_vm_tick.restype = ctypes.c_float
lib.ffb_vm_tick.argtypes = [ctypes.c_void_p, ctypes.c_float]
lib.ffb_vm_param.restype = ctypes.c_int
lib.ffb_vm_param.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_size_t]
lib.ffb_vm_set_param.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float]
lib.ffb_vm_get_param.restype = ctypes.c_float
lib.ffb_vm_get_param.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.ffb_vm_set_scale.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_float]
lib.ffb_vm_load.restype = ctypes.c_int
lib.ffb_vm_load.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_size_t,
                            ctypes.POINTER(ctypes.c_size_t)]
lib.ffb_vm_loaded.restype = ctypes.c_uint

vm = ctypes.create_string_buffer(1 << 20)


def wstr(data, at):
    end = at
    while data[end:end + 2] != b'\0\0':
        end += 2
    return data[at:end].decode('utf-16le')


img = open(EXE_IMG, 'rb').read()
NAMES = {0x201cf68: 'PauseHeartbeat', 0x201cfe0: 'Torque', 0x201cf40: 'InMenuSpringScale',
         0x201cf88: 'InRaceSpringScale', 0x201cfb0: 'InRaceSpringMaxForce',
         0x201cff0: 'InRaceDampingMaxForce', 0x201d020: 'InRaceDampingScale',
         0x201d048: 'LeftAmplitude', 0x201d068: 'LeftWavelength', 0x201d088: 'RightAmplitude',
         0x201d0a8: 'RightWavelength'}
for rva, name in NAMES.items():
    check(wstr(img, rva) == name, 'game image: parameter name %s' % name)
# registration order at 0x10718ab ... (IWheel slot 36), as the game does it
ORDER = ['PauseHeartbeat', 'Torque', 'InMenuSpringScale', 'InRaceSpringScale', 'InRaceSpringMaxForce',
         'InRaceDampingMaxForce', 'InRaceDampingScale', 'LeftAmplitude', 'LeftWavelength',
         'RightAmplitude', 'RightWavelength']
rumble = wstr(img, 0x201d780)
PROGRAMS = [wstr(img, 0x201d0d0), wstr(img, 0x201d170), wstr(img, 0x201d1e0), wstr(img, 0x201d3a0),
            wstr(img, 0x201d460), wstr(img, 0x201d630),
            rumble.replace('%s', 'LeftWavelength', 2).replace('%s', 'LeftAmplitude', 2),
            rumble.replace('%s', 'RightWavelength', 2).replace('%s', 'RightAmplitude', 2)]
check(PROGRAMS[1] == 'TOFL Lt E0 GT E0 L0 E0 ENDN E0 MOV {Torque} Af+ ', 'game image: torque program')
check('{LeftWavelength} 2f' in PROGRAMS[6] and PROGRAMS[6].endswith('MOV {LeftAmplitude} Af+ '),
      'rumble program filled in like swprintf')


def fresh():
    ctypes.memset(vm, 0, len(vm))
    lib.ffb_vm_reset(vm)
    ids = {n: lib.ffb_vm_param(vm, n, len(n)) for n in ORDER}
    for slot, text in enumerate(PROGRAMS):
        err = ctypes.c_size_t(99999)
        ok = lib.ffb_vm_load(vm, slot, text, len(text), ctypes.byref(err))
        if not ok:
            print('    compile error in slot %d at %d: %r' % (slot, err.value, text[err.value:err.value + 20]))
        assert ok
    return ids


ids = fresh()
check([ids[n] for n in ORDER] == list(range(11)), 'parameter ids 0..10 in registration order (p0 heartbeat, p1 torque)')
check(lib.ffb_vm_loaded(vm) == 8, 'all 8 FH2 programs compile')


def setp(name, value):
    lib.ffb_vm_set_param(vm, ids[name], value)


def defaults(driving=True):
    """values as ControllerFFB.ini / the game send them"""
    setp('InMenuSpringScale', 0.5)
    setp('InRaceSpringMaxForce', 0.5)
    setp('InRaceDampingMaxForce', 0.31)
    setp('InRaceDampingScale', 0.33)
    setp('LeftWavelength', 38)
    setp('RightWavelength', 21)
    setp('LeftAmplitude', 0)
    setp('RightAmplitude', 0)
    setp('InRaceSpringScale', 0)
    setp('Torque', 0)
    if driving:
        setp('PauseHeartbeat', 1)


# --- menus / pause: no heartbeat -> menu spring -0.5 * Ad
ids = fresh()
defaults(driving=False)
f = [lib.ffb_vm_tick(vm, 0.2) for _ in range(5)]
check(abs(f[-1] - (-0.1)) < 1e-6, 'menu spring: Ad=0.2 -> Af=-0.1 (got %.4f)' % f[-1])
f = lib.ffb_vm_tick(vm, -0.4)
check(abs(f - 0.2) < 1e-6, 'menu spring pulls back from the left (Ad=-0.4 -> +0.2)')

# --- driving: heartbeat each frame, torque passes through, no menu spring
ids = fresh()
defaults()
setp('Torque', 0.18)
for _ in range(3):
    f = lib.ffb_vm_tick(vm, 0.0)
check(abs(f - 0.18) < 1e-6, 'driving: torque goes straight to the wheel (0.18 -> %.4f)' % f)
check(lib.ffb_vm_get_param(vm, ids['PauseHeartbeat']) == 0.0, 'heartbeat is consumed by program 0')

# heartbeat stops (pause menu) -> after 2.5 s the menu spring takes over, torque is ignored
ids = fresh()
defaults()
setp('Torque', 0.18)
lib.ffb_vm_tick(vm, 0.1)
forces = [lib.ffb_vm_tick(vm, 0.1) for _ in range(300)]
t_switch = next(i for i, v in enumerate(forces) if abs(v - (-0.05)) < 1e-6) + 2  # ticks after the last heartbeat
check(240 <= t_switch <= 260, 'heartbeat timeout after ~2.5 s (%d ms)' % (t_switch * 10))
check(abs(forces[10] - 0.18) < 1e-6, 'inside the 2.5 s the torque is still applied')

# --- in-race spring: -scale * Ad, clamped to +-InRaceSpringMaxForce
ids = fresh()
defaults()
setp('InRaceSpringScale', 0.25)
lib.ffb_vm_tick(vm, 0.4)
setp('PauseHeartbeat', 1)
lib.ffb_vm_tick(vm, 0.4)
setp('PauseHeartbeat', 1)
f = lib.ffb_vm_tick(vm, 0.4)
check(abs(f - (-0.1)) < 1e-5, 'in-race spring 0.25 * 0.4 -> -0.1 (got %.4f)' % f)
setp('InRaceSpringScale', 5.0)
setp('PauseHeartbeat', 1)
f = lib.ffb_vm_tick(vm, 0.4)
check(abs(f - (-0.5)) < 1e-5, 'in-race spring clamped to -InRaceSpringMaxForce (got %.4f)' % f)

# --- damping: velocity from the last positions * 100 (per second), against the motion
ids = fresh()
defaults()
pos = 0.0
for i in range(20):
    setp('PauseHeartbeat', 1)
    pos += 0.004  # 0.4 per second to the right
    f = lib.ffb_vm_tick(vm, pos)
check(abs(f - (-0.33 * 0.4)) < 2e-3, 'damping -0.33 * 0.4/s = -0.132 (got %.4f)' % f)
for i in range(5):
    setp('PauseHeartbeat', 1)
    pos += 0.05  # 5 per second: clamped
    f = lib.ffb_vm_tick(vm, pos)
check(abs(f - (-0.31)) < 1e-4, 'damping clamped to -InRaceDampingMaxForce (got %.4f)' % f)

# --- rumble: square wave, period = wavelength in ms, +-amplitude
ids = fresh()
defaults()
setp('LeftAmplitude', 0.18)
out = []
for i in range(200):
    setp('PauseHeartbeat', 1)
    out.append(round(lib.ffb_vm_tick(vm, 0.0), 4))
check(set(out) <= {0.18, -0.18}, 'left rumble is a square wave of +-0.18')
check(out.count(0.18) > 60 and out.count(-0.18) > 60, 'both halves of the wave appear')
ids = fresh()
defaults()
lib.ffb_vm_set_scale(vm, 'LeftAmplitude', 0.5)
setp('LeftAmplitude', 0.18)
setp('PauseHeartbeat', 1)
f = lib.ffb_vm_tick(vm, 0.0)
check(abs(abs(f) - 0.09) < 1e-6, 'rumble scale (menu Vibration) halves the amplitude')

# --- rumble stops when the heartbeat is gone
ids = fresh()
defaults()
setp('RightAmplitude', 0.4)
for i in range(300):
    f = lib.ffb_vm_tick(vm, 0.0)
check(abs(f) < 1e-6, 'no rumble in menus (Ad=0)')

# --- broken programs are refused, not run
err = ctypes.c_size_t(0)
ok = lib.ffb_vm_load(vm, 9, 'MOV {Torque} Af+ FOO E0', 23, ctypes.byref(err))
check(not ok and err.value == 17, 'unknown instruction is refused with its position')
ok = lib.ffb_vm_load(vm, 9, 'MOV E0 5', 8, ctypes.byref(err))
check(not ok, 'writing to a number is refused')
ok = lib.ffb_vm_load(vm, 9, 'ADD Af+ E0 E1', 13, ctypes.byref(err))
check(not ok, 'Af+ as a source is refused')

print()
print('ALLE TESTS OK (%d Pruefungen)' % checks[0] if not fails else '%d FEHLER' % len(fails))
sys.exit(1 if fails else 0)
