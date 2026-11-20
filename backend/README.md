# Backend fejlesztői jegyzet

A `main.py` definiálja a HTTP-végpontokat és a szerkesztői kulcs ellenőrzését.
A `models.py` a fogadott és visszaadott adatokat ellenőrzi. A `repository.py`
paraméterezett SQL-lel kommunikál a PostgreSQL-lel. A séma létrehozását és a
kitalált kezdeti adatokat a `database/init.sql` tartalmazza, amelyet a hivatalos
PostgreSQL image az üres volume első indításakor futtat le.

## API

| Metódus | Útvonal | Feladat | Kulcs kell? |
| --- | --- | --- | --- |
| GET | `/api/health` | API és adatbázistábla elérhetősége | Nem |
| GET | `/api/instance` | A kérésre válaszoló task azonosítója | Nem |
| GET | `/api/admin/check` | Szerkesztői kulcs ellenőrzése adatváltoztatás nélkül | Igen |
| GET | `/api/missions` | Feladatok listája, `items` és teljes `count` | Nem |
| POST | `/api/missions` | Feladat létrehozása, HTTP 201 | Igen |
| PATCH | `/api/missions/{id}` | Megadott mezők módosítása | Igen |
| DELETE | `/api/missions/{id}` | Feladat törlése, HTTP 204 | Igen |
| GET | `/api/stats` | Darabszámok és lezárt feladatok percei | Nem |
| GET | `/api/openapi.json` | Géppel olvasható API-szerződés | Nem |

A listázás alapértelmezett és legnagyobb `limit` értéke 500. Az `offset`
alapértelmezetten 0. A sorrend dátum, azon belül azonosító szerint csökkenő.
Az instance azonosító nem állít semmit az összes replika számáról; azt a
`docker service ls` parancs mutatja meg.

## Titkok és hibakezelés

Az írások `X-Admin-Token` fejlécét a szolgáltatás a
`/run/secrets/admin_token` fájlhoz hasonlítja. A titok legalább 32 karakteres;
hiánya esetén a szerkesztés HTTP 503 választ ad. Nincs alapértelmezett kulcs.
A generált kulcsot ne küldd be a repositoryba vagy képernyőképen.

Az adatbázis jelszava `/run/secrets/db_password`. A fájlhelyek felülírhatók
`ADMIN_TOKEN_FILE` és `DB_PASSWORD_FILE` környezeti változóval; a titkok értékét
nem környezeti változóban tároljuk. A DB host alapértelmezetten `db`.

Minden adatbázis-művelet rövid életű kapcsolatot és tranzakciót használ. A
kapcsolat automatikusan bezárul. Ha a DB indul vagy újraindul, a healthcheck
503 választ kap, a kérések pedig később újra próbálhatók. A titkot és a belső
adatbázishiba részleteit az API nem adja vissza. A backend nincs közvetlenül
publikálva; a frontend azonos eredetű `/api/` útvonalán érhető el.

## Függőségek és tesztelés

A Dockerfile Python 3.12.16 alapimage-et használ. A Linux/Python 3.12 runtime
függőségei a `requirements.txt` fájlban konkrét verziókkal rögzítettek.

```bash
python -m pip install -r backend/requirements-test.txt
python -m unittest discover -s tests -v
```

A `test_backend.py` 17 API-, jogosultság-, validációs és hibakezelési tesztet
tartalmaz; itt az adatbázis helyett tesztpéldány szerepel. Ez önmagában nem
igazolja a PostgreSQL perzisztenciáját vagy a Swarm működését. Ehhez a fő
útmutató tényleges telepítési és tesztelési lépései szükségesek.

Ellenőrzött elsődleges csomagforrások:

- https://pypi.org/project/fastapi/0.163.1/
- https://pypi.org/project/uvicorn/0.54.0/
- https://pypi.org/project/psycopg/3.3.9/
- https://hub.docker.com/_/python

A csomagverziók rögzítése reprodukálhatóbb buildet ad, de nem helyettesíti a
későbbi karbantartást. A Docker-tagek módosulhatnak; a telepítéshez használt
image digestet a registrybe történő feltöltés után érdemes megőrizni.
