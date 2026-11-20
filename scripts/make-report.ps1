[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$StudentName,
    [Parameter(Mandatory = $true)][string]$RepositoryUrl,
    [Parameter(Mandatory = $true)][string]$PublicUrl,
    [string]$EvidenceFile = '',
    [string]$Neptun = '',
    [switch]$UiVerified,
    [switch]$ExternalVerified,
    [string]$UiNote = '',
    [string]$ExternalNote = '',
    [switch]$Open
)

# This report preserves measured statuses. Manual verification is an explicit
# student attestation, not a result inferred from an automated API request.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$utf8 = New-Object Text.UTF8Encoding($false)

function ConvertTo-HtmlText([object]$Value) { return [System.Net.WebUtility]::HtmlEncode([string]$Value) }
function Valid-Url([string]$Value, [string]$Label) {
    $parsed = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$parsed) -or $parsed.Scheme -ne 'https' -or $parsed.UserInfo -or $parsed.IsLoopback -or $parsed.Fragment -or $parsed.Query) {
        throw ($Label + ': supply an absolute HTTPS URL without credentials, query parameters or fragment.')
    }
    return $parsed.AbsoluteUri.TrimEnd('/')
}
function State-Name([string]$State) {
    switch ($State) {
        'passed' { return 'SIKERES' }
        'failed' { return 'SIKERTELEN' }
        'skipped' { return 'KIHAGYVA' }
        'attested' { return 'HALLGATO IGAZOLTA' }
        default { return 'FUGGOBEN' }
    }
}

$RepositoryUrl = Valid-Url $RepositoryUrl 'RepositoryUrl'
$PublicUrl = Valid-Url $PublicUrl 'PublicUrl'
if ([string]::IsNullOrWhiteSpace($StudentName)) { throw 'StudentName must not be empty.' }
if ($UiVerified -and [string]::IsNullOrWhiteSpace($UiNote)) { throw 'With -UiVerified give -UiNote: the record created in the browser, its ID/title and the time of the check.' }
if ($ExternalVerified -and [string]::IsNullOrWhiteSpace($ExternalNote)) { throw 'With -ExternalVerified give -ExternalNote: the other network/device and the time of the check.' }

if (-not $EvidenceFile) {
    $candidate = Get-ChildItem -LiteralPath (Join-Path $root 'evidence') -Filter test-results.json -Recurse -File |
        Where-Object { $_.Directory.Name -like 'run_*' } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($null -eq $candidate) { throw 'No measured Swarm evidence found. Run scripts/test.ps1 first.' }
    $EvidenceFile = $candidate.FullName
}
$EvidenceFile = (Resolve-Path -LiteralPath $EvidenceFile).Path
$selectedDirectory = Get-Item -LiteralPath (Split-Path $EvidenceFile -Parent)
$evidenceRoot = [IO.Path]::GetFullPath((Join-Path $root 'evidence'))
if ($selectedDirectory.Parent.FullName -ne $evidenceRoot -or $selectedDirectory.Name -notlike 'run_*' -or (Split-Path $EvidenceFile -Leaf) -ne 'test-results.json') {
    throw 'EvidenceFile must be evidence/run_.../test-results.json inside this project, so report links point to the measured files.'
}
$result = [IO.File]::ReadAllText($EvidenceFile) | ConvertFrom-Json
if ($result.schema_version -ne 1 -or $result.project -ne 'DroneLog') { throw 'Unsupported evidence file.' }
$evidenceDir = Split-Path $EvidenceFile -Parent
$recordedPublic = [string]$result.urls.public
$sameUrl = $recordedPublic.TrimEnd('/') -eq $PublicUrl
if ($recordedPublic -and -not $sameUrl) { throw 'PublicUrl differs from the tested URL. Rerun test.ps1 using the current tunnel address.' }

