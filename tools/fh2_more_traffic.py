# -*- coding: utf-8 -*-
"""
FH2 More Traffic Mod

Sichert media\\EntityModel.zip (EntityModel.zip.moretraffic-original), erhoeht die
Traffic-Werte in
    AI/CarLoadingSettings.xml   (MaxActiveTraffic, InitialNumTraffic, MaxActiveTypes)
    AI/Densities*.xml           (Dichte min/max, spawnIn/OutDistance)
und ersetzt damit das Archiv direkt. Unabhaengig von Extra Options und der
Azimuth-Version. Entfernen stellt das Original byte-genau wieder her.
(Alternative mit --mediapc: Kopie nach Mount\\mediapc, braucht Extra Options.)

Start:   python fh2_more_traffic.py              -> installieren / aktualisieren
         python fh2_more_traffic.py --uninstall  -> alles entfernen
         python fh2_more_traffic.py --test-empty -> Diagnose: KEIN Verkehr
         python fh2_more_traffic.py --test-repack -> Test: nur neu schreiben, Werte = Original
         python fh2_more_traffic.py --preset leicht -> vorsichtige Werte (1.5x, max 24 Autos)
Einstellungen: FH2_MoreTraffic.ini (wird beim ersten Start angelegt)
"""
import os
import re
import sys
import time
import shutil
import zipfile
import hashlib
import xml.etree.ElementTree as ET

VERSION = "1.9"
MARKER = "FH2 More Traffic Mod v%s" % VERSION
ZIP_NAME = "EntityModel.zip"
STATE_NAME = "fh2_more_traffic_installed.txt"
INI_NAME = "FH2_MoreTraffic.ini"

# Originalwerte (aus deinem Scan) - nur zur Anzeige/Plausibilitaet
ORIG_MAX_ACTIVE = 18
ORIG_INITIAL = 6

DEFAULT_INI = """; =====================================================================
;  FH2 More Traffic Mod v{v} - Einstellungen
;  Nach dem Aendern einfach "More-Traffic installieren.bat" erneut starten.
; =====================================================================
[MoreTraffic]
; Verkehrsdichte in der Open World (1.0 = Original). Empfohlen: 1.5 - 2.5
TrafficMultiplier=2.0

; Max. gleichzeitig aktive Verkehrsautos. Original: 18
; 0 = automatisch (18 x TrafficMultiplier, max. 64)
MaxActiveTraffic=0

; Verkehrsautos direkt beim Laden. Original: 6.
; 0 = automatisch (= Original 6). Hoehere Werte koennen den Ladebildschirm haengen lassen!
InitialNumTraffic=0

; Wie viele Autos PRO MODELL gleichzeitig fahren duerfen (Bus/LKW im Original: 1). 1 = Original
CarTypeMaxActiveMultiplier=1

; Verschiedene Automodelle gleichzeitig im Speicher. Original: 8
; Mehr = mehr Abwechslung, aber mehr RAM/Ladezeit. Max. 16
MaxActiveTypes=8

; Spawn-/Despawn-Radius in Staedten (dort, wo das Spiel ihn festlegt). 1.0 = Original
SpawnDistanceMultiplier=1.25

; Verkehr in Strassenrennen mit Traffic (1.0 = Original)
RaceTrafficMultiplier=1.0

; Festival-/Drivatar-Autos, die frei herumfahren (1.0 = Original).
; WICHTIG: Das sind die meisten Autos, die man in der offenen Welt sieht!
FestivalMultiplier=2.0

; Strassen mit Typ "open_world" haben im Original GAR KEINEN Zivilverkehr.
; 1 = dort Verkehr wie auf normalen Landstrassen ("b") einschalten, 0 = Original
FillOpenWorldTraffic=1

; Hoechste erlaubte Dichte pro Strassentyp (1.0 = sicher, 1.5 = wie Original-Autobahn, max. 3.0)
MaxDensity=1.0
""".format(v=VERSION)

DENSITY_FILES = {
    "AI/Densities.xml": "open_world",
    "AI/DensitiesRoadTrip.xml": "open_world",
    "AI/DensitiesIEDriveToFestival.xml": "open_world",
    "AI/DensitiesRace.xml": "race",
}
CAR_LOADING = "AI/CarLoadingSettings.xml"


# ---------------------------------------------------------------- Hilfen
def say(msg=""):
    print(msg)
    sys.stdout.flush()


