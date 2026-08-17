param(
    [switch]$SkipTailscaleInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function New-RandomSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer)
}

function Get-TailscaleExe {
    $command = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $candidates = @(
        "$env:ProgramFiles\Tailscale\tailscale.exe",
        "$env:LOCALAPPDATA\Tailscale\tailscale.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Wait-HttpHealthy([string]$Url, [int]$Attempts = 30) {
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

$installRoot = Join-Path $env:LOCALAPPDATA 'OpenPost'
$dataDir = Join-Path $installRoot 'data'
$mediaDir = Join-Path $dataDir 'media'
$logDir = Join-Path $installRoot 'logs'
$serverExe = Join-Path $installRoot 'openpost-server.exe'
$envScript = Join-Path $installRoot 'openpost.env.ps1'
$startScript = Join-Path $installRoot 'start-openpost.ps1'
$stopScript = Join-Path $installRoot 'stop-openpost.ps1'
$publicUrlFile = Join-Path $installRoot 'OpenPost.url'

Write-Step "Preparing OpenPost folders"
New-Item -ItemType Directory -Force -Path $installRoot, $dataDir, $mediaDir, $logDir | Out-Null

Write-Step "Downloading the latest official OpenPost Windows server release"
$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/getopenpost/openpost/releases/latest' -Headers @{ 'User-Agent' = 'SocialScheduler-OpenPost-Installer' }
$asset = $release.assets | Where-Object { $_.name -eq 'openpost-server-windows-amd64.exe' } | Select-Object -First 1
if (-not $asset) {
    throw 'Latest OpenPost release does not contain openpost-server-windows-amd64.exe.'
}

$tempExe = "$serverExe.download"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tempExe -UseBasicParsing

if ($asset.digest -and $asset.digest.StartsWith('sha256:')) {
    $expected = $asset.digest.Substring(7).ToLowerInvariant()
    $actual = (Get-FileHash -Path $tempExe -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        Remove-Item $tempExe -Force -ErrorAction SilentlyContinue
        throw "OpenPost SHA256 verification failed. Expected $expected but got $actual."
    }
}
Move-Item -Force $tempExe $serverExe
Write-Host "Installed OpenPost $($release.tag_name) -> $serverExe" -ForegroundColor Green

if (-not $SkipTailscaleInstall) {
    $tailscaleExe = Get-TailscaleExe
    if (-not $tailscaleExe) {
        Write-Step "Installing Tailscale for the free public HTTPS endpoint"
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $winget) {
            throw 'winget is not installed. Install Tailscale manually, then rerun with -SkipTailscaleInstall.'
        }
        & winget install --id Tailscale.Tailscale --exact --accept-package-agreements --accept-source-agreements
        Start-Sleep -Seconds 3
    }
}

$tailscaleExe = Get-TailscaleExe
if (-not $tailscaleExe) {
    throw 'Tailscale CLI was not found. Install Tailscale, sign in once, and rerun this installer.'
}

Write-Step "Checking Tailscale authentication"
$status = $null
try {
    $status = (& $tailscaleExe status --json 2>$null | ConvertFrom-Json)
} catch {}

if (-not $status -or $status.BackendState -ne 'Running') {
    Write-Host 'Tailscale needs a one-time browser sign-in. A browser window may open now.' -ForegroundColor Yellow
    & $tailscaleExe up
    Start-Sleep -Seconds 2
    $status = (& $tailscaleExe status --json | ConvertFrom-Json)
}

if (-not $status.Self.DNSName) {
    throw 'Tailscale is connected but no MagicDNS hostname is available. Enable MagicDNS in the Tailscale admin console and rerun.'
}

$dnsName = $status.Self.DNSName.TrimEnd('.')
$publicUrl = "https://$dnsName"
Write-Host "Public OpenPost URL will be: $publicUrl" -ForegroundColor Green

$jwtSecret = New-RandomSecret
$encryptionKey = New-RandomSecret
$dbPath = (Join-Path $dataDir 'openpost.db').Replace('\', '/')
$mediaPathEscaped = $mediaDir.Replace("'", "''")
$publicUrlEscaped = $publicUrl.Replace("'", "''")

$envContent = @"
# Generated locally by SocialScheduler deploy/openpost-windows/install-openpost.ps1
# DO NOT COMMIT OR SHARE THIS FILE. It contains OpenPost encryption secrets.
`$env:OPENPOST_PORT = '8080'
`$env:OPENPOST_EDITION = 'selfhost'
`$env:OPENPOST_DATABASE_DRIVER = 'sqlite'
`$env:OPENPOST_DATABASE_PATH = 'file:$dbPath?cache=shared&mode=rwc'
`$env:OPENPOST_STORAGE_DRIVER = 'local'
`$env:OPENPOST_MEDIA_PATH = '$mediaPathEscaped'
`$env:OPENPOST_MEDIA_URL = '/media'
`$env:OPENPOST_APP_URL = '$publicUrlEscaped'
`$env:OPENPOST_PUBLIC_URL = '$publicUrlEscaped'
`$env:OPENPOST_JWT_SECRET = '$jwtSecret'
`$env:OPENPOST_ENCRYPTION_KEY = '$encryptionKey'
`$env:OPENPOST_TELEMETRY_ENABLED = 'false'
`$env:OPENPOST_EMAIL_VERIFICATION_REQUIRED = 'false'
`$env:OPENPOST_DISABLE_REGISTRATIONS = 'false'
`$env:TZ = 'Europe/Athens'
"@
Set-Content -Path $envScript -Value $envContent -Encoding UTF8

$startContent = @"
`$ErrorActionPreference = 'Stop'
`$root = '$($installRoot.Replace("'", "''"))'
`$exe = Join-Path `$root 'openpost-server.exe'
`$envScript = Join-Path `$root 'openpost.env.ps1'
`$logDir = Join-Path `$root 'logs'
. `$envScript

`$existing = Get-CimInstance Win32_Process -Filter "Name = 'openpost-server.exe'" -ErrorAction SilentlyContinue
if (`$existing) { exit 0 }

New-Item -ItemType Directory -Force -Path `$logDir | Out-Null
`$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
`$stdout = Join-Path `$logDir "openpost-`$stamp.out.log"
`$stderr = Join-Path `$logDir "openpost-`$stamp.err.log"
Start-Process -FilePath `$exe -WorkingDirectory (Join-Path `$root 'data') -WindowStyle Hidden -RedirectStandardOutput `$stdout -RedirectStandardError `$stderr
"@
Set-Content -Path $startScript -Value $startContent -Encoding UTF8

