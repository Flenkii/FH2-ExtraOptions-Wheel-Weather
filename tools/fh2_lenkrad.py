# -*- coding: utf-8 -*-
"""
FH2 Lenkrad-Mod (Cockpit): Haende ausblenden + Lenkrad dreht sich realistisch weit

Schreibt NUR in  Mount\\mediaoverride\\  (wird von Extra Options geladen, [Files] EnableMediaOverrides=1).
Die Original-Spieldateien werden NICHT veraendert. Entfernen: --uninstall (loescht nur eigene Dateien).

Aufruf:
  python fh2_lenkrad.py --install [--grad 450] [--haende-zeigen]
  python fh2_lenkrad.py --uninstall
  python fh2_lenkrad.py --status
--grad = maximaler Lenkeinschlag des Lenkrads je Seite (Original FH2: 90). 450 = 900 Grad gesamt (wie G920).
"""
import os, sys, io, json, math, time, struct, zipfile, zlib
from bisect import bisect_right

VERSION = "0.1"
MANIFEST = ".fh2_lenkrad.json"
REPORT = "FH2_Lenkrad_Bericht.txt"
DRIVER_MODELS = ["default", "defaultRace", "suited", "unsuited", "stig"]

def say(m=""):
    print(m); sys.stdout.flush()

# ============================================================== Oodle1 (liboodle, Public Domain)
ONE = 0x4000
REPLEN = [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
          25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48,
          49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 128, 192, 256, 512]

