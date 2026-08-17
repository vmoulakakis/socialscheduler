param(
    [switch]$KeepData
)

$ErrorActionPreference = 'Stop'
$installRoot = Join-Path $env:LOCALAPPDATA 'OpenPost'
$startupDir = [Environment]::GetFolderPath('Startup')
$startupCmd = Join-Path $startupDir 'OpenPost.cmd'
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'OpenPost.url'

Get-CimInstance Win32_Process -Filter "Name = 'openpost-server.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

$tailscale = Get-Command tailscale.exe -ErrorAction SilentlyContinue
if (-not $tailscale -and (Test-Path "$env:ProgramFiles\Tailscale\tailscale.exe")) {
    $tailscale = Get-Item "$env:ProgramFiles\Tailscale\tailscale.exe"
}
if ($tailscale) {
    try { & $tailscale.Source funnel 8080 off | Out-Null } catch {}
}

Remove-Item $startupCmd -Force -ErrorAction SilentlyContinue
Remove-Item $desktopShortcut -Force -ErrorAction SilentlyContinue

if ($KeepData) {
    Remove-Item (Join-Path $installRoot 'openpost-server.exe') -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $installRoot 'OpenPost.url') -Force -ErrorAction SilentlyContinue
    Write-Host "OpenPost stopped and startup entry removed. Data preserved at $installRoot\data" -ForegroundColor Green
} else {
    Remove-Item $installRoot -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host 'OpenPost installation and local data removed. Tailscale itself was left installed.' -ForegroundColor Green
}