$checkLabels = @{
    preflight='Swarm, szolgaltatasok es keszenlet'
    functional_api='API: hitelesitett iras es visszaolvasas'
    scale='API skalazas: 2 peldanyrol 3 peldanyra'
    self_healing='Leallitott API-task automatikus potlasa'
    persistence='Adatmegmaradas a DB-task ujraletrehozasa utan'
    public_http='Nyilvanos HTTP-eleres a telepito geprol'
}
$rows = New-Object System.Text.StringBuilder
$details = New-Object System.Text.StringBuilder
foreach ($check in $result.checks) {
    $label = if ($checkLabels.ContainsKey([string]$check.id)) { $checkLabels[[string]$check.id] } else { [string]$check.label }
    $state = [string]$check.status
    $null = $rows.Append('<tr><td>' + (ConvertTo-HtmlText $label) + '</td><td class="' + (ConvertTo-HtmlText $state) + '">' + (ConvertTo-HtmlText (State-Name $state)) + '</td></tr>')
    $body = $check.details | ConvertTo-Json -Depth 10
    $null = $details.Append('<section class="evidence"><h3>' + (ConvertTo-HtmlText $label) + '</h3><p>' + (ConvertTo-HtmlText $check.checked_at) + ' (UTC)</p><pre>' + (ConvertTo-HtmlText $body) + '</pre></section>')
}
$uiState = if ($UiVerified) {'attested'} else {'pending'}
$externalState = if ($ExternalVerified) {'attested'} else {'pending'}
$now = [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz')
$manual = [ordered]@{
    evidence_run_id=$result.run_id
    recorded_at=$now
    student=$StudentName
    public_url=$PublicUrl
    ui_create_and_read=[ordered]@{status=$uiState; note=$UiNote}
    external_network=[ordered]@{status=$externalState; note=$ExternalNote}
    method='Explicit student attestation. Not automatically inferred.'
}
[IO.File]::WriteAllText((Join-Path $evidenceDir 'manual-checks.json'), ($manual | ConvertTo-Json -Depth 6), $utf8)

$requiredIds = @('preflight','functional_api','scale','self_healing','persistence','public_http')
$allPassed = $true
foreach ($id in $requiredIds) {
    $matching = @($result.checks | Where-Object { $_.id -eq $id })
    if ($matching.Count -ne 1 -or $matching[0].status -ne 'passed') { $allPassed = $false }
}
$ready = $allPassed -and $UiVerified -and $ExternalVerified -and $sameUrl -and ($result.replica_restore.status -eq 'passed')
$overall = if ($ready) {'A meresi lista minden pontja kitoltve. A beadast es a repository hozzafereset meg ellenorizni kell.'} else {'A meresi lista meg tartalmaz hianyzo vagy sikertelen pontot. Lasd a teszttablazatot.'}
$runFolder = Split-Path $evidenceDir -Leaf
$idText = if ($Neptun) { ' | Neptun: ' + (ConvertTo-HtmlText $Neptun) } else { '' }
$uiDisplay = if ($UiVerified) { ConvertTo-HtmlText $UiNote } else { 'A webes feluleten adat rogzitese es ujratoltes utani visszaolvasasa meg igazolando.' }
$externalDisplay = if ($ExternalVerified) { ConvertTo-HtmlText $ExternalNote } else { 'A nyilvanos URL mobilinternetrol vagy masik halozatrol meg ellenorizendo.' }
$environment = ConvertTo-HtmlText ($result.environment | ConvertTo-Json -Depth 6)
$restore = ConvertTo-HtmlText ($result.replica_restore | ConvertTo-Json -Depth 6)

$html = @"
<!doctype html><html lang="hu"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>DroneLog - beadási dokumentáció</title>
<style>
@page {size:A4; margin:17mm 17mm 18mm;} *{box-sizing:border-box} body{font:11pt/1.5 'Segoe UI',Arial,sans-serif;color:#142a40;max-width:190mm;margin:28px auto;background:white} h1{font-size:30pt;line-height:1.12;margin:6px 0 12px} h2{font-size:17pt;margin:22px 0 8px;border-bottom:2px solid #159f92;padding-bottom:5px} h3{font-size:12pt;margin:14px 0 4px} p{margin:7px 0} .eyebrow{color:#11877e;font-weight:700;letter-spacing:2px;text-transform:uppercase}.banner{padding:13px 16px;background:#e9f6f3;border-left:4px solid #11998e;margin:15px 0}.muted{color:#586c7b}.arch{padding:15px;background:#eff4f8;border-radius:7px;text-align:center} table{width:100%;border-collapse:collapse;font-size:10pt;margin:10px 0} th,td{text-align:left;vertical-align:top;border-bottom:1px solid #d9e2ea;padding:8px} th{background:#eaf0f6} pre{font:8.3pt/1.35 Consolas,'Courier New',monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f8;padding:11px;border:1px solid #dbe4ed} code{font-family:Consolas,monospace} .passed{color:#08775d;font-weight:700}.failed{color:#ae2541;font-weight:700}.pending,.skipped{color:#9b6212;font-weight:700}.attested{color:#125ca3;font-weight:700}.evidence{break-inside:avoid}.page{break-before:page} a{color:#136d9f;overflow-wrap:anywhere}.small{font-size:9pt}.noprint{padding:12px;background:#fff4d9} @media print{body{margin:0;max-width:none}.noprint{display:none}a{text-decoration:none}h2,h3{break-after:avoid}tr{break-inside:avoid}}
</style></head><body>
<p class="noprint">Mentés PDF-ként: Ctrl+P → Mentés PDF-ként; A4; a böngésző saját fejléce/lábléce kikapcsolható. A parancskimenetek és a JSON a repository evidence mappájában maradnak.</p>
<p class="eyebrow">Felhőszámítás / Cloud Computing</p><h1>DroneLog<br>Docker Swarm projekt</h1>
<p><strong>Hallgató:</strong> $(ConvertTo-HtmlText $StudentName)$idText</p><p><strong>Dokumentum készítése:</strong> $(ConvertTo-HtmlText $now)</p>
<div class="banner">$(ConvertTo-HtmlText $overall)</div>
<p><strong>Forráskód:</strong> <a href="$(ConvertTo-HtmlText $RepositoryUrl)">$(ConvertTo-HtmlText $RepositoryUrl)</a></p><p><strong>Nyilvános alkalmazás:</strong> <a href="$(ConvertTo-HtmlText $PublicUrl)">$(ConvertTo-HtmlText $PublicUrl)</a></p><p class="small muted">A TryCloudflare-cím ideiglenes. A bemutató alatt a helyi gépnek, a Dockernek és a tunnelnek működnie kell.</p>
<h2>1. Az alkalmazás és architektúrája</h2><p>A DroneLog fiktív drónos feladatokat rögzít, listáz, módosít és töröl. A felület mutatja a feladatok állapotát és a befejezett feladatok repülési idejét. A nyilvános látogató olvashat; a módosításhoz Docker secretből ellenőrzött szerkesztőkulcs kell.</p>
<div class="arch">Külső böngésző · HTTPS<br>↓<br>Cloudflare Quick Tunnel · a gazdagépen fut<br>↓<br>Nginx frontend · közzétett 8080-as port<br>↓ app_net overlay · backend:8000<br>FastAPI backend · alaphelyzetben 2 replika<br>↓ data_net overlay · db:5432<br>PostgreSQL · 1 replika → dronelog_pgdata volume</div>
<table><tr><th>Service</th><th>Szerep / tárolás</th><th>Publikált hostport</th></tr><tr><td>frontend</td><td>HTML/CSS/JS és reverse proxy</td><td>8080</td></tr><tr><td>backend</td><td>Állapotmentes API, jogosultság és SQL</td><td>nincs</td></tr><tr><td>db</td><td>Tartós PostgreSQL-adatok</td><td>nincs</td></tr></table>
<h2 class="page">2. Telepítés és működés</h2><p>Két saját Dockerfile építi az alkalmazásimage-eket. A telepítő konkrét verziójú image-eket buildel és tölt Docker Hubra, majd manager node-on Swarm stackként telepít. A YAML nem tartalmaz build utasítást. A replikaszámot, a healthchecket és az újraindítást a Swarm konfiguráció szabályozza.</p>
<pre>docker login -u SAJAT_DOCKERHUB_NEV
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -DockerHubUser SAJAT_DOCKERHUB_NEV
docker stack services dronelog
docker stack ps dronelog
cloudflared tunnel --url http://localhost:8080</pre>
<p>A tényleges telepítőparancs <code>docker stack deploy --with-registry-auth --resolve-image always --compose-file stack.yml dronelog</code>. A stack process-környezeti változókból kapja az image-neveket; a .env fájlt a Swarm nem tölti be automatikusan.</p>
<p>A frontend csak az alkalmazáshálózaton, az adatbázis csak a belső adathálózaton érhető el. A backend mindkettőhöz kapcsolódik. A dronelog.db=true node-címke az adatbázist a helyi volume-ot tartalmazó node-hoz köti.</p>
<h3>Titkok és korlátok</h3><p>A jelszó és az adminisztrációs kulcs külön Docker secret; a létrehozó .secrets könyvtár Gitből ki van zárva. A módosításokat tokenellenőrzés, a bemeneteket validálás, az SQL-t paraméterezés védi. A frontend és az API nem rootként fut.</p><p>Az egy node-os bemutató konténerpótlást igazol, nem teljes gépkiesés elleni hibatűrést. A local volume nem replikált tároló és nem backup. A demó adatbázis-fiókja bootstrap tulajdonos; éles rendszerben korlátozott alkalmazásfiók szükséges. A tunnelnek nincs rendelkezésreállási garanciája, új indításkor más címet adhat.</p>
<h3>A mért környezet</h3><pre>$environment</pre>
<h2 class="page">3. Mérések és kézi ellenőrzések</h2><p><strong>Mérési futás:</strong> $(ConvertTo-HtmlText $result.run_id)<br><strong>Időszak, UTC:</strong> $(ConvertTo-HtmlText $result.started_at) – $(ConvertTo-HtmlText $result.finished_at)</p>
<table><tr><th>Ellenőrzés</th><th>Mért állapot</th></tr>$($rows.ToString())<tr><td>Webes rögzítés és visszaolvasás</td><td class="$uiState">$(ConvertTo-HtmlText (State-Name $uiState))</td></tr><tr><td>Külső hálózatról történő megnyitás</td><td class="$externalState">$(ConvertTo-HtmlText (State-Name $externalState))</td></tr></table>
<h3>Webes próba</h3><p>$uiDisplay</p><h3>Külső hálózati próba</h3><p>$externalDisplay</p><p class="small">A két kézi pontot a hallgató megadott nyilatkozata rögzíti. A saját gépről a publikus URL-re küldött HTTP-kérés önmagában nem igazolja a másik hálózatról való elérést.</p>
<h3>Replikaszám visszaállítása</h3><pre>$restore</pre><p><strong>Teljes nyers bizonyíték:</strong> evidence/$(ConvertTo-HtmlText $runFolder)/test-results.json és commands.txt. A kézi próbák leírása manual-checks.json. Képernyőképek a külön screenshots mappába tehetők; titok ne szerepeljen rajtuk.</p>
<h2 class="page">4. A mérések részletes eredményei</h2><p>Az alábbi részletek közvetlenül a tesztfuttatás JSON-kimenetéből származnak. A sikertelen és kihagyott pontok is láthatók.</p>$($details.ToString())
<h2>5. Hivatalos források</h2><p class="small">Projektkövetelmények: a kapott Docker Swarm projektkiírás, 1–3. oldal.<br>Docker stack telepítés: https://docs.docker.com/engine/swarm/stack-deploy/<br>Overlay: https://docs.docker.com/engine/network/drivers/overlay/<br>Secrets: https://docs.docker.com/engine/swarm/secrets/<br>PostgreSQL image: https://hub.docker.com/_/postgres<br>Cloudflare: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/</p>
</body></html>
"@

$docs = Join-Path $root 'docs'
$null = New-Item -ItemType Directory -Force -Path $docs
$htmlPath = Join-Path $docs 'Beadasi_dokumentacio.html'
[IO.File]::WriteAllText($htmlPath, $html, $utf8)
$submission = @"
Docker Swarm projekt: DroneLog
Hallgato: $StudentName
Repository: $RepositoryUrl
Nyilvanos alkalmazas: $PublicUrl
Dokumentacio: Beadasi_dokumentacio.pdf (a generalt HTML-bol mentsd PDF-kent)
Meresi futas: $($result.run_id)
Megjegyzes: a TryCloudflare-cim ideiglenes; a bemutato alatt a sajat gep es a tunnel fut.
"@
[IO.File]::WriteAllText((Join-Path $docs 'BEADAS.txt'), $submission, $utf8)
$readmePath = Join-Path $root 'README.md'
$readme = [IO.File]::ReadAllText($readmePath)
$replacement = @"
<!-- SUBMISSION:START -->
## Beadási adatok

- Git-repository: $RepositoryUrl
- Nyilvános alkalmazás: $PublicUrl
- Mérési futás: $($result.run_id)
- Dokumentáció: [generált jelentés](docs/Beadasi_dokumentacio.html); PDF-ként is csatolandó.
- Nyers bizonyítékok: [JSON](evidence/$runFolder/test-results.json), [parancskimenetek](evidence/$runFolder/commands.txt).

A cím ideiglenes; a tunnelnek és a gépnek futnia kell. A részletes tesztállapotokat a jelentés tartalmazza.
<!-- SUBMISSION:END -->
"@
$pattern = '(?s)<!-- SUBMISSION:START -->.*?<!-- SUBMISSION:END -->'
if (-not [Regex]::IsMatch($readme, $pattern)) { throw 'README submission markers missing; report was generated but README was not updated.' }
$readme = [Regex]::Replace($readme, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{param($match) $replacement})
[IO.File]::WriteAllText($readmePath, $readme, $utf8)
Write-Host ('Report: ' + $htmlPath)
Write-Host 'Open the HTML in a browser, press Ctrl+P, select Save as PDF. Save as docs/Beadasi_dokumentacio.pdf.'
Write-Host ('Status: ' + $overall)
Write-Host 'README links and docs/BEADAS.txt were updated. Commit the real evidence and final PDF to Git.'
if ($Open) { Start-Process $htmlPath }