def fmt(v):
    """0.7000 -> '0.7', 3.0 -> '3' (wie im Original-XML)"""
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s else "0"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def script_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def find_mount():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cands = []
    if args:
        cands.append(os.path.abspath(args[0].strip('"')))
    here = script_dir()
    cands += [here, os.path.dirname(here)]
    for c in cands:
        for m in (os.path.join(c, "Mount"), c):
            if os.path.isfile(os.path.join(m, "forza_durango_release_final.exe")) and \
               os.path.isfile(os.path.join(m, "media", ZIP_NAME)):
                return m
    say("Spielordner nicht automatisch gefunden.")
    p = input("Pfad zum Spielordner (der Ordner mit 'Mount' drin) einfuegen + Enter: ").strip().strip('"')
    for m in (os.path.join(p, "Mount"), p):
        if os.path.isfile(os.path.join(m, "media", ZIP_NAME)):
            return os.path.abspath(m)
    raise SystemExit("FEHLER: %s nicht gefunden unter %s" % (ZIP_NAME, p))


def read_ini():
    path = os.path.join(script_dir(), INI_NAME)
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(DEFAULT_INI)
        say("Einstellungsdatei angelegt: %s" % path)
    cfg = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.split(";", 1)[0].strip()
            if not line or line.startswith("[") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip().lower()] = v.strip()

    def num(key, default, lo, hi, cast=float):
        try:
            return clamp(cast(cfg.get(key.lower(), default)), lo, hi)
        except ValueError:
            say("WARNUNG: %s=%r ungueltig, nehme %s" % (key, cfg.get(key.lower()), default))
            return default

    c = {
        "mult": num("TrafficMultiplier", 2.0, 0.0, 10.0),
        "max_active": num("MaxActiveTraffic", 0, 0, 80, int),
        "type_mult": num("CarTypeMaxActiveMultiplier", 1, 1, 8, int),
        "initial": num("InitialNumTraffic", 0, 0, 40, int),
        "types": num("MaxActiveTypes", 8, 1, 16, int),
        "dist": num("SpawnDistanceMultiplier", 1.25, 0.5, 3.0),
        "race": num("RaceTrafficMultiplier", 1.0, 0.0, 5.0),
        "festival": num("FestivalMultiplier", 2.0, 0.0, 10.0),
        "fill": num("FillOpenWorldTraffic", 1, 0, 1, int),
        "cap": num("MaxDensity", 1.0, 0.1, 3.0),
    }
    if c["max_active"] == 0:
        c["max_active"] = int(clamp(round(ORIG_MAX_ACTIVE * max(c["mult"], 1.0)), ORIG_MAX_ACTIVE, 64))
    if c["initial"] == 0:
        # v1.2: beim Laden wartet das Spiel auf diese Anzahl -> Original lassen
        c["initial"] = ORIG_INITIAL
    low = [a.lower() for a in sys.argv]
    if "--preset" in low and "leicht" in low:
        c.update(mult=1.5, max_active=24, initial=ORIG_INITIAL, types=8, dist=1.0, race=1.0,
                 festival=1.5, fill=0)
        path = path + "  (ueberschrieben durch Preset LEICHT)"
    elif "--preset" in low and "stark" in low:
        c.update(mult=2.0, max_active=36, initial=ORIG_INITIAL, types=8, dist=1.25, race=1.0,
                 festival=2.0, fill=1)
        path = path + "  (ueberschrieben durch Preset STARK)"
    elif "--preset" in low and "heftig" in low:
        # "realistisch": volle Strassen, Stadt dicht, Autobahn voll. Grenzen wie im Original (1.5).
        c.update(mult=4.0, max_active=48, initial=ORIG_INITIAL, types=10, dist=1.5, race=1.0,
                 festival=3.0, fill=1, cap=1.5)
        path = path + "  (ueberschrieben durch Preset HEFTIG)"
    elif "--preset" in low and "maximum" in low:
        # EXPERIMENTELL: alles am Anschlag. Dichte bis 3.0 (doppelt so viel wie das Original je nutzt).
        c.update(mult=8.0, max_active=80, initial=ORIG_INITIAL, types=16, dist=2.0, race=2.0,
                 festival=5.0, fill=1, cap=3.0, type_mult=4)
        path = path + "  (ueberschrieben durch Preset MAXIMUM)"
    c["initial"] = min(c["initial"], c["max_active"])
    return c, path


