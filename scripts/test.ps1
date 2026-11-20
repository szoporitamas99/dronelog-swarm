[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://localhost:8080',
    [string]$PublicUrl = ''
)

. (Join-Path $PSScriptRoot 'common.ps1')
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$evidenceDirectory = Join-Path (Join-Path $projectRoot 'evidence') ('run_' + $runId)
$null = New-Item -ItemType Directory -Force -Path $evidenceDirectory
$script:LogPath = Join-Path $evidenceDirectory 'commands.txt'
$result = [ordered]@{
    schema_version = 1
    project = 'DroneLog'
    run_id = $runId
    started_at = [DateTime]::UtcNow.ToString('o')
    finished_at = $null
    environment = [ordered]@{}
    urls = [ordered]@{local=$BaseUrl.TrimEnd('/'); public=$(if ($PublicUrl) {$PublicUrl.TrimEnd('/')} else {$null})}
    checks = @()
    manual_checks = [ordered]@{
        ui_create_and_read = [ordered]@{status='pending'}
        external_network = [ordered]@{status='pending'}
    }
    test_record = $null
    replica_restore = [ordered]@{from=3; to=$null; status='not_needed'}
    evidence_files = [ordered]@{commands='commands.txt'}
    success = $false
    limitations = @(
        'Automated checks are not a substitute for creating and reading a record in the browser.',
        'A successful public URL request from this computer does not prove access over a separate mobile network.',
        'A replaced container on one node does not demonstrate node-level high availability.',
        'The database uses a local volume on the labelled node; no replicated database or backup is configured.'
    )
}
$currentCheck = 'preflight'
$currentLabel = 'Swarm manager and application readiness'
$originalReplicas = $null
$adminToken = $null
$headers = $null
$failed = $false

function Add-Check {
    param([string]$Id, [string]$Label, [string]$Status, [object]$Details)
    $result.checks += [ordered]@{id=$Id; label=$Label; status=$Status; details=$Details; checked_at=[DateTime]::UtcNow.ToString('o')}
    Write-Step ('[' + $Status.ToUpperInvariant() + '] ' + $Id + ': ' + $Label)
}

function Invoke-App {
    param([string]$Method = 'GET', [string]$Path, [object]$Body = $null, [switch]$Authenticated)
    $parameters = @{Method=$Method; Uri=($BaseUrl.TrimEnd('/') + $Path); TimeoutSec=15}
    if ($Authenticated) { $parameters.Headers = $headers }
    if ($null -ne $Body) {
        $parameters.ContentType = 'application/json; charset=utf-8'
        $parameters.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 8 -Compress))
    }
    # Only method/path are logged, never headers or credentials.
    Write-Step ('> HTTP ' + $Method + ' ' + $Path)
    return Invoke-RestMethod @parameters
}

