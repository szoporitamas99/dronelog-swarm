# Saját Swarm-futtatás bizonyítékai

A telepítés és a `scripts/test.ps1` sikeres vagy hibás futása után itt jönnek létre az `run_...` almappák. A csomag nem tartalmaz előre gyártott sikeres Swarm-mérést.

Minden futásban `commands.txt` és `test-results.json` keletkezik. A jelentéskészítő külön `manual-checks.json` fájlban rögzít.

Képernyőképek a `screenshots` almappába:

1. `01-webes-rogzites.png` – új feladat, majd frissítés után is látszó rekord.
2. `02-swarm-services.png` – három service, alaphelyzetben 1/1, 2/2, 1/1 replikák.
3. `03-skalazas.png` – a backend 3/3 állapota.
4. `04-helyreallas.png` – leállított régi task és az új futó task.
5. `05-perzisztencia.png` – DB-taskcsere után a korábbi feladat.
6. `06-kulso-eleres.png` – a tényleges nyilvános URL és a felület másik hálózatról.

