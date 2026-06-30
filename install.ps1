param(
    [string]$Version = "latest",
    [string]$InstallDir = "",
    [switch]$NoPathUpdate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = "imajinyun/cleanwin"
$ReleaseApi = if ($Version -eq "latest") {
    "https://api.github.com/repos/$Repo/releases/latest"
} else {
    $Tag = if ($Version.StartsWith("v", [System.StringComparison]::OrdinalIgnoreCase)) { $Version } else { "v$Version" }
    "https://api.github.com/repos/$Repo/releases/tags/$Tag"
}

function Get-ReleaseAsset {
    param(
        [object]$Release,
        [string]$Pattern
    )

    $Asset = $Release.assets | Where-Object { $_.name -like $Pattern } | Select-Object -First 1
    if ($null -eq $Asset) {
        throw "Release asset not found: $Pattern"
    }
    return $Asset
}

function Get-ExpectedSha256 {
    param([string]$ChecksumPath)

    $Content = Get-Content -LiteralPath $ChecksumPath -Raw
    if ($Content -notmatch "([A-Fa-f0-9]{64})") {
        throw "Checksum file does not contain a SHA256 digest: $ChecksumPath"
    }
    return $Matches[1].ToUpperInvariant()
}

function Add-UserPathEntry {
    param([string]$PathEntry)

    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $Parts = @()
    if (-not [string]::IsNullOrWhiteSpace($CurrentPath)) {
        $Parts = @($CurrentPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }

    $AlreadyPresent = $false
    foreach ($Part in $Parts) {
        if ($Part.TrimEnd("\") -ieq $PathEntry.TrimEnd("\")) {
            $AlreadyPresent = $true
            break
        }
    }

    if (-not $AlreadyPresent) {
        $NewPath = (@($Parts) + $PathEntry) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
        $env:Path = (@($env:Path -split ";" | Where-Object { $_ }) + $PathEntry) -join ";"
    }
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw "LOCALAPPDATA is not set; pass -InstallDir explicitly."
    }
    $InstallDir = Join-Path $env:LOCALAPPDATA "Programs\cleanwin"
}

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$ParentDir = Split-Path -Parent $InstallDir
if ([string]::IsNullOrWhiteSpace($ParentDir)) {
    throw "InstallDir must include a parent directory."
}
$RootDir = [System.IO.Path]::GetPathRoot($InstallDir)
if ($InstallDir.TrimEnd("\", "/") -eq $RootDir.TrimEnd("\", "/")) {
    throw "InstallDir must not be a filesystem root."
}

Write-Host "Resolving cleanwin release metadata..."
$Release = Invoke-RestMethod -Uri $ReleaseApi -Headers @{ "User-Agent" = "cleanwin-installer" }
$ArchiveAsset = Get-ReleaseAsset -Release $Release -Pattern "cleanwin-*-windows-x64.zip"
$ChecksumAsset = Get-ReleaseAsset -Release $Release -Pattern "$($ArchiveAsset.name).sha256"

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("cleanwin-install-" + [System.Guid]::NewGuid().ToString())
$ArchivePath = Join-Path $TempRoot $ArchiveAsset.name
$ChecksumPath = Join-Path $TempRoot $ChecksumAsset.name
$ExtractDir = Join-Path $TempRoot "extract"

try {
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null

    Write-Host "Downloading $($ArchiveAsset.name)..."
    Invoke-WebRequest -Uri $ArchiveAsset.browser_download_url -OutFile $ArchivePath -Headers @{ "User-Agent" = "cleanwin-installer" }
    Invoke-WebRequest -Uri $ChecksumAsset.browser_download_url -OutFile $ChecksumPath -Headers @{ "User-Agent" = "cleanwin-installer" }

    $ExpectedSha256 = Get-ExpectedSha256 -ChecksumPath $ChecksumPath
    $ActualSha256 = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($ActualSha256 -ne $ExpectedSha256) {
        throw "SHA256 mismatch for $($ArchiveAsset.name): expected $ExpectedSha256, got $ActualSha256"
    }

    Write-Host "Installing to $InstallDir..."
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractDir -Force
    if (-not (Test-Path -LiteralPath (Join-Path $ExtractDir "cleanwin.exe") -PathType Leaf)) {
        throw "Archive is missing cleanwin.exe"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $ExtractDir "cleanwin-mcp.exe") -PathType Leaf)) {
        throw "Archive is missing cleanwin-mcp.exe"
    }

    New-Item -ItemType Directory -Force -Path $ParentDir | Out-Null
    if (Test-Path -LiteralPath $InstallDir) {
        $ExistingItems = @(Get-ChildItem -LiteralPath $InstallDir -Force)
        $ExistingCleanwinExe = Test-Path -LiteralPath (Join-Path $InstallDir "cleanwin.exe") -PathType Leaf
        $ExistingMcpExe = Test-Path -LiteralPath (Join-Path $InstallDir "cleanwin-mcp.exe") -PathType Leaf
        if ($ExistingItems.Count -gt 0 -and -not ($ExistingCleanwinExe -and $ExistingMcpExe)) {
            throw "Refusing to replace non-empty directory that does not look like a cleanwin install: $InstallDir"
        }
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }
    Move-Item -LiteralPath $ExtractDir -Destination $InstallDir

    if (-not $NoPathUpdate) {
        Add-UserPathEntry -PathEntry $InstallDir
    }

    Write-Host "Verifying cleanwin..."
    $Doctor = & (Join-Path $InstallDir "cleanwin.exe") --json doctor | ConvertFrom-Json
    if (-not $Doctor.ready) {
        throw "cleanwin doctor reported not ready after installation."
    }

    Write-Host "cleanwin installed successfully."
    Write-Host "Version: $($Release.tag_name)"
    Write-Host "Path: $InstallDir"
    Write-Host "Try: cleanwin --json inspect --categories temp,dev-cache --max-items 10"
    if (-not $NoPathUpdate) {
        Write-Host "Restart your terminal if the cleanwin command is not found in existing sessions."
    }
}
finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
