# Ellenőrzési jegyzet a leszállított forráscsomaghoz

Az élő Codespaces-példány november 20-i Swarm-mérései, a külső böngészős ellenőrzés és a képernyőképek a [bemutató mérési mappájában](../evidence/run_20261120T210650141472Z/) érhetők el. Az alábbi táblázat a korábbi fejlesztési állapotot rögzíti.

Dátum: 2026. november 20. A dokumentum a fejlesztéskor ténylegesen elvégzett ellenőrzéseket rögzíti. A saját gépen futó Swarm mérései később, külön az `evidence/run_...` könyvtárba kerülnek.

| Ellenőrzés | Eredmény | Mit bizonyít, és mit nem? |
| --- | --- | --- |
| Backend API-, hitelesítési és validációs egységtesztek | 17/17 sikeres | Valódi FastAPI, helyettesített repository; nem Docker- vagy adatbázis-mérés. |
| Valódi PostgreSQL-integráció | 15/15 sikeres | SQL-séma, CRUD, statisztika, paraméterezés, adatbáziskiesés és folyamat-újraindítás utáni adatmegmaradás. Helyi PostgreSQL 16.2; a célimage 17.12. |
| Frontend DOM/API-szerződés | 11/11 tesztcsoport sikeres | jsdom és helyettesített API: bejelentkezés, CRUD, szűrés, XSS-kezelés, hibák, kijelentkezés. Nem valódi böngészős megjelenítési próba. |
| JavaScript, Python és Bash szintaxis | Sikeres | A forrás értelmezhető; önmagában nem működési bizonyíték. |
| Valódi Docker stack parser | Sikeres, exit 0, figyelmeztetés nélkül | Docker CLI 28.3.3: `docker stack config -c stack.yml`. Nem indult Docker daemon vagy Swarm. |
| PowerShell parser és vezérlési próbák | Sikeres | PowerShell 7.4.6, helyettesített Docker: első/ismételt deploy, secreteltérés elutasítása, tesztfolyamat és replika-visszaállítás. Windows PowerShell 5.1-en még futtatandó. |
| Jelentéskészítő | Sikeres | Függőben levő kézi próbák, külön hallgatói igazolás, eltérő URL elutasítása és HTML-escape ellenőrizve. |
| Konténerimage-build, Swarm-futtatás, overlay és külső URL | A felhasználó gépén elvégzendő | A fejlesztési környezetben Docker daemon nem volt elérhető. Ezeket a mellékelt telepítő és teszt hajtja végre a saját gépen. |
| Valódi böngészős megjelenítés | A felhasználó gépén elvégzendő | Ebben a környezetben a böngésző nem indult; nincs kitalált képernyőkép vagy vizuális teszteredmény. |

A PostgreSQL-integráció részletes, tényleges eredménye: [development-integration-results.json](development-integration-results.json). A helyi adatbázisfolyamat újraindítása nem helyettesíti a tanár által kért Swarm-adatbáziskonténer újralétrehozását.

## Fejlesztői tesztek újbóli futtatása – opcionális

A program Dockeres használatához nem szükséges Python vagy Node telepítése a hostra. Az alábbiak csak a forrás fejlesztői ellenőrzéséhez valók.

Backend, a projektgyökérből, Python 3.12-vel:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-test.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Linuxon a virtuális környezet Pythonja `.venv/bin/python`. A követelményfájlok rögzített verziókat tartalmaznak. A Starlette a tesztkliens HTTPX-integrációjára deprecation figyelmeztetést adhat; a tesztek ettől még lefutnak. A konténer nem telepíti a tesztkliens függőségét.

Frontend, Node.js 18 vagy újabb környezetben:

```powershell
npm ci --prefix tests
node tests/frontend-dom.cjs
```

Stack-séma, futó Docker Desktop mellett vagy önálló Docker CLI-vel:

```powershell
$env:DOCKERHUB_USER = 'SAJAT_DOCKERHUB_NEV'
$env:APP_TAG = '1.0.0'
docker stack config -c stack.yml
```

## A saját futtatás bizonyítékainak szabálya

A `scripts/test.ps1` és a Bash/Python megfelelő valódi Docker-parancsokat és HTTP-kéréseket futtat. Az automatikus tesztkimenethez ne írj kézzel sikeres állapotokat. A `make-report.ps1` a mért JSON-t változatlanul olvassa; a webes és másik hálózati próba külön, megjegyzéssel ellátott hallgatói igazolás.

Az ellenőrzések során használt helyettesített Docker- és API-kimenetek nem kerültek az `evidence` mappába, a beadási PDF-be vagy a README mérési hivatkozásai közé.
