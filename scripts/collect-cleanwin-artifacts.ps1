param(
    [ValidateSet(
        "all",
        "appx-packages",
        "provisioned-appx",
        "registry-export",
        "scheduled-tasks",
        "services",
        "package-managers",
        "dism-health"
    )]
    [string]$Mode = "all",

    [Parameter(Mandatory = $true)]
    [string]$ArtifactRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$CollectorVersion = "cleanwin-windows-native-collector-wrapper.v1"
$Manifest = [System.Collections.Generic.List[object]]::new()

function Resolve-ArtifactRoot {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "ArtifactRoot must not be empty"
    }

    $Parent = Split-Path -Parent $Path
    if ([string]::IsNullOrWhiteSpace($Parent)) {
        throw "ArtifactRoot must include a parent directory"
    }
    if (-not (Test-Path -LiteralPath $Parent -PathType Container)) {
        throw "ArtifactRoot parent directory must exist: $Parent"
    }

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $RootPath = [System.IO.Path]::GetPathRoot($FullPath)
    if ($FullPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) -eq $RootPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)) {
        throw "ArtifactRoot must not be a filesystem root"
    }

    return New-Item -ItemType Directory -Force -Path $FullPath
}

$Root = Resolve-ArtifactRoot -Path $ArtifactRoot

function New-ArtifactDirectory {
    param([string]$RelativePath)
    return New-Item -ItemType Directory -Force -Path (Join-Path $Root.FullName $RelativePath)
}

function Add-ArtifactManifestEntry {
    param(
        [string]$Id,
        [string]$RelativePath,
        [string]$Schema,
        [string]$Collector,
        [bool]$Available,
        [string]$Reason,
        [string]$Command
    )

    $FullPath = Join-Path $Root.FullName $RelativePath
    $Hash = $null
    if (Test-Path -LiteralPath $FullPath -PathType Leaf) {
        $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $FullPath).Hash
    }
    $Manifest.Add([ordered]@{
        id = $Id
        relative_path = $RelativePath
        schema = $Schema
        collector = $Collector
        available = $Available
        reason = $Reason
        sha256 = $Hash
        command = $Command
    })
}

function Write-JsonArtifact {
    param(
        [string]$Id,
        [string]$RelativePath,
        [string]$Schema,
        [string]$Collector,
        [object]$Value,
        [string]$Command
    )

    $FullPath = Join-Path $Root.FullName $RelativePath
    $Parent = Split-Path -Parent $FullPath
    if ($Parent) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }
    $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $FullPath -Encoding UTF8
    Add-ArtifactManifestEntry -Id $Id -RelativePath $RelativePath -Schema $Schema -Collector $Collector -Available $true -Reason "captured" -Command $Command
}

function Write-TextArtifact {
    param(
        [string]$Id,
        [string]$RelativePath,
        [string]$Schema,
        [string]$Collector,
        [string[]]$Lines,
        [string]$Command
    )

    $FullPath = Join-Path $Root.FullName $RelativePath
    $Parent = Split-Path -Parent $FullPath
    if ($Parent) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }
    $Lines | Set-Content -LiteralPath $FullPath -Encoding UTF8
    Add-ArtifactManifestEntry -Id $Id -RelativePath $RelativePath -Schema $Schema -Collector $Collector -Available $true -Reason "captured" -Command $Command
}

function Add-UnavailableArtifact {
    param(
        [string]$Id,
        [string]$RelativePath,
        [string]$Schema,
        [string]$Collector,
        [string]$Reason,
        [string]$Command
    )

    Add-ArtifactManifestEntry -Id $Id -RelativePath $RelativePath -Schema $Schema -Collector $Collector -Available $false -Reason $Reason -Command $Command
}

function Command-Exists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Collect-AppxPackages {
    $Command = "Get-AppxPackage -AllUsers"
    try {
        $Packages = Get-AppxPackage -AllUsers | Select-Object Name, PackageFullName, PackageFamilyName, Publisher, Version, Architecture, ResourceId, InstallLocation, IsFramework, NonRemovable, SignatureKind, Status
        Write-JsonArtifact -Id "powershell-appx-packages" -RelativePath "appx-packages.json" -Schema "cleanwin.appx-package-snapshot.v1" -Collector "powershell-appx-packages" -Value $Packages -Command $Command
    } catch {
        Add-UnavailableArtifact -Id "powershell-appx-packages" -RelativePath "appx-packages.json" -Schema "cleanwin.appx-package-snapshot.v1" -Collector "powershell-appx-packages" -Reason $_.Exception.Message -Command $Command
    }
}