# ---------------------------------------------------------------- XML-Bearbeitung (Text bleibt sonst unveraendert)
def set_attr(tag_text, name, func, log, where):
    rx = re.compile(r'(\s%s\s*=\s*")([^"]*)(")' % re.escape(name))
    m = rx.search(tag_text)
    if not m:
        return tag_text
    old = m.group(2)
    try:
        new = func(float(old))
    except ValueError:
        return tag_text
    if new == old:
        return tag_text
    try:
        if float(new) == float(old):     # nur Schreibweise anders ("1.0" -> "1") -> Original lassen
            return tag_text
    except ValueError:
        pass
    log.append("    %-44s %-18s %8s -> %s" % (where, name, old, new))
    return tag_text[:m.start(2)] + new + tag_text[m.end(2):]


def patch_densities(text, mult_traffic, mult_festival, dist_mult, log, fname, fill=False, cap=1.0):
    def patch_list(m):
        block = m.group(0)
        cartype = m.group(1).lower()
        mult = mult_traffic if cartype == "traffic" else mult_festival if cartype == "festival" else 1.0
        # Vorlage fuer "open_world" (dort ist Verkehr im Original komplett aus): Werte von "b"
        ref = None
        if fill and cartype == "traffic":
            rb = re.search(r'<Density\b[^>]*densityNameTagValue\s*=\s*"b"[^>]*/>', block)
            if rb:
                ref = rb.group(0)

        def patch_density(dm):
            tag = dm.group(0)
            name_m = re.search(r'densityNameTagValue\s*=\s*"([^"]*)"', tag)
            where = "%s [%s] %s" % (fname.split("/")[-1], cartype, name_m.group(1) if name_m else "?")
            if ref and name_m and name_m.group(1) == "open_world" and \
                    re.search(r'\smax\s*=\s*"0(\.0*)?"', tag):
                # Kopie des "b"-Eintrags (mit speed usw.), aber id/Name von open_world behalten
                idm = re.search(r'\sid\s*=\s*"([^"]*)"', tag)
                new = ref
                new = re.sub(r'(\sid\s*=\s*")[^"]*(")', lambda q: q.group(1) + (idm.group(1) if idm else "12") + q.group(2), new, count=1)
                new = re.sub(r'(densityNameTagValue\s*=\s*")[^"]*(")', lambda q: q.group(1) + "open_world" + q.group(2), new, count=1)
                m2 = max(mult, 1.0)
                new = set_attr(new, "min", lambda v: fmt(min(v * m2, cap)), [], where)
                new = set_attr(new, "max", lambda v: fmt(min(v * m2, cap)), [], where)
                log.append("    %-44s %s" % (where, "Zivilverkehr eingeschaltet (wie 'b')"))
                return new
            if mult != 1.0:
                # Dichte ist ein Anteil (0..1) -> nie ueber 1.0
                # Obergrenze "cap" (Standard 1.0; das Original nutzt selbst bis 1.5)
                tag = set_attr(tag, "min", lambda v: fmt(min(v * mult, cap) if v <= cap else v), log, where)
                tag = set_attr(tag, "max", lambda v: fmt(min(v * mult, cap) if v <= cap else v), log, where)
            if dist_mult != 1.0 and cartype == "traffic":
                tag = set_attr(tag, "spawnInDistance", lambda v: fmt(round(v * dist_mult)), log, where)
                tag = set_attr(tag, "spawnOutDistance", lambda v: fmt(round(v * dist_mult)), log, where)
            return tag

        return re.sub(r"<Density\b[^>]*?/>", patch_density, block)

    return re.sub(r'<DensityList\b[^>]*\bcartype\s*=\s*"([^"]*)"[^>]*>.*?</DensityList>',
                  patch_list, text, flags=re.S | re.I)


def patch_car_loading(text, c, log):
    def patch_ts(m):
        tag = m.group(0)
        tag = set_attr(tag, "MaxActiveTraffic", lambda v: str(c["max_active"]), log, "CarLoadingSettings")
        tag = set_attr(tag, "InitialNumTraffic", lambda v: str(c["initial"]), log, "CarLoadingSettings")
        tag = set_attr(tag, "MaxActiveTypes", lambda v: str(c["types"]), log, "CarLoadingSettings")
        return tag
    new, n = re.subn(r"<TrafficSettings\b[^>]*>", patch_ts, text, count=1)
    tm = c.get("type_mult", 1)
    if tm and tm != 1:
        # Pro Automodell: wie viele davon gleichzeitig fahren duerfen (z.B. Bus/LKW = 1)
        def patch_ct(m):
            tag = m.group(0)
            mid = re.search(r'ModelID\s*=\s*"([^"]*)"', tag)
            return set_attr(tag, "MaxActive", lambda v: str(int(max(1, round(v * tm)))), log,
                            "CarType %s" % (mid.group(1) if mid else "?"))
        new = re.sub(r"<CarType\b[^>]*>", patch_ct, new)
    if n != 1:
        raise RuntimeError("TrafficSettings-Element nicht gefunden - unbekannte Spielversion?")
    return new


