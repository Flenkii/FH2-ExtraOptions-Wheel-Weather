#!/usr/bin/env python3
"""Packs the release ZIP.

    python3 tools/make_release.py <winmm.dll> <output.zip>

Layout:
    LIESMICH.txt, Tastenbelegung.txt, LICENSE.txt
    Azimuth/winmm.dll, Azimuth/FH2_ExtraOptions.ini          (required)
    Optional/Profile/<name>/FH2_Lenkrad.ini, FH2_Tastatur.ini  (ready-made settings)

The profile INIs are the mod's own default files (taken from the C sources, so they always match
the DLL) with a few values changed. No game files are packed."""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def c_literal(source, name):
    """Joins the string literal pieces of `static const char <name>[] = "..." "...";`."""
    text = (ROOT / source).read_text(encoding='utf-8')
    block = text[text.index(f'{name}[] ='):]
    block = block[:block.index(';\r\n') if ';\r\n' in block else block.index(';\n')]
    pieces = re.findall(r'"((?:[^"\\]|\\.)*)"', block)
    escapes = {'r': '\r', 'n': '\n', '"': '"', '\\': '\\', 't': '\t'}
    return ''.join(re.sub(r'\\(.)', lambda m: escapes[m.group(1)], p) for p in pieces)


def keyboard_ini():
    text = c_literal('features/keyboard_pad.c', 'default_ini')
    source = (ROOT / 'features/keyboard_pad.c').read_text(encoding='utf-8')
    table = source[source.index('static Binding bindings[] = {'):]
    table = table[:table.index('};')]
    for key, keys in re.findall(r'\{L"(\w+)", \w+, \w+, L"([^"]*)"', table):
        text += f'{key}={keys}\r\n'
    return text


def changed(text, section, values):
    """Sets key=value lines (keys must exist in the file)."""
    for key, value in values.items():
        pattern = re.compile(rf'^({key}=)[^\r\n]*', re.M)
        assert pattern.search(text), f'{key} fehlt in [{section}]'
        text = pattern.sub(lambda m: m.group(1) + str(value), text, count=1)
    return text


PROFILES = {
    'Controller': ({'Aktiv': 0}, {'Aktiv': 0}),
    'Tastatur': ({'Aktiv': 0}, {'Aktiv': 1}),
    'Lenkrad': ({'Aktiv': 1}, {'Aktiv': 1}),
}


def main():
    dll, output = (Path(a) for a in sys.argv[1:3])
    assert dll.name.lower() == 'winmm.dll', 'die DLL muss winmm.dll heißen (Name steht in der Exporttabelle)'
    wheel, keyboard = c_literal('features/wheel_bridge.c', 'default_ini'), keyboard_ini()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        def add(name, data):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 12, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)

        for name in ('LIESMICH.txt', 'Tastenbelegung.txt'):
            add(name, (ROOT / 'release' / name).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        add('LICENSE.txt', (ROOT / 'LICENSE').read_bytes())
        add('Azimuth/winmm.dll', dll.read_bytes())
        add('Azimuth/FH2_ExtraOptions.ini', (ROOT / 'release/FH2_ExtraOptions.ini').read_bytes())
        for name, (wheel_values, keyboard_values) in PROFILES.items():
            add(f'Optional/Profile/{name}/FH2_Lenkrad.ini', changed(wheel, 'Lenkrad', wheel_values).encode('ascii'))
            add(f'Optional/Profile/{name}/FH2_Tastatur.ini',
                changed(keyboard, 'Tastatur', keyboard_values).encode('ascii'))
    with zipfile.ZipFile(output) as z:
        for info in z.infolist():
            print(f'{info.file_size:>9}  {info.filename}')


if __name__ == '__main__':
    main()