function Collect-ProvisionedAppx {
    $Command = "Get-AppxProvisionedPackage -Online"
    try {
        $Packages = Get-AppxProvisionedPackage -Online | Select-Object DisplayName, PackageName, Version, Architecture, ResourceId, Regions, InstallLocation
        Write-JsonArtifact -Id "powershell-provisioned-appx" -RelativePath "provisioned-appx.json" -Schema "cleanwin.provisioned-appx-package-snapshot.v1" -Collector "powershell-provisioned-appx" -Value $Packages -Command $Command
    } catch {
        Add-UnavailableArtifact -Id "powershell-provisioned-appx" -RelativePath "provisioned-appx.json" -Schema "cleanwin.provisioned-appx-package-snapshot.v1" -Collector "powershell-provisioned-appx" -Reason $_.Exception.Message -Command $Command
    }
}

function Collect-RegistryExports {
    $RegistryDir = New-ArtifactDirectory -RelativePath "registry"
    $Exports = @(
        @{ Id = "registry-data-collection-policy"; Key = "HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection"; Path = "registry\data-collection.reg" },
        @{ Id = "registry-content-delivery-policy"; Key = "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"; Path = "registry\content-delivery-manager.reg" },
        @{ Id = "registry-explorer-advanced"; Key = "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"; Path = "registry\explorer-advanced.reg" }
    )
    foreach ($Export in $Exports) {
        $OutFile = Join-Path $Root.FullName $Export.Path
        $Command = "reg.exe export $($Export.Key) $OutFile /y"
        try {
            $Output = & reg.exe export $Export.Key $OutFile /y 2>&1
            if ($LASTEXITCODE -eq 0) {
                Add-ArtifactManifestEntry -Id $Export.Id -RelativePath $Export.Path -Schema "cleanwin.registry-export-artifact.v1" -Collector "registry-export" -Available $true -Reason "captured" -Command $Command
            } else {
                Add-ArtifactManifestEntry -Id $Export.Id -RelativePath $Export.Path -Schema "cleanwin.registry-export-artifact.v1" -Collector "registry-export" -Available $false -Reason ($Output -join "`n") -Command $Command
            }
        } catch {
            Add-ArtifactManifestEntry -Id $Export.Id -RelativePath $Export.Path -Schema "cleanwin.registry-export-artifact.v1" -Collector "registry-export" -Available $false -Reason $_.Exception.Message -Command $Command
        }
    }
    $RegistryDir | Out-Null
}

