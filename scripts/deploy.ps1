[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9][a-z0-9_-]{2,}$')][string]$DockerHubUser,
    [ValidatePattern('^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$')][string]$Tag = '1.0.0',
    [string]$AdvertiseAddr = ''
)

. (Join-Path $PSScriptRoot 'common.ps1')
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    if ($Tag -eq 'latest') { throw 'Use a fixed version tag, for example 1.0.0, rather than latest.' }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found. Install/start Docker Desktop, then reopen PowerShell.' }
    $osType = Invoke-Docker -Arguments @('info', '--format', '{{.OSType}}') -Quiet
    if ($osType -ne 'linux') { throw 'Switch Docker Desktop to Linux containers before deployment.' }
    $state = Invoke-Docker -Arguments @('info', '--format', '{{.Swarm.LocalNodeState}}') -Quiet
    if ($state -eq 'inactive') {
        $initArguments = @('swarm', 'init')
        if ($AdvertiseAddr) { $initArguments += @('--advertise-addr', $AdvertiseAddr) }
        $null = Invoke-Docker -Arguments $initArguments
    } elseif ($state -ne 'active') {
        throw ('Swarm state is ' + $state + '. Resolve it before deployment; this script will not reset an existing swarm.')
    }
    Assert-Manager
    $nodeId = Invoke-Docker -Arguments @('info', '--format', '{{.Swarm.NodeID}}') -Quiet
    $allNodes = (Invoke-Docker -Arguments @('node', 'ls', '--format', '{{.ID}}') -Quiet) -split "`r?`n"
    $inspectArgs = @('node', 'inspect') + $allNodes
    $nodeDetails = (Invoke-Docker -Arguments $inspectArgs -Quiet) | ConvertFrom-Json
    $otherDatabaseNodes = @($nodeDetails | Where-Object {
        $labelsProperty = $_.Spec.PSObject.Properties['Labels']
        $labelsValue = if ($null -ne $labelsProperty) { $labelsProperty.Value } else { $null }
        $label = if ($null -ne $labelsValue) { $labelsValue.PSObject.Properties['dronelog.db'] } else { $null }
        $null -ne $label -and $label.Value -eq 'true' -and $_.ID -ne $nodeId
    })
    if ($otherDatabaseNodes.Count -gt 0) {
        throw 'Another node is already labelled dronelog.db=true. Run deployment on the original database node; a local volume must not be moved implicitly.'
    }
    $null = Invoke-Docker -Arguments @('node', 'update', '--label-add', 'dronelog.db=true', $nodeId)
    $null = Invoke-Docker -Arguments @('volume', 'create', '--label', 'project=dronelog', 'dronelog_pgdata')

    $secretDirectory = Join-Path $projectRoot '.secrets'
    $null = New-Item -ItemType Directory -Force -Path $secretDirectory
    $existingSecretsText = Invoke-Docker -Arguments @('secret', 'ls', '--format', '{{.Name}}') -Quiet
    $existingSecrets = @($existingSecretsText -split "`r?`n")
    foreach ($secret in @(@{Name='dronelog_db_password';File='db_password.txt'}, @{Name='dronelog_admin_token';File='admin_token.txt'})) {
        $secretPath = Join-Path $secretDirectory $secret.File
        $existsInSwarm = $existingSecrets -contains $secret.Name
        if ($existsInSwarm -and -not (Test-Path -LiteralPath $secretPath)) {
            throw ('Existing secret ' + $secret.Name + ' has no matching local file. Restore the original .secrets folder; do not silently replace database credentials.')
        }
        if (-not (Test-Path -LiteralPath $secretPath)) {
            $randomBytes = New-Object byte[] 32
            $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
            try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
            $value = ([BitConverter]::ToString($randomBytes)).Replace('-', '').ToLowerInvariant()
            [IO.File]::WriteAllText($secretPath, $value, (New-Object Text.UTF8Encoding($false)))
            $value = $null
        }
        $localHash = (Get-FileHash -LiteralPath $secretPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existsInSwarm) {
            $secretLabels = (Invoke-Docker -Arguments @('secret', 'inspect', '--format', '{{json .Spec.Labels}}', $secret.Name) -Quiet) | ConvertFrom-Json
            $hashProperty = if ($null -ne $secretLabels) { $secretLabels.PSObject.Properties['dronelog.sha256'] } else { $null }
            $remoteHash = if ($null -ne $hashProperty) { $hashProperty.Value } else { '' }
            if (-not $remoteHash) { throw ('Cannot verify the origin of existing secret ' + $secret.Name + ': its fingerprint label is absent. Use the original project deployment; this script will not overwrite unknown secrets.') }
            if ($remoteHash -and $remoteHash -ne $localHash) { throw ('Secret file mismatch: ' + $secret.Name + '. Restore the original file; changing a local file does not rotate a Docker secret.') }
            Write-Step ('Reusing existing secret: ' + $secret.Name)
        } else {
            $null = Invoke-Docker -Arguments @('secret', 'create', '--label', ('dronelog.sha256=' + $localHash), $secret.Name, $secretPath)
        }
    }

    $env:DOCKERHUB_USER = $DockerHubUser
    $env:APP_TAG = $Tag
    Write-Step 'Build and push the application images. Run docker login before this script.'
    foreach ($component in @('backend', 'frontend')) {
        $imageName = '{0}/dronelog-{1}:{2}' -f $DockerHubUser, $component, $Tag
        $null = Invoke-Docker -Arguments @('build', '--pull', '--tag', $imageName, ('./' + $component))
        $null = Invoke-Docker -Arguments @('push', $imageName)
    }
    $null = Invoke-Docker -Arguments @('stack', 'config', '--compose-file', 'stack.yml')
    $null = Invoke-Docker -Arguments @('stack', 'deploy', '--with-registry-auth', '--resolve-image', 'always', '--compose-file', 'stack.yml', 'dronelog')
    $null = Wait-Service -Service 'dronelog_db' -Replicas 1
    $null = Wait-Service -Service 'dronelog_backend' -Replicas 2
    $null = Wait-Service -Service 'dronelog_frontend' -Replicas 1
    $health = Wait-Api
    $null = Invoke-Docker -Arguments @('stack', 'services', 'dronelog')
    $null = Invoke-Docker -Arguments @('stack', 'ps', '--no-trunc', 'dronelog')
    Write-Step ('Ready: http://localhost:8080 ; API instance: ' + $health.instance)
    Write-Step 'Admin token: Get-Content .\.secrets\admin_token.txt (keep it private; do not screenshot it).'
    Write-Step 'Next: .\scripts\test.ps1 ; then start cloudflared in a separate terminal.'
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    Pop-Location
}