class _BS:
    __slots__ = ('d', 'i', 'sr', 'm', 'lsb')
    def __init__(self, d, i):
        self.d = d; self.i = i + 1
        self.sr = d[i] >> 1; self.lsb = d[i] & 1; self.m = 0x80
    def ingest(self):
        d = self.d
        while self.m <= 0x800000:
            b = d[self.i] if self.i < len(d) else 0
            self.sr = (((self.sr << 1) | self.lsb) << 7 | (b >> 1)) & 0xFFFFFFFF
            self.lsb = b & 1
            self.m = (self.m << 8) & 0xFFFFFFFF
            self.i += 1
    def peek(self, one):
        self.ingest(); scale = self.m // one
        return min(self.sr // scale, one - 1)
    def consume(self, minz, span, one):
        scale = self.m // one; sz = minz * scale
        self.sr -= sz
        if minz < one - span: self.m = span * scale
        else: self.m -= sz
    def get(self, one):
        self.ingest(); scale = self.m // one
        z = min(self.sr // scale, one - 1); sz = z * scale
        self.sr -= sz
        if z < one - 1: self.m = scale
        else: self.m -= sz
        return z

class _Dec:
    __slots__ = ('used', 'sym', 'w', 'occ', 'tot', 'hls', 'hns', 'nrw', 'dt', 'rri', 'ri')
    def __init__(self, alpha, uniq):
        n = alpha + 2
        self.used = uniq; self.sym = [0] * n
        self.w = [ONE] * n; self.w[0] = 0
        self.occ = [0] * n; self.occ[0] = 4
        self.tot = 4; self.nrw = 8
        self.dt = max(256, min((alpha - 1) * 32, 15160))
        self.rri = 4; self.ri = max(128, min((alpha - 1) * 2, (self.dt // 2) - 32))
        self.hls = 0; self.hns = 0
    def decay(self):
        occ = self.occ; sym = self.sym
        occ[0] //= 2; self.tot = occ[0]
        hw = 0; hi = 0; idx = 1
        while idx <= self.hls:
            brk = False
            while occ[idx] <= 1:
                if idx >= self.hls:
                    occ[idx] = 0; self.hls -= 1; brk = True; break
                occ[idx] = occ[self.hls]; occ[self.hls] = 0
                sym[idx] = sym[self.hls]; self.hls -= 1
            if brk or not occ[idx]: break
            occ[idx] //= 2; self.tot += occ[idx]
            if occ[idx] > hw: hw = occ[idx]; hi = idx
            idx += 1
        if hw and hi != self.hls:
            occ[self.hls], occ[hi] = occ[hi], occ[self.hls]
            sym[self.hls], sym[hi] = sym[hi], sym[self.hls]
        if self.hls != self.used and not occ[0]:
            occ[0] = 1; self.tot += 1
        for k in range(self.hls + 1, len(self.w)): self.w[k] = ONE
    def renorm(self):
        q = 0x20000 // self.tot; w = self.w; occ = self.occ
        w[0] = 0; acc = (occ[0] * q) // 8
        for idx in range(1, self.hls + 1):
            w[idx] = acc; acc += (occ[idx] * q) // 8
        if self.rri * 2 < self.ri:
            self.rri *= 2; self.nrw = self.tot + self.rri
        else:
            self.nrw = self.tot + self.ri
        self.hns = self.hls
        for k in range(self.hls + 1, len(w)): w[k] = ONE
    def decode(self, bs, alpha):
        if self.tot >= self.nrw:
            if self.tot >= self.dt: self.decay()
            self.renorm()
        z = bs.peek(ONE); w = self.w
        idx = bisect_right(w, z, 1, self.hns + 2) - 1
        if idx > self.hns: idx = self.hns
        while idx > 0 and not (w[idx + 1] > z and w[idx] <= z): idx -= 1
        bs.consume(w[idx], w[idx + 1] - w[idx], ONE)
        self.occ[idx] += 1; self.tot += 1
        if idx: return self.sym[idx]
        if self.hls != self.hns and bs.get(2):
            idx = bs.get(self.hls - self.hns) + self.hns + 1
            self.occ[idx] += 2; self.tot += 2
            return self.sym[idx]
        self.hls += 1
        s = bs.get(alpha)
        self.sym[self.hls] = s; self.occ[self.hls] += 2; self.tot += 2
        if self.hls == self.used:
            self.tot -= self.occ[0]; self.occ[0] = 0
        return s

class _Decomp:
    def __init__(self, bs, h):
        self.bs = bs; self.win = h[0] >> 9; self.la = h[0] & 0x1FF
        ul = h[1] & 0x1FF
        self.lit = [_Dec(self.la, ul) for _ in range(4)]
        rl = h[2]; self.ln = []
        for g in range(4):
            for _ in range(16): self.ln.append(_Dec(65, (rl >> 24) & 0xFF))
            rl = (rl << 8) & 0xFFFFFFFF
        self.ln.append(_Dec(65, (rl >> 24) & 0xFF))
        self.o1a = min(4, self.win + 1)
        o4a = min(256, self.win // 4 + 1)
        self.o1 = _Dec(self.o1a, self.o1a)
        self.o4 = [_Dec(o4a, o4a) for _ in range(256)]
        self.o1k = _Dec(self.win // 1024 + 1, (h[1] >> 19) + 1)
        self.n = 0; self.last = 0
    def step(self, out):
        bs = self.bs
        lc = self.ln[self.last].decode(bs, 65); self.last = lc
        if not lc:
            out.append(self.lit[self.n & 3].decode(bs, self.la)); self.n += 1
            return
        ln = REPLEN[lc]; ew = min(self.win, self.n)
        o1 = self.o1.decode(bs, self.o1a) + 1
        o1k = self.o1k.decode(bs, ew // 1024 + 1)
        o4 = self.o4[o1k].decode(bs, min(256, ew // 4 + 1))
        off = o1k * 1024 + o4 * 4 + o1
        self.n += ln; start = len(out) - off
        for k in range(ln): out.append(out[start + k])

def oodle1(data, off, stops):
    h = struct.unpack_from('<9I', data, off)
    bs = _BS(data, off + 36); out = bytearray()
    for si in range(3):
        if len(out) >= stops[2]: break
        dc = _Decomp(bs, h[si * 3: si * 3 + 3])
        while len(out) < stops[si]: dc.step(out)
    return bytes(out[:stops[2]])

# ============================================================== Granny GR2
class GR2:
    def __init__(self, d):
        self.d = d
        self.P = 8 if d[:4] == bytes.fromhex('e59b495e') else 4
        self.MD = 44 if self.P == 8 else 32
        fi = 0x20
        ver, total, crc, so, sc = struct.unpack_from('<5I', d, fi)
        if ver != 7: raise ValueError('GR2-Version %d' % ver)
        self.shoff = fi + so
        self.hsize = struct.unpack_from('<I', d, 0x10)[0]
        self.secs = [list(struct.unpack_from('<11I', d, self.shoff + i * 44)) for i in range(sc)]
        self.root_type = struct.unpack_from('<2I', d, fi + 20)
        self.root_obj = struct.unpack_from('<2I', d, fi + 28)
        self.datas = []
        for s in self.secs:
            if s[3] == 0: self.datas.append(b'')
            elif s[0] == 0: self.datas.append(d[s[1]:s[1] + s[2]])
            elif s[0] == 2: self.datas.append(oodle1(d, s[1], (s[5], s[6], s[3])))
            else: raise ValueError('Kompression %d nicht unterstuetzt' % s[0])
        self.base = []; buf = bytearray()
        for x in self.datas:
            self.base.append(len(buf)); buf += x
        self.buf = buf
        self.relocs = []; self.ptr = {}
        for si, s in enumerate(self.secs):
            rl = []
            for r in range(s[8]):
                src, ts, to = struct.unpack_from('<3I', d, s[7] + r * 12)
                rl.append([src, ts, to])
                self.ptr[self.base[si] + src] = self.base[ts] + to
            self.relocs.append(rl)
    def p(self, at): return self.ptr.get(at)
    def cstr(self, at):
        if at is None: return None
        return self.buf[at:self.buf.index(b'\0', at)].decode('latin1')
    def typedef(self, at):
        res = []
        while True:
            t = struct.unpack_from('<I', self.buf, at)[0]
            if t == 0: break
            res.append((t, self.cstr(self.p(at + 4)), self.p(at + 4 + self.P), struct.unpack_from('<I', self.buf, at + 4 + 2 * self.P)[0]))
            at += self.MD
        return res
    def msize(self, t, sub):
        P = self.P
        if t == 1: return self.size_of(sub)
        if t in (2, 8, 22): return P
        if t in (3, 4): return 4 + P
        if t == 5: return 2 * P
        if t == 7: return 4 + 2 * P
        if t == 9: return 68
        return {10: 4, 11: 1, 12: 1, 13: 1, 14: 1, 15: 2, 16: 2, 17: 2, 18: 2, 19: 4, 20: 4, 21: 2}[t]
    def size_of(self, td):
        return sum(self.msize(t, s) * max(1, a) for t, n, s, a in self.typedef(td))
    def member(self, td, name):
        off = 0
        for t, n, s, a in self.typedef(td):
            if n == name: return off, t, s
            off += self.msize(t, s) * max(1, a)
        raise KeyError(name)
    def sec_of(self, absaddr):
        for i, b in enumerate(self.base):
            if len(self.datas[i]) and b <= absaddr < b + len(self.datas[i]):
                return i, absaddr - b
        raise ValueError(absaddr)
    def write(self, datas, relocs):
        d = self.d
        out = bytearray(d[:self.hsize])
        ss = [list(s) for s in self.secs]
        for i, s in enumerate(ss):
            while len(out) % 4: out.append(0)
            s[0] = 0; s[1] = len(out); s[2] = s[3] = len(datas[i])
            out += datas[i]
        for i, s in enumerate(ss):
            while len(out) % 4: out.append(0)
            mar = d[self.secs[i][9]:self.secs[i][9] + self.secs[i][10] * 12]
            s[7] = len(out); s[8] = len(relocs[i])
            for rr in relocs[i]: out += struct.pack('<3I', *rr)
            s[9] = len(out); out += mar
        for i, s in enumerate(ss):
            struct.pack_into('<11I', out, self.shoff + i * 44, *s)
        struct.pack_into('<I', out, 0x24, len(out))
        struct.pack_into('<I', out, 0x28, zlib.crc32(out[0x68:]) & 0xffffffff)
        return bytes(out)

# ---------------------------------------------- Quaternion-Kurven (Tabellen aus LSLib, MIT)
ST = [1.4142135, 0.70710677, 0.35355338, 0.35355338, 0.35355338, 0.17677669, 0.17677669, 0.17677669,
      -1.4142135, -0.70710677, -0.35355338, -0.35355338, -0.35355338, -0.17677669, -0.17677669, -0.17677669]
OT = [-0.70710677, -0.35355338, -0.53033006, -0.17677669, 0.17677669, -0.17677669, -0.088388346, 0.0,
      0.70710677, 0.35355338, 0.53033006, 0.17677669, -0.17677669, 0.17677669, 0.088388346, -0.0]

def _q(a, b, c, sc, of, bits):
    top = 1 << bits; mask = top - 1
    s1 = ((b & top) >> (bits - 1)) | (c >> bits)
    s2 = (s1 + 1) & 3; s3 = (s2 + 1) & 3; s4 = (s3 + 1) & 3
    A = (a & mask) * sc[s2] + of[s2]; B = (b & mask) * sc[s3] + of[s3]; C = (c & mask) * sc[s4] + of[s4]
    D = math.sqrt(max(0.0, 1 - (A * A + B * B + C * C)))
    if a & top: D = -D
    f = [0.0] * 4; f[s2] = A; f[s3] = B; f[s4] = C; f[s1] = D
    return tuple(f)

def curve_quats(g, td, obj):
    hdr = g.typedef(td)[0][1] or ''
    kind = hdr.replace('CurveDataHeader_', '')
    def arr16(name, fmt, size):
        o, t, s = g.member(td, name)
        cnt = struct.unpack_from('<I', g.buf, obj + o)[0]; q = g.p(obj + o + 4)
        return list(struct.unpack_from('<%d%s' % (cnt, fmt), g.buf, q)) if cnt else []
    if kind in ('D4nK16uC15u', 'D4nK8uC7u'):
        bits, fmt, mul = (15, 'H', 0.000030518509) if kind == 'D4nK16uC15u' else (7, 'B', 0.0078740157)
        so, _, _ = g.member(td, 'ScaleOffsetTableEntries')
        sel = struct.unpack_from('<H', g.buf, obj + so)[0]
        sc = [ST[(sel >> s) & 15] * mul for s in (0, 4, 8, 12)]
        of = [OT[(sel >> s) & 15] for s in (0, 4, 8, 12)]
        v = arr16('KnotsControls', fmt, 0)
        n = len(v) // 4
        return [_q(v[n + i * 3], v[n + i * 3 + 1], v[n + i * 3 + 2], sc, of, bits) for i in range(n)]
    if kind == 'DaK32fC32f':
        c = arr16('Controls', 'f', 4)
        return [tuple(c[i:i + 4]) for i in range(0, len(c) - 3, 4)]
    if kind == 'D4Constant32f':
        o, t, s = g.member(td, 'Controls')
        return [struct.unpack_from('<4f', g.buf, obj + o)]
    raise ValueError(kind)

def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)

def qinv(q): return (-q[0], -q[1], -q[2], q[3])

def axis_angle(q):
    x, y, z, w = q
    if w < 0: x, y, z, w = -x, -y, -z, -w
    w = max(-1.0, min(1.0, w)); ang = 2 * math.acos(w)
    s = math.sqrt(max(1e-12, 1 - w * w))
    return (x / s, y / s, z / s), ang

def steering_gr2(src, maxdeg, samples=241, bone='boneSteeringWheelSpindle', curve=1.0):
    g = GR2(src)
    P = g.P
    rtd = g.base[g.root_type[0]] + g.root_type[1]
    rob = g.base[g.root_obj[0]] + g.root_obj[1]
    o, t, tg_td = g.member(rtd, 'TrackGroups')
    tg_cnt = struct.unpack_from('<I', g.buf, rob + o)[0]; tg_arr = g.p(rob + o + 4)
    track = None; dak_td = None; hdr_td = None
    for i in range(tg_cnt):
        tg = g.p(tg_arr + i * P)
        o2, t2, tt_td = g.member(tg_td, 'TransformTracks')
        cnt = struct.unpack_from('<I', g.buf, tg + o2)[0]; arr = g.p(tg + o2 + 4)
        es = g.size_of(tt_td); oc, _, _ = g.member(tt_td, 'OrientationCurve')
        for k in range(cnt):
            e = arr + k * es
            vt = g.p(e + oc)
            if vt is not None:
                tdl = g.typedef(vt)
                if tdl:
                    hdr_td = hdr_td or tdl[0][2]
                    if tdl[0][1] == 'CurveDataHeader_DaK32fC32f': dak_td = vt
            if g.cstr(g.p(e)) == bone: track = (e, oc, vt)
    if track is None: return None, 'kein Lenkrad-Knochen'
    e, oc, vt = track
    qs = curve_quats(g, vt, g.p(e + oc + P))
    if len(qs) < 2: return None, 'Lenkrad dreht sich im Original nicht'
    mid = [(a + b) / 2 for a, b in zip(qs[0], qs[-1])]
    ln = math.sqrt(sum(c * c for c in mid))
    if ln < 1e-6: return None, 'unerwartete Kurve'
    qc = tuple(c / ln for c in mid)
    axis, ang0 = axis_angle(qmul(qs[0], qinv(qc)))
    if math.degrees(ang0) < 5: return None, 'Lenkrad dreht sich im Original kaum'
    ao, _, anim_td = g.member(rtd, 'Animations')
    anim = g.p(g.p(rob + ao + 4))
    do, _, _ = g.member(anim_td, 'Duration')
    dur = struct.unpack_from('<f', g.buf, anim + do)[0]
    sec0 = bytearray(g.datas[0])
    relocs = [[list(r) for r in rl] for rl in g.relocs]
    def align():
        while len(sec0) % 8: sec0.append(0)
    def addstr(s):
        align(); a = len(sec0); sec0.extend(s.encode() + b'\0'); return a
    if dak_td is None:
        # Typdefinition DaK32fC32f selbst anlegen
        if hdr_td is None: return None, 'kein Kurven-Typ gefunden'
        hs, ho = g.sec_of(hdr_td)
        n_real = addstr('Real32'); n_hdr = addstr('CurveDataHeader_DaK32fC32f')
        n_pad = addstr('Padding'); n_kn = addstr('Knots'); n_ct = addstr('Controls')
        align(); real_td = len(sec0)
        def mdef(tp, name_off, def_target):
            a = len(sec0)
            sec0.extend(struct.pack('<I', tp) + b'\0' * P + b'\0' * P + b'\0' * 16 + b'\0' * P)
            relocs[0].append([a + 4, 0, name_off])
            if def_target is not None: relocs[0].append([a + 4 + P, def_target[0], def_target[1]])
        mdef(10, n_real, None); sec0.extend(b'\0' * g.MD)
        align(); new_td = len(sec0)
        mdef(1, n_hdr, (hs, ho)); mdef(15, n_pad, None)
        mdef(3, n_kn, (0, real_td)); mdef(3, n_ct, (0, real_td)); sec0.extend(b'\0' * g.MD)
        dak = (0, new_td)
    else:
        dak = g.sec_of(dak_td)
    K = [dur * i / (samples - 1) for i in range(samples)]
    C = []
    for tk in K:
        u = 1 - 2 * tk / dur  # Lenkwert des Spiels -1..1
        if curve > 1.0:  # Bruecke lenkt progressiv: Spielwert -> echter Lenkradwinkel zurueckrechnen
            u = math.copysign(1 - (1 - min(abs(u), 1.0)) ** (1.0 / curve), u)
        th = math.radians(maxdeg) * u
        s = math.sin(th / 2)
        C.extend(qmul((axis[0] * s, axis[1] * s, axis[2] * s, math.cos(th / 2)), qc))
    align(); obj = len(sec0)
    sec0.extend(struct.pack('<BBH', 1, 1, 0))
    sec0.extend(struct.pack('<I', len(K)) + b'\0' * P)
    sec0.extend(struct.pack('<I', len(C)) + b'\0' * P)
    align(); kn = len(sec0); sec0.extend(struct.pack('<%df' % len(K), *K))
    align(); cn = len(sec0); sec0.extend(struct.pack('<%df' % len(C), *C))
    vs, vo = g.sec_of(e + oc)
    hit = 0
    for rr in relocs[vs]:
        if rr[0] == vo: rr[1], rr[2] = dak[0], dak[1]; hit += 1
        elif rr[0] == vo + P: rr[1], rr[2] = 0, obj; hit += 1
    if hit != 2: return None, 'Zeiger nicht gefunden'
    relocs[0].append([obj + 8, 0, kn])
    relocs[0].append([obj + 8 + P + 4, 0, cn])
    datas = [bytes(sec0)] + [bytes(x) for x in g.datas[1:]]
    return g.write(datas, relocs), 'Original +-%.0f Grad' % math.degrees(ang0)

# ============================================================== Fahrer-Modell (modelbin)
def _bundle(d):
    n = struct.unpack_from('<H', d, 6)[0]
    blobs = []
    for i in range(n):
        o = 16 + i * 24
        bt, bmj, bmn, mc, mo, do, ds, du = struct.unpack_from('<4sBBHIIII', d, o)
        metas = {}
        for j in range(mc):
            mt, vs, off = struct.unpack_from('<4sHH', d, mo + j * 8)
            metas[mt[::-1].decode('latin1')] = d[mo + j * 8 + off: mo + j * 8 + off + (vs >> 4)]
        blobs.append((bt[::-1].decode('latin1'), metas, do, ds))
    return blobs

def hide_hands(model, cut=0.22, ymin=1.10):
    d = bytearray(model)
    if d[:4] != b'burG': raise ValueError('kein modelbin')
    blobs = _bundle(bytes(d))
    ib = [b for b in blobs if b[0] == 'IndB'][0]
    pv = [b for b in blobs if b[0] == 'VerB' and b[1].get('Id  ') == b'\xff\xff\xff\xff'][0]
    if struct.unpack_from('<H', d, ib[2] + 8)[0] != 2 or struct.unpack_from('<H', d, pv[2] + 8)[0] != 12:
        raise ValueError('unerwartetes Format')
    ioff = ib[2] + 16; poff = pv[2] + 16; nv = struct.unpack_from('<I', d, pv[2])[0]
    meshes = []
    for b in blobs:
        if b[0] != 'Mesh': continue
        lod = struct.unpack_from('<H', d, b[2] + 4)[0]
        start, base, ic = struct.unpack_from('<IiI', d, b[2] + 25)
        meshes.append((lod, start, ic))
    other = [(s, s + c) for l, s, c in meshes if not (l & 1)]
    culled = 0; done = set()
    for lod, s, c in meshes:
        if not (lod & 1) or (s, c) in done: continue
        for a, e in other:
            if a < s + c and s < e: raise ValueError('geteilter Indexbereich')
        done.add((s, c))
        for tri in range(s, s + c, 3):
            idx = struct.unpack_from('<3H', d, ioff + tri * 2)
            if idx[0] == idx[1] == idx[2]: continue
            for i in idx:
                if i >= nv: break
                x, y = struct.unpack_from('<2f', d, poff + i * 12)
                if abs(x) > cut and y > ymin:
                    struct.pack_into('<3H', d, ioff + tri * 2, idx[0], idx[0], idx[0]); culled += 1
                    break
    return bytes(d), culled

# ============================================================== Ablauf
def script_dir(): return os.path.dirname(os.path.abspath(sys.argv[0]))

def find_mount():
    args = [a for a in sys.argv[1:] if not a.startswith('--') and not a.replace('.', '').isdigit()]
    cands = ([os.path.abspath(args[0].strip('"'))] if args else []) + [script_dir(), os.path.dirname(script_dir())]
    for c in cands:
        for m in (os.path.join(c, 'Mount'), c):
            if os.path.isfile(os.path.join(m, 'forza_durango_release_final.exe')) and os.path.isdir(os.path.join(m, 'media', 'cars')):
                return m
    raise SystemExit('FEHLER: Spielordner nicht gefunden (Ordner mit Mount\\media\\cars).')

def load_manifest(mo):
    p = os.path.join(mo, MANIFEST)
    if os.path.isfile(p):
        try: return json.load(open(p, encoding='utf-8'))
        except Exception: pass
    return {'files': []}

def uninstall(mount, quiet=False):
    mo = os.path.join(mount, 'mediaoverride')
    man = load_manifest(mo)
    n = 0
    for rel in man.get('files', []):
        p = os.path.join(mo, rel)
        if os.path.isfile(p):
            os.remove(p); n += 1
    # leere Ordner (nur die eigenen) aufraeumen
    dirs = sorted({os.path.dirname(os.path.join(mo, r)) for r in man.get('files', [])}, key=len, reverse=True)
    for dpath in dirs:
        while dpath.startswith(mo) and dpath != mo:
            try:
                if os.listdir(dpath): break
                os.rmdir(dpath)
            except OSError:
                break
            dpath = os.path.dirname(dpath)
    mp = os.path.join(mo, MANIFEST)
    if os.path.isfile(mp): os.remove(mp)
    try:
        if os.path.isdir(mo) and not os.listdir(mo): os.rmdir(mo)
    except OSError:
        pass
    if not quiet: say('Entfernt: %d Dateien. Das Spiel nutzt wieder Original-Haende und -Lenkrad.' % n)
    return n

def install(mount, maxdeg, hands, curve=1.0):
    media = os.path.join(mount, 'media'); mo = os.path.join(mount, 'mediaoverride')
    if os.path.isfile(os.path.join(mo, MANIFEST)): uninstall(mount, quiet=True)
    files = []; log = []
    def put(rel, data):
        p = os.path.join(mo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + '.tmp', 'wb') as f: f.write(data)
        os.replace(p + '.tmp', p)
        files.append(rel)
    t0 = time.time()
    if hands:
        say('Haende im Cockpit ausblenden ...')
        for dm in DRIVER_MODELS:
            z = os.path.join(media, 'drivers', dm + '.zip')
            if not os.path.isfile(z): continue
            try:
                with zipfile.ZipFile(z) as zf:
                    src = zf.read('driver.modelbin')
                out, n = hide_hands(src)
                put(os.path.join('drivers', dm, 'driver.modelbin'), out)
                log.append('  Fahrer %-12s %6d Dreiecke ausgeblendet' % (dm, n))
            except Exception as e:
                log.append('  Fahrer %-12s FEHLER %s' % (dm, e))
    ok = skip = err = 0
    if maxdeg and abs(maxdeg - 90) > 0.5:
        cars = sorted(f for f in os.listdir(os.path.join(media, 'cars')) if f.lower().endswith('.zip'))
        say('Lenkrad-Drehung +-%g Grad fuer %d Autos ...' % (maxdeg, len(cars)))
        for i, cz in enumerate(cars):
            stem = cz[:-4]
            if i % 25 == 0: say('  %3d / %d  %s' % (i, len(cars), stem))
            try:
                with zipfile.ZipFile(os.path.join(media, 'cars', cz)) as zf:
                    names = [n for n in zf.namelist() if n.replace('\\', '/').lower().endswith('/leftrightturn.gr2') and '/drivers/' in n.replace('\\', '/').lower()]
                    if not names: skip += 1; continue
                    for n in names:
                        out, info = steering_gr2(zf.read(n), maxdeg, curve=curve)
                        if out is None:
                            skip += 1; log.append('  %-30s uebersprungen: %s' % (stem, info)); continue
                        put(os.path.join('cars', stem, *n.replace('\\', '/').split('/')), out)
                        ok += 1
            except Exception as e:
                err += 1; log.append('  %-30s FEHLER %s' % (stem, e))
    json.dump({'version': VERSION, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'grad': maxdeg, 'kurve': curve, 'hands': hands, 'files': files},
              open(os.path.join(mo, MANIFEST), 'w', encoding='utf-8'), indent=1)
    say('')
    say('Fertig in %.0f s: %d Autos angepasst, %d uebersprungen, %d Fehler, %d Dateien.' % (time.time() - t0, ok, skip, err, len(files)))
    return files, log, ok, skip, err

def main():
    say('=' * 70)
    say(' FH2 Lenkrad-Mod v%s  (schreibt nur in Mount\\mediaoverride)' % VERSION)
    say('=' * 70)
    mount = find_mount()
    say('Spielordner: %s' % mount)
    a = [x.lower() for x in sys.argv[1:]]
    if '--uninstall' in a:
        uninstall(mount); return 0
    if '--status' in a:
        man = load_manifest(os.path.join(mount, 'mediaoverride'))
        say('Installiert: %s' % ('ja, +-%s Grad, Haende %s, %d Dateien' % (man.get('grad'), 'aus' if man.get('hands') else 'an', len(man['files'])) if man.get('files') else 'nein'))
        return 0
    grad = 450.0
    if '--grad' in a:
        try: grad = float(a[a.index('--grad') + 1])
        except Exception: raise SystemExit('FEHLER: --grad braucht eine Zahl (z. B. 450)')
    grad = max(30.0, min(grad, 1080.0))
    hands = '--haende-zeigen' not in a
    curve = 1.0
    if '--kurve' in a:
        try: curve = max(1.0, min(float(a[a.index('--kurve') + 1]), 6.0))
        except Exception: raise SystemExit('FEHLER: --kurve braucht eine Zahl (z. B. 3)')
    files, log, ok, skip, err = install(mount, grad, hands, curve)
    try:
        with open(os.path.join(script_dir(), REPORT), 'w', encoding='utf-8', newline='\r\n') as f:
            f.write('FH2 Lenkrad-Mod v%s  %s  %s\n' % (VERSION, time.strftime('%Y-%m-%d %H:%M:%S'), ' '.join(sys.argv[1:])))
            f.write('\n'.join(log) + '\n')
    except OSError:
        pass
    for l in log[:40]: say(l)
    say('')
    say('OK: %d Dateien in %s' % (len(files), os.path.join(mount, 'mediaoverride')))
    say('Spiel starten, Cockpit-Ansicht waehlen und lenken.')
    return 0 if err == 0 else 1

if __name__ == '__main__':
    rc = 1
    try:
        rc = main()
    except SystemExit as e:
        say(str(e))
    except Exception as e:
        import traceback; traceback.print_exc(); say('\nFEHLER: %s' % e)
    if '--no-pause' not in sys.argv:
        try: input('\nEnter zum Schliessen ...')
        except Exception: pass
    sys.exit(rc)