function Collect-ScheduledTasks {
    New-ArtifactDirectory -RelativePath "scheduled-tasks\xml" | Out-Null
    $CsvCommand = "schtasks.exe /Query /FO CSV /V"
    try {
        $Csv = & schtasks.exe /Query /FO CSV /V 2>&1
        Write-TextArtifact -Id "scheduled-task-csv" -RelativePath "scheduled-tasks\scheduled-tasks.csv" -Schema "cleanwin.scheduled-task-csv-artifact.v1" -Collector "scheduled-task-csv" -Lines $Csv -Command $CsvCommand
    } catch {
        Add-UnavailableArtifact -Id "scheduled-task-csv" -RelativePath "scheduled-tasks\scheduled-tasks.csv" -Schema "cleanwin.scheduled-task-csv-artifact.v1" -Collector "scheduled-task-csv" -Reason $_.Exception.Message -Command $CsvCommand
    }

    try {
        $Tasks = Get-ScheduledTask | Select-Object TaskName, TaskPath, State, Author, Description, URI, Principal, Triggers, Actions, Settings
        Write-JsonArtifact -Id "scheduled-task-json" -RelativePath "scheduled-tasks\scheduled-tasks.json" -Schema "cleanwin.scheduled-task-json-artifact.v1" -Collector "scheduled-task-json" -Value $Tasks -Command "Get-ScheduledTask"
        foreach ($Task in $Tasks) {
            $SafeName = (($Task.TaskPath.Trim("\") + "-" + $Task.TaskName) -replace '[\\/:*?"<>| ]+', "_").Trim("_")
            if (-not $SafeName) {
                $SafeName = "task"
            }
            $XmlPath = "scheduled-tasks\xml\$SafeName.xml"
            try {
                $Xml = Export-ScheduledTask -TaskName $Task.TaskName -TaskPath $Task.TaskPath
                Write-TextArtifact -Id "scheduled-task-xml-$SafeName" -RelativePath $XmlPath -Schema "cleanwin.scheduled-task-xml-artifact.v1" -Collector "scheduled-task-xml" -Lines @($Xml) -Command "Export-ScheduledTask"
            } catch {
                Add-UnavailableArtifact -Id "scheduled-task-xml-$SafeName" -RelativePath $XmlPath -Schema "cleanwin.scheduled-task-xml-artifact.v1" -Collector "scheduled-task-xml" -Reason $_.Exception.Message -Command "Export-ScheduledTask"
            }
        }
    } catch {
        Add-UnavailableArtifact -Id "scheduled-task-json" -RelativePath "scheduled-tasks\scheduled-tasks.json" -Schema "cleanwin.scheduled-task-json-artifact.v1" -Collector "scheduled-task-json" -Reason $_.Exception.Message -Command "Get-ScheduledTask"
    }
}

function Collect-Services {
    New-ArtifactDirectory -RelativePath "services\sc-qc" | Out-Null
    try {
        $Services = Get-CimInstance Win32_Service | Select-Object Name, DisplayName, State, Status, StartMode, StartName, PathName, ServiceType, ProcessId
        Write-JsonArtifact -Id "service-cim-inventory" -RelativePath "services\services.json" -Schema "cleanwin.service-inventory-artifact.v1" -Collector "service-cim-inventory" -Value $Services -Command "Get-CimInstance Win32_Service"
        foreach ($Service in $Services) {
            if (-not $Service.Name) {
                continue
            }
            $SafeName = ($Service.Name -replace '[\\/:*?"<>| ]+', "_")
            $Output = & sc.exe qc $Service.Name 2>&1
            Write-TextArtifact -Id "service-config-$SafeName" -RelativePath "services\sc-qc\$SafeName.txt" -Schema "cleanwin.service-config-artifact.v1" -Collector "service-query-config" -Lines $Output -Command "sc.exe qc <service-name>"
        }
    } catch {
        Add-UnavailableArtifact -Id "service-cim-inventory" -RelativePath "services\services.json" -Schema "cleanwin.service-inventory-artifact.v1" -Collector "service-cim-inventory" -Reason $_.Exception.Message -Command "Get-CimInstance Win32_Service"
    }
}

function Collect-PackageManagers {
    New-ArtifactDirectory -RelativePath "package-managers" | Out-Null
    if (Command-Exists "winget.exe") {
        Write-TextArtifact -Id "winget-list" -RelativePath "package-managers\winget-list.txt" -Schema "cleanwin.winget-list-artifact.v1" -Collector "winget-list" -Lines (& winget.exe list 2>&1) -Command "winget.exe list"
        $WingetExportPath = Join-Path $Root.FullName "package-managers\winget-export.json"
        $WingetExportOutput = & winget.exe export --output $WingetExportPath --accept-source-agreements 2>&1
        if (Test-Path -LiteralPath $WingetExportPath -PathType Leaf) {
            Add-ArtifactManifestEntry -Id "winget-export" -RelativePath "package-managers\winget-export.json" -Schema "cleanwin.winget-export-artifact.v1" -Collector "winget-export" -Available $true -Reason "captured" -Command "winget.exe export --output <artifact.json>"
        } else {
            Add-UnavailableArtifact -Id "winget-export" -RelativePath "package-managers\winget-export.json" -Schema "cleanwin.winget-export-artifact.v1" -Collector "winget-export" -Reason ($WingetExportOutput -join "`n") -Command "winget.exe export --output <artifact.json>"
        }
        Write-TextArtifact -Id "winget-export-log" -RelativePath "package-managers\winget-export.log" -Schema "cleanwin.command-output-log.v1" -Collector "winget-export" -Lines $WingetExportOutput -Command "winget.exe export --output <artifact.json>"
    } else {
        Add-UnavailableArtifact -Id "winget-list" -RelativePath "package-managers\winget-list.txt" -Schema "cleanwin.winget-list-artifact.v1" -Collector "winget-list" -Reason "winget.exe unavailable" -Command "winget.exe list"
        Add-UnavailableArtifact -Id "winget-export" -RelativePath "package-managers\winget-export.json" -Schema "cleanwin.winget-export-artifact.v1" -Collector "winget-export" -Reason "winget.exe unavailable" -Command "winget.exe export --output <artifact.json>"
    }

    if (Command-Exists "scoop.cmd") {
        Write-TextArtifact -Id "scoop-list" -RelativePath "package-managers\scoop-list.txt" -Schema "cleanwin.scoop-list-artifact.v1" -Collector "scoop-list" -Lines (& scoop.cmd list 2>&1) -Command "scoop.cmd list"
    } else {
        Add-UnavailableArtifact -Id "scoop-list" -RelativePath "package-managers\scoop-list.txt" -Schema "cleanwin.scoop-list-artifact.v1" -Collector "scoop-list" -Reason "scoop.cmd unavailable" -Command "scoop.cmd list"
    }

    if (Command-Exists "choco.exe") {
        Write-TextArtifact -Id "chocolatey-list" -RelativePath "package-managers\chocolatey-list.txt" -Schema "cleanwin.chocolatey-list-artifact.v1" -Collector "chocolatey-list" -Lines (& choco.exe list --local-only 2>&1) -Command "choco.exe list --local-only"
    } else {
        Add-UnavailableArtifact -Id "chocolatey-list" -RelativePath "package-managers\chocolatey-list.txt" -Schema "cleanwin.chocolatey-list-artifact.v1" -Collector "chocolatey-list" -Reason "choco.exe unavailable" -Command "choco.exe list --local-only"
    }
}

function Collect-DismHealth {
    New-ArtifactDirectory -RelativePath "dism" | Out-Null
    Write-TextArtifact -Id "dism-features" -RelativePath "dism\features.txt" -Schema "cleanwin.windows-feature-snapshot.v1" -Collector "dism-features" -Lines (& dism.exe /Online /Get-Features /Format:Table 2>&1) -Command "dism.exe /Online /Get-Features /Format:Table"
    Write-TextArtifact -Id "dism-component-store" -RelativePath "dism\component-store.txt" -Schema "cleanwin.dism-component-store-analysis.v1" -Collector "dism-component-store" -Lines (& dism.exe /Online /Cleanup-Image /AnalyzeComponentStore 2>&1) -Command "dism.exe /Online /Cleanup-Image /AnalyzeComponentStore"
    Write-TextArtifact -Id "dism-scanhealth" -RelativePath "dism\scanhealth.txt" -Schema "cleanwin.dism-health-evidence.v1" -Collector "dism-scanhealth" -Lines (& dism.exe /Online /Cleanup-Image /ScanHealth 2>&1) -Command "dism.exe /Online /Cleanup-Image /ScanHealth"
    Write-TextArtifact -Id "dism-checkhealth" -RelativePath "dism\checkhealth.txt" -Schema "cleanwin.dism-health-evidence.v1" -Collector "dism-checkhealth" -Lines (& dism.exe /Online /Cleanup-Image /CheckHealth 2>&1) -Command "dism.exe /Online /Cleanup-Image /CheckHealth"
}

function Write-Manifest {
    $ManifestPath = Join-Path $Root.FullName "manifest.json"
    $Payload = [ordered]@{
        schema = "cleanwin.windows-native-collector-manifest.v1"
        collector_version = $CollectorVersion
        generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        computer_name = $env:COMPUTERNAME
        user_name = $env:USERNAME
        is_windows = $IsWindows
        is_admin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        artifact_root = $Root.FullName
        mode = $Mode
        destructive = $false
        executes_cleanup = $false
        records = $Manifest
        summary = [ordered]@{
            record_count = $Manifest.Count
            available_count = @($Manifest | Where-Object { $_.available }).Count
            unavailable_count = @($Manifest | Where-Object { -not $_.available }).Count
        }
    }
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
    return $Payload
}

if ($Mode -eq "all" -or $Mode -eq "appx-packages") { Collect-AppxPackages }
if ($Mode -eq "all" -or $Mode -eq "provisioned-appx") { Collect-ProvisionedAppx }
if ($Mode -eq "all" -or $Mode -eq "registry-export") { Collect-RegistryExports }
if ($Mode -eq "all" -or $Mode -eq "scheduled-tasks") { Collect-ScheduledTasks }
if ($Mode -eq "all" -or $Mode -eq "services") { Collect-Services }
if ($Mode -eq "all" -or $Mode -eq "package-managers") { Collect-PackageManagers }
if ($Mode -eq "all" -or $Mode -eq "dism-health") { Collect-DismHealth }

Write-Manifest | ConvertTo-Json -Depth 8