$stopContent = @"
Get-CimInstance Win32_Process -Filter "Name = 'openpost-server.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id `$_.ProcessId -Force -ErrorAction SilentlyContinue
}
"@
Set-Content -Path $stopScript -Value $stopContent -Encoding UTF8

Write-Step "Starting OpenPost locally"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $startScript
if (-not (Wait-HttpHealthy 'http://127.0.0.1:8080/api/v1/health')) {
    throw "OpenPost did not become healthy. Check $logDir for the latest .err.log file."
}
Write-Host 'OpenPost local health check: OK' -ForegroundColor Green

Write-Step "Enabling the free Tailscale Funnel HTTPS endpoint"
& $tailscaleExe funnel --bg 8080
if ($LASTEXITCODE -ne 0) {
    throw 'Tailscale Funnel could not be enabled. Follow the approval URL printed by Tailscale, then rerun this installer.'
}

$urlShortcut = @"
[InternetShortcut]
URL=$publicUrl
"@
Set-Content -Path $publicUrlFile -Value $urlShortcut -Encoding ASCII

$desktop = [Environment]::GetFolderPath('Desktop')
if ($desktop) {
    Copy-Item -Force $publicUrlFile (Join-Path $desktop 'OpenPost.url')
}

Write-Step "Configuring OpenPost to start automatically when you sign in to Windows"
$startupDir = [Environment]::GetFolderPath('Startup')
$startupCmd = Join-Path $startupDir 'OpenPost.cmd'
$startupContent = "@echo off`r`npowershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startScript`"`r`n"
Set-Content -Path $startupCmd -Value $startupContent -Encoding ASCII

Write-Step "Final verification"
$localHealthy = Wait-HttpHealthy 'http://127.0.0.1:8080/api/v1/health' 5
$publicHealthy = $false
try {
    $publicResponse = Invoke-WebRequest -Uri "$publicUrl/api/v1/health" -UseBasicParsing -TimeoutSec 15
    $publicHealthy = ($publicResponse.StatusCode -ge 200 -and $publicResponse.StatusCode -lt 500)
} catch {}

Write-Host "Local health : $localHealthy"
Write-Host "Public health: $publicHealthy"
Write-Host "OpenPost URL : $publicUrl" -ForegroundColor Green
Write-Host "Data folder  : $dataDir"
Write-Host "Logs folder  : $logDir"

if (-not $NoBrowser) {
    Start-Process $publicUrl
}

Write-Host @"

INSTALLATION COMPLETE.

Next browser steps (interactive by design):
1. Create the first LOCAL OpenPost user at $publicUrl
2. Create the SocialMarket workspace.
3. Configure/connect Facebook, Instagram, TikTok and LinkedIn provider apps/OAuth.
4. Create a workspace API token with api:write.
5. Put that token in GitHub Actions Secret OPENPOST_API_TOKEN (never paste it into chat).

The server, SQLite database, media and encryption secrets are stored only on this PC under:
$installRoot
"@ -ForegroundColor Green