def decode(data):
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), b"\xef\xbb\xbf", "utf-8"
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16"), b"", "utf-16"
    try:
        return data.decode("utf-8"), b"", "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252"), b"", "cp1252"


def encode(text, bom, enc):
    return bom + text.encode(enc)


# ---------------------------------------------------------------- ZIP "chirurgisch" aendern
# v1.3: Das Archiv wird NICHT neu gepackt. Die Datei bleibt byte-genau gleich gross,
# alle Eintraege bleiben an ihrer Original-Position. Nur die Daten der geaenderten
# XML-Dateien (+ CRC/Groesse im Header) werden an Ort und Stelle ersetzt.
import struct
import zlib

SIG_LOCAL, SIG_CEN, SIG_EOCD, SIG_DD = 0x04034b50, 0x02014b50, 0x06054b50, 0x08074b50


class ZipLayout:
    def __init__(self, blob):
        self.blob = blob
        pos = blob.rfind(struct.pack("<I", SIG_EOCD), max(0, len(blob) - 65557))
        if pos < 0:
            raise RuntimeError("ZIP-Ende nicht gefunden")
        (_, disk, cd_disk, n_disk, n, cd_size, cd_off, clen) = struct.unpack_from("<IHHHHIIH", blob, pos)
        if n == 0xFFFF or cd_off == 0xFFFFFFFF:
            raise RuntimeError("ZIP64-Archive werden nicht unterstuetzt")
        self.eocd, self.cd_off, self.cd_size = pos, cd_off, cd_size
        self.entries = []
        p = cd_off
        for _ in range(n):
            f = struct.unpack_from("<IHHHHHHIIIHHHHHII", blob, p)
            if f[0] != SIG_CEN:
                raise RuntimeError("Zentralverzeichnis beschaedigt")
            nl, xl, cl = f[10], f[11], f[12]
            e = dict(cen=p, flags=f[3], method=f[4], crc=f[7], csize=f[8], usize=f[9],
                     local=f[16], name=blob[p + 46:p + 46 + nl].decode("utf-8" if f[3] & 0x800 else "cp437"))
            lf = struct.unpack_from("<IHHHHHIIIHH", blob, e["local"])
            if lf[0] != SIG_LOCAL:
                raise RuntimeError("Lokaler Header beschaedigt: %s" % e["name"])
            e["data"] = e["local"] + 30 + lf[9] + lf[10]
            self.entries.append(e)
            p += 46 + nl + xl + cl
        # Platz jedes Eintrags = bis zum naechsten lokalen Header bzw. Zentralverzeichnis
        starts = sorted(x["local"] for x in self.entries) + [cd_off]
        for e in self.entries:
            nxt = min(s for s in starts if s > e["local"])
            dd = 0
            if e["flags"] & 8:
                q = e["data"] + e["csize"]
                dd = 16 if struct.unpack_from("<I", blob, q)[0] == SIG_DD else 12
            e["dd"] = dd
            e["slot"] = nxt - e["data"] - dd
            e["gap"] = e["slot"] - e["csize"]

    def describe(self):
        gaps = sum(1 for e in self.entries if e["gap"] != 0)
        methods = sorted({e["method"] for e in self.entries})
        flags = sorted({e["flags"] for e in self.entries})
        al = 0
        for k in range(16, 0, -1):
            if all(e["data"] % (1 << k) == 0 for e in self.entries):
                al = 1 << k
                break
        return ("%d Eintraege, Methode %s, Flags %s, Luecken %d, Daten-Ausrichtung %s" %
                (len(self.entries), methods, ["0x%x" % f for f in flags], gaps, al or "keine"))


def _deflate_candidates(data):
    """Viele gueltige Deflate-Varianten (Level/Fenster/Speicher/Strategie) -
    die kleinste passt am ehesten in den Original-Platz."""
    seen = set()
    for wbits in (15, 14, 13, 12, 11, 10, 9):
        for level in (9, 8, 7, 6, 5, 4, 3, 2, 1):
            for mem in (9, 8, 7, 6, 5, 4, 3, 2, 1):
                for strat in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_RLE,
                              zlib.Z_FIXED, zlib.Z_HUFFMAN_ONLY):
                    co = zlib.compressobj(level, zlib.DEFLATED, -wbits, mem, strat)
                    out = co.compress(data) + co.flush()
                    if out not in seen:
                        seen.add(out)
                        yield out