try {
    Assert-Manager
    $nodes = (Invoke-Docker -Arguments @('node', 'ls', '--format', '{{.ID}}') -Quiet) -split "`r?`n"
    $result.environment = [ordered]@{
        docker_context = Invoke-Docker -Arguments @('context', 'show') -Quiet
        node_id = Invoke-Docker -Arguments @('info', '--format', '{{.Swarm.NodeID}}') -Quiet
        docker_server_version = Invoke-Docker -Arguments @('version', '--format', '{{.Server.Version}}') -Quiet
        powershell_version = $PSVersionTable.PSVersion.ToString()
        single_node = ($nodes.Count -eq 1)
    }
    if ($nodes.Count -ne 1) { throw 'The automatic failure test is designed for the one-node project. Use the documented manual tests for a multi-node swarm.' }
    $originalReplicas = [int](Invoke-Docker -Arguments @('service', 'inspect', '--format', '{{.Spec.Mode.Replicated.Replicas}}', 'dronelog_backend') -Quiet)
    $result.replica_restore.to = $originalReplicas
    $health = Wait-Api -BaseUrl $BaseUrl
    $secretPath = Join-Path $projectRoot '.secrets/admin_token.txt'
    if (-not (Test-Path -LiteralPath $secretPath)) { throw 'Missing .secrets/admin_token.txt. Use the original folder created by deployment.' }
    $adminToken = [IO.File]::ReadAllText($secretPath).Trim()
    if ($adminToken.Length -lt 32) { throw 'The local administrator token is missing or too short.' }
    $headers = @{'X-Admin-Token'=$adminToken}
    $null = Invoke-Docker -Arguments @('node', 'ls')
    $null = Invoke-Docker -Arguments @('stack', 'services', 'dronelog')
    $null = Invoke-Docker -Arguments @('network', 'inspect', '--format', '{{.Name}} driver={{.Driver}} scope={{.Scope}} internal={{.Internal}}', 'dronelog_app_net', 'dronelog_data_net')
    $null = Invoke-Docker -Arguments @('volume', 'inspect', '--format', '{{.Name}} driver={{.Driver}} scope={{.Scope}}', 'dronelog_pgdata')
    $null = Invoke-Docker -Arguments @('secret', 'ls', '--format', '{{.Name}}')
    foreach ($service in @('dronelog_frontend','dronelog_backend','dronelog_db')) {
        $null = Invoke-Docker -Arguments @('service', 'inspect', '--format', '{{.Spec.Name}} image={{.Spec.TaskTemplate.ContainerSpec.Image}}', $service)
    }
    Add-Check -Id $currentCheck -Label $currentLabel -Status 'passed' -Details @{health=$health; original_backend_replicas=$originalReplicas}

    $currentCheck = 'functional_api'
    $currentLabel = 'Authenticated create, read and update; unauthenticated write rejected'
    $payload = @{
        title=('Swarm verification ' + $runId)
        location='Demo test area'
        aircraft='Training UAV'
        mission_date=[DateTime]::Now.ToString('yyyy-MM-dd')
        flight_minutes=12
        status='planned'
        notes='Fictional test record generated by scripts/test.ps1; keep it as evidence.'
    }
    $deniedStatus = 0
    try {
        $null = Invoke-App -Method 'POST' -Path '/api/missions' -Body $payload
    } catch {
        if ($null -ne $_.Exception.Response) { $deniedStatus = [int]$_.Exception.Response.StatusCode }
        else { throw }
    }
    if ($deniedStatus -notin @(401,403)) { throw ('Unauthenticated write was not rejected with 401/403; received ' + $deniedStatus) }
    $created = Invoke-App -Method 'POST' -Path '/api/missions' -Body $payload -Authenticated
    $result.test_record = [ordered]@{id=$created.id; title=$created.title}
    $listed = Invoke-App -Path '/api/missions?limit=500'
    $found = @($listed.items | Where-Object { $_.id -eq $created.id -and $_.title -eq $payload.title })
    if ($found.Count -ne 1) { throw 'The created record could not be read back from PostgreSQL.' }
    $updated = Invoke-App -Method 'PATCH' -Path ('/api/missions/' + $created.id) -Body @{status='completed'} -Authenticated
    if ($updated.status -ne 'completed') { throw 'PATCH did not return the requested updated status.' }
    Add-Check -Id $currentCheck -Label $currentLabel -Status 'passed' -Details @{record_id=$created.id; title=$created.title; unauthorized_status=$deniedStatus; updated_status=$updated.status}

    $currentCheck = 'scale'
    $currentLabel = 'Backend scaled from two to three running replicas'
    # Explicitly establish the teacher's example baseline, regardless of a
    # previous demonstration. The original count is restored in finally.
    $null = Invoke-Docker -Arguments @('service', 'scale', '--detach=true', 'dronelog_backend=2')
    $null = Wait-Service -Service 'dronelog_backend' -Replicas 2
    $null = Invoke-Docker -Arguments @('stack', 'services', 'dronelog')
    $null = Invoke-Docker -Arguments @('service', 'scale', '--detach=true', 'dronelog_backend=3')
    $scaledTasks = @(Wait-Service -Service 'dronelog_backend' -Replicas 3)
    $null = Wait-Api -BaseUrl $BaseUrl
    $null = Invoke-Docker -Arguments @('stack', 'services', 'dronelog')
    Add-Check -Id $currentCheck -Label $currentLabel -Status 'passed' -Details @{from=2; to=3; running_task_ids=$scaledTasks}

    $currentCheck = 'self_healing'
    $currentLabel = 'Stopped backend task replaced automatically by Swarm'
    $beforeTasks = @(Get-RunningTasks -Service 'dronelog_backend')
    $containers = (Invoke-Docker -Arguments @('ps', '--filter', 'label=com.docker.swarm.service.name=dronelog_backend', '--filter', 'status=running', '--format', '{{.ID}}') -Quiet) -split "`r?`n"
    if (-not $containers[0]) { throw 'No local backend container found. The automatic test expects one node.' }
    $victim = $containers[0]
    $victimLabels = (Invoke-Docker -Arguments @('inspect', '--format', '{{json .Config.Labels}}', $victim) -Quiet) | ConvertFrom-Json
    $victimTask = $victimLabels.'com.docker.swarm.task.id'
    $null = Invoke-Docker -Arguments @('stop', '--time', '5', $victim)
    $afterTasks = @(Wait-Service -Service 'dronelog_backend' -Replicas 3 -AbsentTask $victimTask)
    $replacementTasks = @($afterTasks | Where-Object { $beforeTasks -notcontains $_ })
    if ($replacementTasks.Count -lt 1) { throw 'Replica count recovered, but no new task ID was observed.' }
    $null = Wait-Api -BaseUrl $BaseUrl
    $null = Invoke-Docker -Arguments @('service', 'ps', '--no-trunc', 'dronelog_backend')
    Add-Check -Id $currentCheck -Label $currentLabel -Status 'passed' -Details @{stopped_container=$victim; stopped_task=$victimTask; replacement_task_ids=$replacementTasks; running_task_ids=$afterTasks; scope='container replacement on one node'}

    $currentCheck = 'persistence'
    $currentLabel = 'Database task recreated; the same record and update survived'
    $databaseBefore = @(Get-RunningTasks -Service 'dronelog_db')
    if ($databaseBefore.Count -ne 1) { throw 'Expected exactly one running database task.' }
    $null = Invoke-Docker -Arguments @('service', 'update', '--force', '--detach=true', 'dronelog_db')
    $databaseAfter = @(Wait-Service -Service 'dronelog_db' -Replicas 1 -AbsentTask $databaseBefore[0])
    $null = Wait-Api -BaseUrl $BaseUrl
    $afterRestart = Invoke-App -Path '/api/missions?limit=500'
    $persisted = @($afterRestart.items | Where-Object { $_.id -eq $created.id -and $_.title -eq $created.title -and $_.status -eq 'completed' })
    if ($persisted.Count -ne 1) { throw 'The same record/update was not found after database task replacement.' }
    $null = Invoke-Docker -Arguments @('service', 'ps', '--no-trunc', 'dronelog_db')
    Add-Check -Id $currentCheck -Label $currentLabel -Status 'passed' -Details @{old_task=$databaseBefore[0]; new_task=$databaseAfter[0]; preserved_record_id=$created.id; volume='dronelog_pgdata'; same_node=$result.environment.node_id}

    $currentCheck = 'public_http'
    $currentLabel = 'Public URL HTTP check from the deployment computer'
    if ($PublicUrl) {
        $publicUri = [Uri]$PublicUrl
        if (-not $publicUri.IsAbsoluteUri -or $publicUri.Scheme -notin @('http','https') -or $publicUri.UserInfo -or $publicUri.IsLoopback) { throw 'PublicUrl must be a public absolute HTTP(S) address without embedded credentials.' }
        $publicBase = $PublicUrl.TrimEnd('/')
        Write-Step ('> HTTP GET ' + $publicBase + '/api/health')
        $publicHealth = Invoke-RestMethod -Uri ($publicBase + '/api/health') -TimeoutSec 20
        $publicRecords = Invoke-RestMethod -Uri ($publicBase + '/api/missions?limit=500') -TimeoutSec 20
        $publicMatch = @($publicRecords.items | Where-Object { $_.id -eq $created.id -and $_.title -eq $created.title })
        if ($publicHealth.status -ne 'ok' -or $publicMatch.Count -ne 1) { throw 'The public URL did not return the same live application and record.' }
        Add-Check -Id $currentCheck -Label $currentLabel -Status 'passed' -Details @{url=$publicBase; health=$publicHealth; matched_record_id=$created.id; independent_network_verified=$false}
    } else {
        Add-Check -Id $currentCheck -Label $currentLabel -Status 'skipped' -Details @{reason='No -PublicUrl argument. Start the tunnel, then rerun with its current URL.'}
    }
    $result.success = $true
} catch {
    $failed = $true
    $result.success = $false
    Add-Check -Id $currentCheck -Label $currentLabel -Status 'failed' -Details @{error=$_.Exception.Message}
    Write-Step ('TEST FAILED: ' + $_.Exception.Message)
} finally {
    if ($null -ne $originalReplicas) {
        try {
            $null = Invoke-Docker -Arguments @('service', 'scale', '--detach=true', ('dronelog_backend=' + $originalReplicas))
            $null = Wait-Service -Service 'dronelog_backend' -Replicas $originalReplicas
            $result.replica_restore.status = 'passed'
        } catch {
            $result.replica_restore.status = 'failed'
            $result.replica_restore.error = $_.Exception.Message
            $result.success = $false
            $failed = $true
            Write-Step ('WARNING: replica count could not be restored: ' + $_.Exception.Message)
        }
    }
    $finishedIds = @($result.checks | ForEach-Object { $_.id })
    foreach ($pendingId in @('preflight','functional_api','scale','self_healing','persistence','public_http')) {
        if ($finishedIds -notcontains $pendingId) { Add-Check -Id $pendingId -Label 'Not run' -Status 'skipped' -Details @{reason='An earlier test failed.'} }
    }
    $adminToken = $null
    $headers = $null
    $result.finished_at = [DateTime]::UtcNow.ToString('o')
    $jsonPath = Join-Path $evidenceDirectory 'test-results.json'
    $json = $result | ConvertTo-Json -Depth 15
    [IO.File]::WriteAllText($jsonPath, $json, (New-Object Text.UTF8Encoding($false)))
    Write-Step ('Evidence saved: ' + $evidenceDirectory)
    Write-Step 'Still required: create/read a record in the browser; verify the public URL over mobile data; add screenshots and the current links to the submission.'
    Pop-Location
}
if ($failed) { exit 1 }
