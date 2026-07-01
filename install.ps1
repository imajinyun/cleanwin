param(
    [string]$Version = "latest",
    [string]$InstallDir = "",
    [switch]$NoPathUpdate,
    [switch]$Uninstall,
    [switch]$Force
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
        return $true
    }
    return $false
}

function Remove-UserPathEntry {
    param([string]$PathEntry)

    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($CurrentPath)) {
        return $false
    }
    $Parts = @($CurrentPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $NewParts = @($Parts | Where-Object { $_.TrimEnd("\") -ine $PathEntry.TrimEnd("\") })
    if ($NewParts.Count -eq $Parts.Count) {
        return $false
    }
    $NewPath = $NewParts -join ";"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    $env:Path = (@($env:Path -split ";" | Where-Object { $_ -and $_.TrimEnd("\") -ine $PathEntry.TrimEnd("\") }) -join ";")
    return $true
}

function Get-InstalledVersion {
    param([string]$Dir)

    $Exe = Join-Path $Dir "cleanwin.exe"
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
        return $null
    }
    try {
        $Info = & $Exe --json doctor 2>$null | ConvertFrom-Json
        if ($null -ne $Info -and $null -ne $Info.version) {
            return $Info.version
        }
    } catch {
    }
    return $null
}

function Resolve-InstallDir {
    param([string]$Dir)

    if ([string]::IsNullOrWhiteSpace($Dir)) {
        if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            throw "LOCALAPPDATA is not set; pass -InstallDir explicitly."
        }
        $Dir = Join-Path $env:LOCALAPPDATA "Programs\cleanwin"
    }

    $Dir = [System.IO.Path]::GetFullPath($Dir)
    $ParentDir = Split-Path -Parent $Dir
    if ([string]::IsNullOrWhiteSpace($ParentDir)) {
        throw "InstallDir must include a parent directory."
    }
    $RootDir = [System.IO.Path]::GetPathRoot($Dir)
    if ($Dir.TrimEnd("\", "/") -eq $RootDir.TrimEnd("\", "/")) {
        throw "InstallDir must not be a filesystem root."
    }
    return $Dir
}

function Invoke-Uninstall {
    param([string]$Dir)

    if (-not (Test-Path -LiteralPath $Dir)) {
        Write-Host "cleanwin is not installed at $Dir"
        return
    }

    $HasCleanwin = Test-Path -LiteralPath (Join-Path $Dir "cleanwin.exe") -PathType Leaf
    $HasMcp = Test-Path -LiteralPath (Join-Path $Dir "cleanwin-mcp.exe") -PathType Leaf
    if (-not ($HasCleanwin -or $HasMcp)) {
        if (-not $Force) {
            throw "Refusing to remove directory that does not look like a cleanwin install: $Dir`nUse -Force to override."
        }
    }

    $RemovedFromPath = $false
    if (-not $NoPathUpdate) {
        $RemovedFromPath = Remove-UserPathEntry -PathEntry $Dir
    }

    Write-Host "Uninstalling cleanwin from $Dir..."
    Remove-Item -LiteralPath $Dir -Recurse -Force

    Write-Host "cleanwin uninstalled."
    if ($RemovedFromPath) {
        Write-Host "Removed from user PATH. Restart your terminal for changes to take effect in existing sessions."
    }
}

$InstallDir = Resolve-InstallDir -Dir $InstallDir

if ($Uninstall) {
    Invoke-Uninstall -Dir $InstallDir
    exit 0
}

Write-Host "Resolving cleanwin release metadata..."
$Release = Invoke-RestMethod -Uri $ReleaseApi -Headers @{ "User-Agent" = "cleanwin-installer" }
$TargetVersion = $Release.tag_name
$ArchiveAsset = Get-ReleaseAsset -Release $Release -Pattern "cleanwin-*-windows-x64.zip"
$ChecksumAsset = Get-ReleaseAsset -Release $Release -Pattern "$($ArchiveAsset.name).sha256"

$ExistingVersion = Get-InstalledVersion -Dir $InstallDir
if ($null -ne $ExistingVersion -and -not $Force) {
    $ExistingTag = if ($ExistingVersion.StartsWith("v", [System.StringComparison]::OrdinalIgnoreCase)) { $ExistingVersion } else { "v$ExistingVersion" }
    if ($ExistingTag -ieq $TargetVersion) {
        Write-Host "cleanwin $TargetVersion is already installed at $InstallDir"
        if (-not $NoPathUpdate) {
            $null = Add-UserPathEntry -PathEntry $InstallDir
        }
        Write-Host "Try: cleanwin --json inspect --categories temp,dev-cache --max-items 10"
        exit 0
    }
    Write-Host "Upgrading cleanwin from $ExistingTag to $TargetVersion..."
}

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

    $ParentDir = Split-Path -Parent $InstallDir
    New-Item -ItemType Directory -Force -Path $ParentDir | Out-Null

    $BackupDir = ""
    $RollbackNeeded = $false
    if (Test-Path -LiteralPath $InstallDir) {
        $ExistingItems = @(Get-ChildItem -LiteralPath $InstallDir -Force)
        $ExistingCleanwinExe = Test-Path -LiteralPath (Join-Path $InstallDir "cleanwin.exe") -PathType Leaf
        $ExistingMcpExe = Test-Path -LiteralPath (Join-Path $InstallDir "cleanwin-mcp.exe") -PathType Leaf
        if ($ExistingItems.Count -gt 0 -and -not ($ExistingCleanwinExe -and $ExistingMcpExe)) {
            throw "Refusing to replace non-empty directory that does not look like a cleanwin install: $InstallDir"
        }
        $BackupDir = Join-Path $ParentDir ("cleanwin.backup-" + [System.Guid]::NewGuid().ToString("N"))
        Move-Item -LiteralPath $InstallDir -Destination $BackupDir
        $RollbackNeeded = $true
    }

    try {
        Move-Item -LiteralPath $ExtractDir -Destination $InstallDir

        $PathAdded = $false
        if (-not $NoPathUpdate) {
            $PathAdded = Add-UserPathEntry -PathEntry $InstallDir
        }

        Write-Host "Verifying cleanwin..."
        $Doctor = & (Join-Path $InstallDir "cleanwin.exe") --json doctor | ConvertFrom-Json
        if (-not $Doctor.ready) {
            throw "cleanwin doctor reported not ready after installation."
        }

        if ($RollbackNeeded -and (Test-Path -LiteralPath $BackupDir)) {
            Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    } catch {
        if ($RollbackNeeded -and (Test-Path -LiteralPath $BackupDir)) {
            Write-Host "Rolling back to previous installation..."
            if (Test-Path -LiteralPath $InstallDir) {
                Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
            }
            Move-Item -LiteralPath $BackupDir -Destination $InstallDir -ErrorAction SilentlyContinue
            Write-Host "Rollback complete."
        }
        throw
    }

    $Action = if ($null -ne $ExistingVersion) { "upgraded to" } else { "installed successfully" }
    Write-Host "cleanwin $Action."
    Write-Host "Version: $TargetVersion"
    Write-Host "Path: $InstallDir"
    Write-Host "Try: cleanwin --json inspect --categories temp,dev-cache --max-items 10"
    if ($PathAdded) {
        Write-Host "Added to user PATH. Restart your terminal for changes to take effect in existing sessions."
    }
}
finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
