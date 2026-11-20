# Védési segédlet – érthetően elmondható bemutató

## A GitHubon futó bemutató indítása

1. Nyisd meg a saját [Codespaces-listádat](https://github.com/codespaces), és indítsd el a **dronelog-swarm** projekthez tartozó meglévő gépet. Ennek lemezén vannak a bemutató rekordjai.
2. A terminálban futtasd a `docker stack services dronelog` parancsot. Várd meg a `frontend 1/1`, `backend 2/2`, `db 1/1` állapotot. Ha a stack még nincs telepítve, a projekt gyökerében futtasd a `bash scripts/codespace.sh` parancsot.
3. A **Ports** panelen a **DroneLog (8080)** sor láthatósága legyen **Public**. A **Forwarded Address** oszlop HTTPS-címét nyisd meg. Az adatbázis és a registry maradjon belső.
4. A webes űrlaphoz szükséges kulcsot a saját terminálodban a `cat .secrets/admin_token.txt` paranccsal olvashatod ki. A kulcsot a képernyőmegosztás előtt illeszd be a **Szerkesztés engedélyezése** ablakba.

## 3–5 perces bemutató sorrendje

**0:00–0:40 – Alkalmazás.** Nyisd meg a nyilvános URL-t. „A DroneLog egy drónos feladatnyilvántartó. Feladatot lehet felvenni, visszaolvasni, módosítani és törölni. A bemutató minden adata fiktív.” Hozz létre egy rövid mintafeladatot, majd frissítsd az oldalt. A kulcsot ne mutasd a képernyőn.

**0:40–1:20 – Három szolgáltatás.** Mutasd: `docker stack services dronelog`. „A frontend Nginxet futtat, az API Python/FastAPI, a tartós tároló PostgreSQL. Az API-ból két replika működik, így alaphelyzetben négy alkalmazáskonténer van. A frontend és az API a app_net overlay hálózaton, az API és az adatbázis a data_net hálózaton kommunikál név alapján.”

**1:20–2:00 – Skálázás.** `docker service scale dronelog_backend=3`, majd `docker service ps dronelog_backend`. Várd meg a három Running taskot. „Az API állapotmentes: az adatok a közös PostgreSQL-ben vannak, ezért a harmadik példány ugyanazokat az adatokat látja.”

**2:00–2:50 – Öngyógyítás.** Válassz egy backendkonténert, állítsd le, és mutasd az új konténer/task azonosítóját. „A Swarm a kívánt három példány és a tényleges állapot eltérését észleli, majd új taskot indít. Ez konténerszintű helyreállítás egy node-on.”

**2:50–3:40 – Tartós adat.** A mentett mérési jegyzőkönyvben mutasd a DB újralétrehozása előtti és utáni taskazonosítót, valamint ugyanazt a megmaradt feladatazonosítót. Az új taskhoz új adatbázis-konténer tartozik. Ha az idő engedi, élőben is elvégezhető. „A PostgreSQL-adatkönyvtár külső named volume-on van, ezért a konténer cseréje nem törli az adatot.”

**3:40–4:20 – Elérés és korlátok.** „A konténerek egyetlen Linux-gépen, GitHub Codespacesben futnak. A GitHub a frontend 8080-as portját teszi elérhetővé HTTPS-en. A link addig szolgálja ki az alkalmazást, amíg a gép fut. Egy API-konténer kiesését a Swarm pótolja. A teljes gép leállásakor a rendszer a gép újraindításával áll helyre.”

## Rövid, helyes válaszok gyakori kérdésekre

| Kérdés | Válasz |
| --- | --- |
| Mi az image és mi a konténer? | Az image a futtatáshoz szükséges fájlok és beállítások csomagja. A konténer ennek egy elindított példánya. |
| Mi a service és mi a task? | A service a kívánt szolgáltatásállapot, például image + két replika. A task egy konkrét futtatási egység, amelyhez konténer tartozik. Leálláskor új task jön létre. |
| Miért Swarm és nem sima Compose? | A kiírás Swarmot kér. A manager a deklarált replikaszámot fenntartja, taskokat ütemez és pótol; a telepítés `docker stack deploy`. |
| Miért kellett build és push külön? | A stack deploy image-hivatkozásokat használ; nem épít Dockerfile-ból. A registryből minden érintett node le tudja tölteni a szükséges image-et. |
| Mire jó az overlay? | Swarm-szolgáltatásokat kapcsol össze egy logikai hálózatban. Több node között is használható; itt egy node-on demonstráljuk. |
| Miért nincs az adatbázis portja kint? | A böngészőnek csak a webes belépési pont kell. Az adatbázist az API belső hálózaton éri el. |
| Miért az API-t skálázzuk? | Nem tart saját üzleti adatot a helyi fájlrendszerében, ezért több azonos példány tud a közös adatbázissal dolgozni. |
| Miért csak egy DB-replika? | Több PostgreSQL-konténer elindítása önmagában nem hoz létre konzisztens adatbázis-replikációt. Ahhoz külön konfigurált adatbázis-HA szükséges. |
| Mi a healthcheck? | A konténer alkalmazásszintű működését ellenőrző parancs. Az API-próba az adatbázis használhatóságát is ellenőrzi. A hibás taskot a Swarm a szabályai szerint pótolhatja. |
| Miért külső a volume? | Életciklusa elkülönül a stacktől. A stack eltávolítása önmagában nem törli; az új DB-konténer ugyanazt a helyi adatot kapja. |
| Miért kell DB-node címke? | A local volume azon a gépen van, ahol létrejött. A címke oda köti az adatbázist; ettől még a tároló nem válik elosztottá. |
| Hol vannak a jelszavak? | A futó service Docker secrets fájlokból olvassa őket. A létrehozó helyi `.secrets` könyvtár Gitből ki van zárva. |
| Biztonsági mentés a volume? | Nem. A konténercserét túléli, de lemezhiba vagy kézi törlés ellen külön mentés kell. |
| A Cloudflare futtatja a kódot? | Ennél a megoldásnál a saját gép futtatja. A Cloudflare a bejövő kapcsolat továbbítását végzi. |
| Mi történik gépleálláskor? | Egy node esetén minden alkalmazáskonténer és a tunnel leáll. Újra kell indítani őket, és az új tunnelcímet frissíteni kell. |
| Miért nem bizonyítja a változó hostname önmagában a terheléselosztást? | Egy válasz az azt kiszolgáló példányt mutatja. A replikaállapotot a Docker parancsaival igazoljuk; a kapcsolatok újrafelhasználása miatt a válaszok nem feltétlenül váltakoznak. |

## Élő parancsok a Codespace Bash-termináljához

```bash
docker stack services dronelog
docker service scale dronelog_backend=3
docker service ps dronelog_backend
victim=$(docker ps --filter label=com.docker.swarm.service.name=dronelog_backend --format '{{.ID}}' | head -1)
docker stop "$victim"
docker service ps dronelog_backend
docker service update --force dronelog_db
docker service scale dronelog_backend=2
```

A bemutató után a Codespaces-listán a **Stop codespace** művelettel állíthatod le a gépet. A következő alkalommal ugyanazt a gépet indítsd el.

## Kézi parancsok – PowerShell

```powershell
docker stack services dronelog
docker service scale dronelog_backend=3
docker service ps dronelog_backend
$victim = docker ps --filter label=com.docker.swarm.service.name=dronelog_backend --format '{{.ID}}' | Select-Object -First 1
docker stop $victim
docker service ps dronelog_backend
docker service update --force dronelog_db
docker service ps dronelog_db
docker service scale dronelog_backend=2
```

A `docker stop` után várd meg az új Running taskot; egy parancs elfogadása még nem jelenti a helyreállás befejeződését. A DB cseréje alatt rövid API-kiesés előfordulhat. A meglévő feladatot a böngésző frissítésével ellenőrizd.

## Az önálló megértéshez

Olvasd végig a `stack.yml` fájlt, mindkét Dockerfile-t és a `backend/main.py` végpontjait. Tudj elmagyarázni legalább egy teljes kérést: űrlap → POST `/api/missions` → Nginx → API-validálás és tokenellenőrzés → paraméterezett INSERT → PostgreSQL-volume → visszaküldött JSON → lista frissítése. A projekt elkészítéséhez kapott segítséget az intézményi szabályok szerint tüntesd fel; a mért eredményeket a saját futtatásod adja.
