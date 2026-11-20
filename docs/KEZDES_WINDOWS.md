# Kezdés Windows 11 alatt – a letöltéstől a beadásig

Ez az elsőként követendő útmutató. **Ne a fájlra dupla kattintással próbáld elindítani az appot.** A felületet a Dockerben futó szerver szolgálja ki, a böngészőben `http://localhost:8080` címen nyitod meg.

## 0. Mit kell a végén beadnod?

1. A saját GitHub-repository URL-jét, benne a teljes forrással.
2. A ténylegesen működő nyilvános HTTPS URL-t.
3. Rövid PDF-dokumentációt a saját futtatás eredményeivel.

A képernyőképen 2026. november 21. 00:00 látszik, vagyis november 20. végén éjfél. A szöveges leírás ugyanakkor nyitva hagyott határidőt említ. Az aktuális Moodle-határidőt ellenőrizd: ez nem november 21. estét jelenti.

## 1. Egyszeri előkészítés

### Docker Desktop

Töltsd le a [hivatalos Docker Desktop Windows telepítőt](https://docs.docker.com/desktop/setup/install/windows-install/). A WSL 2 hátteret válaszd, és Linux-konténereket használj. Ha a telepítő újraindítást kér, végezd el; utána indítsd el a Docker Desktopot, és várd meg, amíg a motor elindul.

PowerShellben ellenőrizd:

```powershell
wsl --version
docker version
docker info --format '{{.OSType}}'
```

A `docker version` parancsnak Client **és** Server adatokat kell mutatnia; az utolsó parancsnak `linux` a kívánt eredménye. Ha csak a Client látszik, előbb a Docker Desktopot kell működésre bírni. Ha a WSL hiányzik vagy frissítendő, a Docker hivatalos telepítési útmutatójának WSL-lépéseit kövesd; a BIOS/UEFI virtualizáció is legyen engedélyezve.

### Fiókok és segédprogramok

- Hozz létre vagy használj saját [Docker Hub](https://hub.docker.com/) fiókot; erősítsd meg az e-mailt, ha kéri.
- Hozz létre vagy használj saját [GitHub](https://github.com/) fiókot.
- Telepítsd a [Git for Windows](https://git-scm.com/downloads/win) programot, ha a `git --version` még nem működik.
- A cloudflared telepíthető PowerShellből: `winget install --id Cloudflare.cloudflared -e`. Ha a winget nem érhető el, a [hivatalos Cloudflare letöltőoldal](https://developers.cloudflare.com/tunnel/downloads/) Windows 64 bites telepítőjét használd.

A telepítések után nyiss új PowerShell-ablakot, hogy a PATH frissüljön. `cloudflared --version` és `git --version` mutassa a program verzióját. Python/Node/PostgreSQL külön telepítése az alkalmazás indításához nem kell.

## 2. A projekt kibontása

A ZIP-ben egy `drone-swarm` mappa van. Csomagold ki úgy, hogy például ez legyen a helye:

```text
C:\projektek\drone-swarm
```

PowerShellben:

```powershell
cd C:\projektek\drone-swarm
Get-ChildItem
```

Itt kell látnod a `stack.yml`, `README.md`, `backend`, `frontend`, `database` és `scripts` elemeket. A további parancsokat ebből a mappából indítsd. A ZIP belsejéből ne futtass scripteket.

## 3. A saját image-ek felépítése és a Swarm elindítása

A Docker Hub webes felületén hozz létre két repositoryt `dronelog-backend` és `dronelog-frontend` névvel, a saját felhasználóneved alatt. Oktatási bemutatóhoz a Public láthatóság egyszerű. A Docker Hub image-tárhely; a GitHubon majd a forráskód lesz.

Az alábbiakban a `SAJAT_DOCKERHUB_NEV` helyére a Docker Hub felhasználónevedet írd, kisbetűkkel, szóköz nélkül. Ez nem feltétlenül egyezik a GitHub-neveddel.

```powershell
docker login -u SAJAT_DOCKERHUB_NEV
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -DockerHubUser SAJAT_DOCKERHUB_NEV
```

A Docker-belépés titkát csak a Docker által kért helyre add meg. Kétlépcsős azonosításnál a Docker által engedélyezett belépési módot vagy személyes hozzáférési tokent használd; ne írd bele a kódba. A `powershell` parancs a helyi shellt indítja a megadott futtatási házirenddel, nem módosít tartós gépszintű házirendet.

Az első telepítés hálózattól függően több perc. A script:

1. Ellenőrzi a Linux Docker motort és a manager jogosultságot.
2. Szükség esetén `docker swarm init` paranccsal létrehozza az egy node-os Swarmot.
3. Megjelöli az adatbázis node-ját, és létrehozza a tartós volume-ot.
4. Véletlen adatbázisjelszót és szerkesztőkulcsot hoz létre Docker secretként.
5. Buildeli a két saját image-et, és feltölti a Docker Hubra.
6. `docker stack deploy` paranccsal telepít, majd kivárja a szolgáltatásokat és az API-t.

Ellenőrizd:

```powershell
docker node ls
docker stack services dronelog
docker stack ps dronelog
Invoke-RestMethod http://localhost:8080/api/health
```

Elvárt: `dronelog_frontend 1/1`, `dronelog_backend 2/2`, `dronelog_db 1/1`; az API-ban `status: ok`, `database: ok`. A pillanatnyi 0/1 vagy 1/2 indulás közben még lehet normális, tartósan viszont hibát kell keresni. A végső sikeres kimenetről készíts képet, titkok nélkül.

## 4. Használd a valódi alkalmazást

Nyisd meg a böngészőben: **http://localhost:8080**.

Olvasás kulcs nélkül is működik. A szerkesztőkulcs megjelenítése:

```powershell
Get-Content .\.secrets\admin_token.txt
```

Másold a kulcsot a felület szerkesztésengedélyező ablakába. Hozz létre egy egyedi, kitalált feladatot, például „Bemutató – tetőfelmérés”, majd frissítsd az oldalt. A rekordnak meg kell maradnia. Próbáld a státuszváltást is. Készíts képet a felületről úgy, hogy a titkos kulcs ne látszódjon.

## 5. Nyilvános cím a tanárnak

Nyiss **egy második** PowerShell-ablakot:

```powershell
cloudflared tunnel --url http://localhost:8080
```

A kimenetben egy valódi `https://valami.trycloudflare.com` alakú cím jelenik meg. A „valami” véletlenszerű, nem előre tudható. A kiírt teljes HTTPS címet másold ki; ne az itt szereplő példát add be.

Nyisd meg a címet telefonon, **Wi-Fi kikapcsolva, mobilinternettel**. Ellenőrizd, hogy ugyanaz a felület és a létrehozott rekord látszik. Jegyezd fel az ellenőrzés időpontját, és készíts képernyőképet az URL-lel. A tanárnak ezt a címet adod, nem a localhostot, nem egy 192.168.x.x címet és nem a Docker Hub image linkjét.

Ezt a terminált hagyd nyitva. A gép ne aludjon el; a Docker Desktopot se zárd le. A tunnel folyamat leállításával megszűnik az elérés, és újraindításkor új URL keletkezik. A beadáskor és a bemutatáskor is a működő aktuális link kell.

## 6. Az automatikus bizonyító tesztek

Vissza az első terminálba, a projekt mappájában:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1 -PublicUrl 'https://IDE_A_TENYLEGES_CIM.trycloudflare.com'
```

A példacím helyett a saját, tényleges címedet add meg. A script adatot ír és olvas, ellenőrzi a jogosulatlan írás elutasítását, növeli a replikaszámot, leállít és pótlásig követ egy API-konténert, újralétrehozza az adatbázis taskját, és visszaolvassa a megmaradt adatot. Végül az eredeti API-replikaszámot állítja vissza.

A rövid megszakítás a hibapróba része. A futás eredménye az `evidence\run_...` mappába kerül. A `[PASSED]` a ténylegesen ellenőrzött pontra vonatkozik; `[FAILED]` esetén ne állíts sikert a beadásban. A `PublicUrl` elhagyásakor a nyilvános próba `[SKIPPED]` lesz: ettől a helyi tesztek még sikerülhetnek, de a külső elérés nincs igazolva.

A böngészős rögzítést és a telefonos megnyitást a script nem tudja helyetted elvégezni. A 4–5. lépésben készített bizonyíték ezeket egészíti ki.

## 7. GitHub-repository létrehozása

A GitHubon hozz létre egy **üres**, `drone-swarm` nevű Public repositoryt. Most ne kérj automatikusan README-t, `.gitignore`-t vagy licencet, mert a forráscsomagban már vannak projektfájlok. Privát repo is elfogadható a kiírás szerint, de az oktatónak külön hozzáférést kell adnod.

A létrejött repository URL-je például `https://github.com/SAJAT_GITHUB_NEV/drone-swarm`. Ezt majd a saját adatodra cserélve használd.

```powershell
git init
git branch -M main
git check-ignore .secrets/admin_token.txt .secrets/db_password.txt
git status --short
```

A `git check-ignore` írja ki a két helyi titokfájl nevét: ez mutatja, hogy ki vannak zárva. A titkok tartalmát nem jeleníti meg. Ha nem írja ki őket, állj meg, és ellenőrizd a `.gitignore` meglétét, mielőtt feltöltesz.

## 8. A mért eredményekből PDF és beadási szöveg

Hozz létre `evidence\screenshots` mappát, és tedd bele a saját képernyőképeidet. Ne tartalmazzanak jelszót vagy tokent. A JSON és a parancskimenet önmagában is megőrzi az automatikus méréseket.

Először a jelentés minden automatikus eredménnyel, kézi igazolások nélkül is elkészíthető:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\make-report.ps1 -StudentName 'SAJAT NEV' -RepositoryUrl 'https://github.com/SAJAT_GITHUB_NEV/drone-swarm' -PublicUrl 'https://IDE_A_TENYLEGES_CIM.trycloudflare.com' -Open
```

Ha a webes és a telefonos próba ténylegesen megtörtént, a teljes parancs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\make-report.ps1 `
  -StudentName 'SAJAT NEV' `
  -RepositoryUrl 'https://github.com/SAJAT_GITHUB_NEV/drone-swarm' `
  -PublicUrl 'https://IDE_A_TENYLEGES_CIM.trycloudflare.com' `
  -UiVerified -UiNote 'Az en egyedi feladatom ID-je/cime; letrehozas es ujratoltes ideje.' `
  -ExternalVerified -ExternalNote 'Telefon, kikapcsolt Wi-Fi, mobilinternet; a megnyitas idopontja.' `
  -Open
```

A sortörésekhez használt backtick a sor legutolsó karaktere legyen; utána ne kerüljön szóköz. A parancs egy sorban is kiadható. A saját időpontot és tényleges adatot írd a megjegyzésekbe. Opcionálisan `-Neptun 'SAJATKOD'` adható meg, de személyes adatot csak akkor tegyél nyilvános repóba, ha ezt valóban akarod.

A script a legfrissebb valódi mérésből dolgozik. Másik, a projekt saját `evidence\run_...` almappájában levő futáshoz `-EvidenceFile 'C:\projektek\drone-swarm\evidence\run_...\test-results.json'` adható. Ha a tunnel címe időközben változott, az új címmel futtasd újra a tesztet is.

Megnyílik a `docs\Beadasi_dokumentacio.html`. **Ctrl+P → Mentés PDF-ként → A4**. Mentsd `docs\Beadasi_dokumentacio.pdf` néven. Az eredmény a rövid beadási dokumentáció: architektúra, szolgáltatások, telepítés és a saját mérési adatok. Ha a böngésző plusz fejlécet/láblécet tesz rá, kapcsold ki a nyomtatási beállításokban.

A script frissíti a README aktuális linkjeit, és előkészíti a `docs\BEADAS.txt` beadási szöveget. A „hallgató igazolta” kézi pontok kifejezetten a saját ellenőrzésedet dokumentálják.

## 9. Feltöltés és tényleges beadás

```powershell
git add .
git diff --cached --name-only
git commit -m 'DroneLog Docker Swarm projekt es meresi bizonyitekok'
git remote add origin https://github.com/SAJAT_GITHUB_NEV/drone-swarm.git
git push -u origin main
```

Push előtt a fájllistában ne legyen `.secrets` vagy `.env`. A feltöltésnél a saját GitHub-belépésedet használd. Ha a Git nevet/e-mailt kér, állítsd be a projektben: `git config user.name 'Sajat neved'` és `git config user.email 'A_GITHUBON_HASZNALT_CIMED'`; választhatsz a GitHub fiókodban megadott noreply címet. Ha az origin már létezik, `git remote -v` segítségével ellenőrizd, ne hozd létre még egyszer.

Nyisd meg a repositoryt a böngészőben, és ellenőrizd, hogy a forrás, a README, a Dockerfile-ok, a stack, a mérések és a PDF is látszanak. Ezután a Moodle-be add be a repo linkjét, a nyilvános app linkjét és a PDF-et. A `BEADAS.txt` szövege segít; a tényleges Beadás gombot is használd.

Ha a PDF csak később került a mappába, ismét: `git add docs/Beadasi_dokumentacio.pdf`, `git commit -m 'Vegleges PDF dokumentacio'`, `git push`.

## 10. Gyors hibakeresés

| Jelenség | Első ellenőrzés / megoldás |
| --- | --- |
| `docker` nem ismert | Docker Desktop telepítve van-e; új PowerShell-ablak. |
| `Cannot connect to the Docker daemon` / hiányzó Server | Docker Desktop elindítása, motor indulásának kivárása. |
| `OSType=windows` | Docker Desktop átállítása Linux containers módra. |
| `denied`, `unauthorized` push közben | `docker login -u ...`, felhasználónév és repositorytulajdonos egyezése. |
| `invalid reference format` | Kisbetűs tényleges Docker Hub-név; a script beállítja az image-változókat. |
| Nem tud advertise címet választani | A hiba által felsorolt Docker-node címek alapján `-AdvertiseAddr 'A_NODE_TENYLEGES_IPJE'`; ne találj ki publikus IP-t. |
| Tartósan `db 0/1` | `docker service ps --no-trunc dronelog_db`, node címke, secret és volume ellenőrzése. |
| API `503`, illetve backend újraindul | `docker service logs --tail 80 dronelog_backend`; majd az adatbázis naplója. |
| 8080-as port foglalt | Az azt használó másik saját program/stack leállítása vagy célzott portcsere a stackben és minden URL-ben. |
| Helyben működik, nyilvánosan 502 | A tunnel valóban a `http://localhost:8080` címre mutat-e; fut-e Docker és frontend. |
| Tunnel hálózati kapcsolat nem jön létre | Ha QUIC/UDP blokkolt: `cloudflared tunnel --protocol http2 --url http://localhost:8080`; új URL-t használj. |
| `cloudflared` nem ismert | Új terminál, `cloudflared --version`, hivatalos telepítő/PATH ellenőrzés. |
| Szerkesztés 401 | A saját `.secrets/admin_token.txt` pontos tartalmával jelentkezz be. |
| Secret fingerprint eltérés | Állítsd vissza az eredeti helyi `.secrets` fájlokat. A secretet és az adatbázist ne töröld találomra. |

Hasznos parancsok:

```powershell
docker stack services dronelog
docker stack ps --no-trunc dronelog
docker service logs --tail 80 dronelog_backend
docker service logs --tail 80 dronelog_db
Invoke-RestMethod http://localhost:8080/api/health
```

Elakadáskor ezek kimenetét vagy a hiba képernyőképét küldd vissza. Jelszót, tokent, `.secrets` tartalmat ne küldj.

## 11. Bemutató után

A tunnel ablakában Ctrl+C megszünteti a külső hozzáférést. Ha a tanár még később ellenőrzi, egyeztetett ideig maradjon működőképes. A stack külön állítható le: `docker stack rm dronelog`; a külső volume és titkok megmaradnak. Az újraindítási és védési magyarázatok a README-ben és a VEDES.md fájlban vannak.