def surgical_replace(src_blob, changed):
    """changed: {name: [Variante1, Variante2, ...]} (unkomprimierte Bytes, bevorzugte zuerst).
    Jede Datei wird NUR an ihrer Original-Stelle ersetzt - es wird nichts verschoben.
    Liefert (neue_bytes, info_zeilen, {name: gewaehlte_variante})."""
    lay = ZipLayout(src_blob)
    out = bytearray(src_blob)
    info = ["ZIP: " + lay.describe()]
    by_name = {e["name"]: e for e in lay.entries}
    chosen = {}
    for name, variants in changed.items():
        if isinstance(variants, bytes):
            variants = [variants]
        e = by_name.get(name)
        if e is None:
            raise RuntimeError("Eintrag fehlt: %s" % name)
        if e["method"] != 8:
            raise RuntimeError("%s: Kompressionsmethode %d nicht unterstuetzt" % (name, e["method"]))
        pick = None
        tried = []
        for vi, data in enumerate(variants):
            best = min(_deflate_candidates(data), key=len)
            tried.append(len(best))
            if len(best) <= e["csize"]:
                pick = (vi, data, best)
                break
        if pick is None:
            raise RuntimeError("%s passt nicht an seine Original-Stelle (%s > %d Bytes). "
                               "Bitte etwas kleinere Werte in der INI waehlen." %
                               (name, "/".join(map(str, tried)), e["csize"]))
        vi, data, best = pick
        if zlib.decompressobj(-15).decompress(best) != data:
            raise RuntimeError("Selbsttest Deflate fehlgeschlagen: %s" % name)
        crc = zlib.crc32(data) & 0xFFFFFFFF
        # Rest mit Nullen fuellen: Inflate endet am letzten Block, Groesse bleibt gleich
        comp = best + b"\0" * (e["csize"] - len(best))
        out[e["data"]:e["data"] + e["csize"]] = comp
        if not e["flags"] & 8:
            struct.pack_into("<III", out, e["local"] + 14, crc, e["csize"], len(data))
        else:
            q = e["data"] + e["csize"] + (4 if e["dd"] == 16 else 0)
            struct.pack_into("<III", out, q, crc, e["csize"], len(data))
        struct.pack_into("<III", out, e["cen"] + 16, crc, e["csize"], len(data))
        chosen[name] = data
        info.append("  %-40s an Ort und Stelle (%d von %d Bytes%s)" %
                    (name, len(best), e["csize"], ", kompakt %d" % vi if vi else ""))
    return bytes(out), info, chosen


