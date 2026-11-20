# Követelménymátrix és beadási ellenőrzés

Forrás: a mellékelt Docker Swarm projektkiírás, 1–3. oldal. Ez megfeleltetési térkép, nem előzetes pontszámígéret. A működéshez kapcsolódó pontokat a saját futó rendszerrel kell bizonyítani.

| Kiírás / pontozás | Megvalósítás | Beadáshoz szükséges bizonyíték |
| --- | --- | --- |
| Működő alkalmazás, három service – 20 pont | `frontend`, `backend`, `db`; valódi CRUD; három fiktív induló rekord | Saját böngészős mentés és újratöltés, `docker stack services dronelog` |
| Dockerfile, image-ek, reprodukálható stack – 25 pont | Két saját Dockerfile, konkrét verziók, registry push, `stack.yml`, telepítő script | Docker Hub image-linkek/digestek, build/push és stack deploy kimenet |
| Hálózat, adattárolás, biztonság – 15 pont | Két overlay hálózat, külső local volume, DB-node címke, Docker secrets, csak webes publikált port | Hálózat/volume konfiguráció és vizsgálat, titkok nevei értékük nélkül |
| Skálázás, helyreállás, tesztek – 15 pont | API 2 → 3 replika, backendtask leállítás és pótlás, DB-task újralétrehozás | `test-results.json`, `commands.txt`, előtte/utána azonosítók |
| Nyilvános internetes elérés – 10 pont | Host cloudflared → Swarm frontend 8080 | Aktuális HTTPS URL és másik hálózatról sikeres megnyitás |
| Dokumentáció és bemutató – 15 pont | README, architektúra, útmutató, generálható mérési PDF, védési segédlet | Elérhető Git-repo, végleges PDF, élő rendszer és saját magyarázat |

## A beadás akkor tekinthető késznek, ha

- [ ] A forráskód látható a saját GitHub-repositoryban, az oktató hozzáfér.
- [ ] A saját frontend- és backend-image valóban fent van a registryben.
- [ ] `docker node ls`: van Ready/Active manager node.
- [ ] `docker stack services dronelog`: frontend 1/1, backend legalább 2/2, db 1/1.
- [ ] A webes felületen létrehozott rekord újratöltés után látszik.
- [ ] A skálázás és a konténerpótlás mért eredménye sikeres.
- [ ] A DB-konténer újralétrehozása után ugyanaz a rekord megmaradt.
- [ ] A nyilvános URL mobilinternetről / másik hálózatról működik.
- [ ] A README tartalmazza az aktuális URL-t.
- [ ] A rövid PDF tényleges méréseket és képernyőképeket vagy parancskimeneteket tartalmaz.
- [ ] A repo linkjét, az app linkjét és a PDF-et feltöltötted a kiírt beadási felületre.
- [ ] A bemutató idejére a gép, a Docker és a tunnel bekapcsolva marad.

## Amit külön kell tudni megmagyarázni

A két backend-replika nem helyettesíti a három különböző szolgáltatást. A frontend, backend és adatbázis eltérő felelősséget valósít meg. A tunnel nem negyedik kötelező alkalmazásréteg, hanem külső átjáró. A Compose-fájl formátuma és a Compose-futtatás két külön dolog: itt `docker stack deploy` hozza létre a Swarm-szolgáltatásokat.

Egyetlen node elfogadott a kiírásban. Ebben az esetben a hibateszt a leállított konténer automatikus pótlását igazolja; sem a teljes gép kiesését, sem PostgreSQL-replikációt nem demonstrál.
