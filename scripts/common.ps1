# Shared helpers. Compatible with Windows PowerShell 5.1 and PowerShell 7.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:LogPath = $null

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host $Message
    if ($script:LogPath) {
        $line = '{0} {1}' -f [DateTime]::UtcNow.ToString('o'), $Message
        Add-Content -LiteralPath $script:LogPath -Value $line -Encoding UTF8
    }
}

function Invoke-Docker {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$Quiet
    )
    if (-not $Quiet) { Write-Step ('> docker ' + ($Arguments -join ' ')) }
    # Windows PowerShell turns native stderr into ErrorRecord objects even for
    # successful commands. Capture it, then use the native exit code explicitly.
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lines = @(& docker @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    $output = ($lines | ForEach-Object { $_.ToString() }) -join "`n"
    if (-not $Quiet -and $output) { Write-Step $output }
    if ($exitCode -ne 0) {
        throw ('docker {0} failed (exit {1}): {2}' -f ($Arguments -join ' '), $exitCode, $output)
    }
    return $output.Trim()
}

function Get-RunningTasks {
    param([Parameter(Mandatory = $true)][string]$Service)
    $text = Invoke-Docker -Arguments @('service', 'ps', '--no-trunc', '--filter', 'desired-state=running', '--format', '{{.ID}}|{{.CurrentState}}', $Service) -Quiet
    if (-not $text) { return @() }
    return @($text -split "`r?`n" | Where-Object { $_ -match '\|Running\b' } | ForEach-Object { ($_ -split '\|', 2)[0] })
}

function Wait-Service {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [Parameter(Mandatory = $true)][int]$Replicas,
        [int]$TimeoutSeconds = 180,
        [string]$AbsentTask = ''
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $actual = @(Get-RunningTasks -Service $Service)
        $desired = [int](Invoke-Docker -Arguments @('service', 'inspect', '--format', '{{.Spec.Mode.Replicated.Replicas}}', $Service) -Quiet)
        if ($desired -eq $Replicas -and $actual.Count -eq $Replicas -and ($AbsentTask -eq '' -or $actual -notcontains $AbsentTask)) {
            return $actual
        }
        Start-Sleep -Seconds 2
    }
    $null = Invoke-Docker -Arguments @('service', 'ps', '--no-trunc', $Service)
    throw ('Timeout: {0} did not reach {1}/{1} running tasks.' -f $Service, $Replicas)
}

function Wait-Api {
    param([string]$BaseUrl = 'http://localhost:8080', [int]$TimeoutSeconds = 180)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd('/') + '/api/health') -TimeoutSec 5
            if ($health.status -eq 'ok' -and $health.database -eq 'ok') { return $health }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw ('API/database readiness timeout: ' + $BaseUrl)
}

function Assert-Manager {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found. Install and start Docker Desktop (Linux containers), then reopen PowerShell.' }
    $osType = Invoke-Docker -Arguments @('info', '--format', '{{.OSType}}') -Quiet
    if ($osType -ne 'linux') { throw 'This project requires Docker Linux containers. Switch Docker Desktop to Linux containers.' }
    $manager = Invoke-Docker -Arguments @('info', '--format', '{{.Swarm.ControlAvailable}}') -Quiet
    if ($manager -ne 'true') { throw 'Run this command against a Swarm manager. First run scripts/deploy.ps1.' }
}