# ---------------------------------------------------------------- Extra Options INI
def ensure_media_overrides(mount):
    say("")
    say("Extra Options muss den mediapc-Ordner laden ([Files] EnableMediaOverrides=1).")
    guess = []
    for base in (script_dir(), os.path.dirname(script_dir()), os.path.expanduser("~")):
        for name in ("Azimuth", "azimuth"):
            guess.append(os.path.join(base, name))
    found = None
    for g in guess:
        p = os.path.join(g, "data", "bin", "FH2_ExtraOptions.ini")
        if os.path.isfile(p):
            found = p
            break
    if not found:
        p = input("Pfad zu deinem Azimuth-Ordner (Enter = ueberspringen, dann bitte manuell setzen): ").strip().strip('"')
        if not p:
            say("  -> uebersprungen. Trage in Azimuth\\data\\bin\\FH2_ExtraOptions.ini unter [Files] EnableMediaOverrides=1 ein.")
            return
        for cand in (os.path.join(p, "data", "bin", "FH2_ExtraOptions.ini"), os.path.join(p, "FH2_ExtraOptions.ini"), p):
            if os.path.isfile(cand) and cand.lower().endswith(".ini"):
                found = cand
                break
        if not found:
            say("  -> FH2_ExtraOptions.ini nicht gefunden. Bitte manuell setzen.")
            return

    raw = open(found, "rb").read()
    text = raw.decode("utf-8", "replace")
    nl = "\r\n" if "\r\n" in text else "\n"
    # Pruefen, ob schon aktiv
    section = None
    for line in text.splitlines():
        s = line.split(";", 1)[0].split("#", 1)[0].strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
        elif section == "files" and re.match(r"(?i)enablemediaoverrides\s*=\s*1$", s):
            say("  OK: EnableMediaOverrides ist bereits aktiv (%s)" % found)
            return
    backup = found + ".bak_moretraffic"
    if not os.path.exists(backup):
        shutil.copy2(found, backup)
    lines = text.splitlines()
    out, section, done = [], None, False
    for line in lines:
        s = line.split(";", 1)[0].split("#", 1)[0].strip()
        if s.startswith("[") and s.endswith("]"):
            if section == "files" and not done:
                out.append("EnableMediaOverrides=1")
                done = True
            section = s[1:-1].strip().lower()
        elif section == "files" and re.match(r"(?i)enablemediaoverrides\s*=", s):
            line = "EnableMediaOverrides=1"
            done = True
        out.append(line)
    if section == "files" and not done:
        out.append("EnableMediaOverrides=1")
        done = True
    if not done:
        out += ["", "[Files]", "EnableMediaOverrides=1"]
    new = nl.join(out) + nl
    if len(new.encode("utf-8")) > 8192:
        say("  -> INI waere groesser als 8192 Bytes (Extra-Options-Limit). Bitte manuell setzen.")
        return
    with open(found, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    say("  OK: EnableMediaOverrides=1 gesetzt in %s (Backup: %s)" % (found, os.path.basename(backup)))


# ---------------------------------------------------------------- Installation
BACKUP_SUFFIX = ".moretraffic-original"


STATE_SUFFIX = ".moretraffic-state"


def is_ours(path):
    """v1.0-1.2 erkennt man am ZIP-Kommentar, ab v1.3 an der Status-Datei (SHA-256)."""
    try:
        with zipfile.ZipFile(path) as z:
            if z.comment.decode("utf-8", "ignore").startswith("FH2 More Traffic Mod"):
                return True
    except Exception:
        return False
    st = path + STATE_SUFFIX
    if os.path.isfile(st):
        try:
            return open(st, encoding="utf-8").read().split()[0] == sha256(path)
        except Exception:
            return False
    return False


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _xml_shape(text):
    def walk(el):
        return (el.tag, sorted(el.attrib.items()), (el.text or "").strip(),
                [walk(ch) for ch in el], (el.tail or "").strip())
    return walk(ET.fromstring(text.encode("utf-8")))


def compact_variants(text, bom, enc):
    """Gleicher XML-Inhalt, schrittweise kompakter (nur Kommentare/Leerraum entfernt),
    damit die Datei komprimiert in ihren Original-Platz passt."""
    shape = _xml_shape(text)
    steps = [text]
    t = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    steps.append(t)
    t = re.sub(r">\s+<", "><", t).strip()
    steps.append(t)
    t = re.sub(r"\s+/>", "/>", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    steps.append(t)
    out = []
    for v in steps:
        if _xml_shape(v) == shape:      # Inhalt muss identisch bleiben
            b = encode(v, bom, enc)
            if b not in out:
                out.append(b)
    return out


def make_zip(src, dst, c, empty):
    """Aendert die XML-Dateien in einer Kopie von src (chirurgisch) und ersetzt dst atomar.
    Liefert (log, changed)."""
    log = []
    changed = {}
    repack = "--test-repack" in sys.argv
    tmp = dst + ".tmp"
    with zipfile.ZipFile(src) as zin:
        names = {i.filename for i in zin.infolist()}
        need = [CAR_LOADING] + list(DENSITY_FILES)
        missing = [n for n in need if n not in names]
        if missing:
            raise RuntimeError("Im Original-ZIP fehlen: %s" % ", ".join(missing))
        for name in need:
            data = zin.read(name)
            if repack:
                changed[name] = data      # Test: gleicher Inhalt, nur neu geschrieben
                continue
            text, bom, enc = decode(data)
            if name == CAR_LOADING:
                # Diagnose: Dichte 0 -> InitialNumTraffic muss auch 0 sein,
                # sonst wartet der Ladebildschirm endlos auf Autos.
                new = patch_car_loading(text, dict(c, initial=0, max_active=ORIG_MAX_ACTIVE, types=8), log) if empty else patch_car_loading(text, c, log)
            else:
                kind = DENSITY_FILES[name]
                mt = 0.0 if empty else (c["mult"] if kind == "open_world" else c["race"])
                if empty:
                    mf = 0.0          # Test LEER: auch Drivatare/Festival-Autos aus
                else:
                    mf = c["festival"] if kind == "open_world" else 1.0
                new = patch_densities(text, mt, mf, 1.0 if empty else c["dist"], log, name,
                                      fill=bool(c["fill"]) and not empty and kind == "open_world",
                                      cap=c["cap"])
            ET.fromstring(new.encode("utf-8"))  # wohlgeformt?
            enc_new = encode(new, bom, enc)
            if enc_new != data:
                changed[name] = compact_variants(new, bom, enc)

    with open(src, "rb") as f:
        blob = f.read()
    new_blob, info, changed = surgical_replace(blob, changed)
    log += [""] + info
    with open(tmp, "wb") as f:
        f.write(new_blob)

    # Pruefen: alle Eintraege vorhanden, CRC ok, nur die gewollten Dateien geaendert
    try:
        with zipfile.ZipFile(tmp) as zt, zipfile.ZipFile(src) as zo:
            if zt.testzip() is not None:
                raise RuntimeError("Neues ZIP fehlerhaft")
            a = [i.filename for i in zo.infolist()]
            b = [i.filename for i in zt.infolist()]
            if a != b:
                raise RuntimeError("Eintragsliste weicht ab")
            for n in a:
                want = changed.get(n)
                got = zt.read(n)
                if (want if want is not None else zo.read(n)) != got:
                    raise RuntimeError("Unerwarteter Inhalt in %s" % n)
                if want is None:
                    io, it = zo.getinfo(n), zt.getinfo(n)
                    if (io.header_offset, io.compress_size, io.CRC) != (it.header_offset, it.compress_size, it.CRC):
                        raise RuntimeError("Unerwartete Verschiebung in %s" % n)
        os.replace(tmp, dst)
    except PermissionError:
        os.remove(tmp)
        raise RuntimeError("Datei ist gesperrt - bitte Spiel/Azimuth komplett schliessen und erneut starten.")
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    with open(dst + STATE_SUFFIX, "w", encoding="utf-8") as f:
        f.write("%s\n%s\n%s\n" % (sha256(dst), MARKER, time.strftime("%Y-%m-%d %H:%M:%S")))
    return log, changed


def install_direct(mount, c, empty):
    """Standard: Original-Archiv media\\EntityModel.zip direkt ersetzen (mit Backup)."""
    media_zip = os.path.join(mount, "media", ZIP_NAME)
    backup = media_zip + BACKUP_SUFFIX
    if not os.path.isfile(backup):
        if is_ours(media_zip):
            raise RuntimeError("%s ist bereits veraendert, aber das Backup fehlt. "
                               "Bitte Original-Datei wiederherstellen." % ZIP_NAME)
        shutil.copy2(media_zip, backup)
        if sha256(backup) != sha256(media_zip):
            raise RuntimeError("Backup fehlerhaft - Abbruch, nichts veraendert.")
        say("Backup des Originals: %s" % backup)
    elif is_ours(backup):
        raise RuntimeError("Backup-Datei ist selbst veraendert - Abbruch.")
    log, _ = make_zip(backup, media_zip, c, empty)
    return media_zip, log


def build_mediapc(mount, c, empty):
    """Alternative (--mediapc): Kopie nach Mount\\mediapc (braucht Extra Options)."""
    src = os.path.join(mount, "media", ZIP_NAME)
    backup = src + BACKUP_SUFFIX
    if os.path.isfile(backup):
        src = backup
    mediapc = os.path.join(mount, "mediapc")
    dst = os.path.join(mediapc, ZIP_NAME)
    os.makedirs(mediapc, exist_ok=True)
    if os.path.isfile(dst) and not is_ours(dst):
        bak = dst + ".bak_%s" % time.strftime("%Y%m%d-%H%M%S")
        shutil.move(dst, bak)
        say("Vorhandene fremde %s gesichert als %s" % (ZIP_NAME, os.path.basename(bak)))
    log, changed = make_zip(src, dst, c, empty)
    written = [dst]
    for name, data in changed.items():
        p = os.path.join(mediapc, *name.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        written.append(p)
    with open(os.path.join(mediapc, STATE_NAME), "w", encoding="utf-8") as f:
        f.write(MARKER + "\n")
        f.write("installiert: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        for p in written:
            f.write("datei: %s\n" % os.path.relpath(p, mediapc))
    return dst, log


def uninstall_mediapc(mount, quiet=False):
    mediapc = os.path.join(mount, "mediapc")
    state = os.path.join(mediapc, STATE_NAME)
    if not os.path.isfile(state):
        return 0
    removed = 0
    for line in open(state, encoding="utf-8"):
        if line.startswith("datei: "):
            p = os.path.join(mediapc, line[7:].strip())
            if os.path.isfile(p):
                os.remove(p)
                removed += 1
    os.remove(state)
    for d in (os.path.join(mediapc, "AI"), mediapc):
        try:
            os.rmdir(d)
        except OSError:
            pass
    if not quiet:
        say("mediapc: %d Dateien entfernt." % removed)
    return removed


def uninstall(mount):
    media_zip = os.path.join(mount, "media", ZIP_NAME)
    backup = media_zip + BACKUP_SUFFIX
    did = False
    if os.path.isfile(backup):
        if is_ours(backup):
            raise RuntimeError("Backup-Datei ist veraendert - bitte manuell pruefen.")
        with zipfile.ZipFile(backup) as z:
            if z.testzip() is not None:
                raise RuntimeError("Backup-Datei ist beschaedigt - bitte manuell pruefen.")
        try:
            os.replace(backup, media_zip)
        except PermissionError:
            raise RuntimeError("Datei ist gesperrt - bitte Spiel/Azimuth komplett schliessen.")
        if os.path.isfile(media_zip + STATE_SUFFIX):
            os.remove(media_zip + STATE_SUFFIX)
        say("Original %s wiederhergestellt." % ZIP_NAME)
        did = True
    if uninstall_mediapc(mount):
        did = True
    if not did:
        say("Nichts zu entfernen (keine Installation gefunden).")
    else:
        say("Das Spiel nutzt wieder die Originalwerte.")


def main():
    say("=" * 70)
    say(" FH2 More Traffic Mod v%s" % VERSION)
    say("=" * 70)
    mount = find_mount()
    say("Spielordner: %s" % mount)

    if "--uninstall" in sys.argv:
        uninstall(mount)
        return 0

    empty = "--test-empty" in sys.argv
    use_mediapc = "--mediapc" in sys.argv
    c, ini = read_ini()
    if "--test-repack" in sys.argv:
        say("\n*** TEST-MODUS: Archiv wird neu geschrieben, alle Werte bleiben ORIGINAL ***")
    if empty:
        say("\n*** DIAGNOSE-MODUS: Verkehrsdichte = 0 (es sollten KEINE Verkehrsautos fahren) ***")
    say("")
    say("Einstellungen (%s):" % os.path.basename(ini))
    say("  TrafficMultiplier       %s" % fmt(c["mult"]))
    say("  MaxActiveTraffic        %d   (Original %d)" % (c["max_active"], ORIG_MAX_ACTIVE))
    say("  InitialNumTraffic       %d   (Original %d)" % (c["initial"], ORIG_INITIAL))
    say("  MaxActiveTypes          %d   (Original 8)" % c["types"])
    say("  SpawnDistanceMultiplier %s" % fmt(c["dist"]))
    say("  RaceTrafficMultiplier   %s" % fmt(c["race"]))
    say("  FestivalMultiplier      %s" % fmt(c["festival"]))
    say("  FillOpenWorldTraffic    %d" % c["fill"])
    say("  MaxDensity              %s" % fmt(c["cap"]))

    if use_mediapc:
        dst, log = build_mediapc(mount, c, empty)
    else:
        # alte mediapc-Installation (v1.0) aufraeumen, damit nichts doppelt wirkt
        if uninstall_mediapc(mount, quiet=True):
            say("Alte mediapc-Installation entfernt (nicht mehr noetig).")
        dst, log = install_direct(mount, c, empty)

    say("")
    say("Geaenderte Werte:")
    for l in log:
        say(l)
    if not log:
        say("    (keine - Diagnose setzt nur Dichte auf 0)" if empty else "    (keine)")
    try:
        with open(os.path.join(script_dir(), "FH2_MoreTraffic_Bericht.txt"), "w", encoding="utf-8", newline="\r\n") as f:
            f.write("%s  %s  %s\n" % (MARKER, time.strftime("%Y-%m-%d %H:%M:%S"), " ".join(sys.argv[1:])))
            f.write("\n".join(log) + "\n")
    except OSError:
        pass
    say("")
    say("OK: %s" % dst)
    if use_mediapc:
        ensure_media_overrides(mount)
    say("")
    say("Fertig. Spiel starten und auf einer Autobahn/in einer Stadt testen.")
    say("Rueckgaengig: 'More-Traffic entfernen.bat' (stellt das Original wieder her).")
    return 0


if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    except SystemExit as e:
        say(str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        say("\nFEHLER: %s" % e)
    try:
        input("\nEnter zum Schliessen ...")
    except Exception:
        pass
    sys.exit(rc)
