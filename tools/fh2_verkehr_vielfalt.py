"""FH2 Verkehrs-Vielfalt: legt Verkehrs-KOPIEN normaler Spielautos in der Spieldatenbank an.

Die Originalautos bleiben unverändert (Autohaus, Garage, Spielstand). Jede Kopie bekommt eine
neue Auto-Nummer ab 3001 und wird in die Tabelle TrafficCars eingetragen. Ergebnis ist eine
geänderte Kopie von gamedbRC.slt für Mount\\mediaoverride\\Stripped\\.

Aufruf: python fh2_verkehr_vielfalt.py ORIGINAL.slt AUSGABE.slt
"""
import shutil, sqlite3, sys

FIRST_ID = 3001
CARS = [  # Alltagsautos aus dem Spiel (MediaName), passend zu Südeuropa
    'VW_GolfR_10', 'VW_Beetle_66', 'VW_Type2_63', 'VAU_Astra_12', 'REN_Clio_03',
    'FOR_FocusST_12', 'FIA_500AbarthSS_10', 'MER_190E_90', 'MER_E63AMG_13', 'BMW_M5_12',
    'AUD_RS4Avant_13', 'LR_RangeRover_14', 'POR_Cayenne_12', 'NIS_Juke_14', 'VOL_S60Polestar_15',
    'FOR_TransitSSV_11', 'LR_Defender_97', 'JEE_Cherokee_14', 'TES_ModelS_14', 'LAN_Delta_92',
]
CAR_COLUMNS = ('ordinal', 'carid', 'carordinal')
SKIP_TABLES = {  # Fortschritt, Events, Autohaus: Kopien dürfen dort nie auftauchen
    'AnthemEventParticipants', 'BucketListChallenges', 'CarListFilters', 'Data_Car_Buckets',
    'EventCars', 'IEAutoShowCars', 'IslandIEDriveCars', 'MiniCareerCars', 'RaceParticipants',
    'RentalCars', 'Rewards_EventCars', 'TrafficCars', 'CarsDropParts', 'StripeColors',
}


def build(source, target):
    shutil.copyfile(source, target)
    db = sqlite3.connect(target)
    c = db.cursor()
    tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
    plan = []  # (table, car column, primary key column)
    for t in tables:
        if t in SKIP_TABLES or t.startswith('NewProfile_') or t == 'Data_Car':
            continue
        info = list(c.execute(f"pragma table_info('{t}')"))
        car_col = next((r[1] for r in info if r[1].lower() in CAR_COLUMNS), None)
        if not car_col:
            continue
        pk = next((r[1] for r in info if r[5] == 1), None)
        plan.append((t, car_col, pk, [r[1] for r in info]))
    used = {r[0] for r in c.execute('select Id from Data_Car')}
    added = []
    for k, name in enumerate(CARS):
        src = c.execute('select Id from Data_Car where MediaName=?', (name,)).fetchone()
        if not src:
            print('fehlt im Spiel, übersprungen:', name)
            continue
        src = src[0]
        new = FIRST_ID + k
        assert new not in used
        cols = [r[1] for r in c.execute("pragma table_info('Data_Car')")]
        row = list(c.execute('select * from Data_Car where Id=?', (src,)).fetchone())
        row[cols.index('Id')] = new  # ModelId bleibt = Original (gleiches 3D-Modell)
        c.execute(f"insert into Data_Car values ({','.join('?' * len(row))})", row)
        for t, car_col, pk, cols in plan:
            rows = c.execute(f"select * from '{t}' where \"{car_col}\"=?", (src,)).fetchall()
            for r in rows:
                r = list(r)
                r[cols.index(car_col)] = new
                if pk and pk != car_col:
                    old = r[cols.index(pk)]
                    cand = old - src * 1000 + new * 1000 if src * 1000 <= old < src * 1000 + 1000 else None
                    if cand is None or c.execute(f"select 1 from '{t}' where \"{pk}\"=?", (cand,)).fetchone():
                        cand = c.execute(f"select max(\"{pk}\") + 1 from '{t}'").fetchone()[0]
                    r[cols.index(pk)] = cand
                elif not pk and 'ID' in cols:  # z. B. CarPartPositions: ID ohne Primärschlüssel
                    old = r[cols.index('ID')]
                    if src * 1000 <= old < src * 1000 + 1000:
                        r[cols.index('ID')] = old - src * 1000 + new * 1000
                c.execute(f"insert into '{t}' values ({','.join('?' * len(r))})", r)
        c.execute('insert into TrafficCars (CarId, IsLaunchChunkCar) values (?, 0)', (new,))
        added.append((new, name))
    db.commit()
    bad = c.execute('pragma integrity_check').fetchone()[0]
    db.close()
    return added, bad


if __name__ == '__main__':
    added, check = build(sys.argv[1], sys.argv[2])
    for new, name in added:
        print(f'{new}: {name}')
    print('Verkehrsautos neu:', len(added), '| Datenbank-Prüfung:', check)
