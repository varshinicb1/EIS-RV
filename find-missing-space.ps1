#!/usr/bin/env pwsh
# Find Missing Disk Space Script
# This will identify where the remaining ~550 GB is located

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Red
Write-Host "║         FINDING MISSING DISK SPACE (~550 GB)                    ║" -ForegroundColor Red
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Red
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️  Not running as Administrator." -ForegroundColor Yellow
    Write-Host "   Some system folders may not be accessible." -ForegroundColor Yellow
    Write-Host "   For complete scan, right-click and 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "This will scan your entire C: drive. It may take 10-30 minutes." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to cancel at any time." -ForegroundColor Yellow
Write-Host ""
$response = Read-Host "Continue? (y/n)"
if ($response -ne 'y') {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 1: Scanning Root Folders" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Function to get folder size with progress
function Get-FolderSizeWithProgress {
    param($path, $name)
    
    Write-Host "📁 Scanning: $name..." -NoNewline
    $startTime = Get-Date
    
    try {
        $size = (Get-ChildItem $path -Recurse -File -Force -ErrorAction SilentlyContinue | 
                Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
        
        $sizeGB = [math]::Round($size / 1GB, 2)
        $elapsed = ((Get-Date) - $startTime).TotalSeconds
        
        Write-Host " $sizeGB GB " -NoNewline -ForegroundColor $(if($sizeGB -gt 100){'Red'}elseif($sizeGB -gt 50){'Yellow'}else{'Green'})
        Write-Host "($([math]::Round($elapsed, 1))s)" -ForegroundColor DarkGray
        
        return [PSCustomObject]@{
            Name = $name
            Path = $path
            SizeGB = $sizeGB
            Time = $elapsed
        }
    } catch {
        Write-Host " Error" -ForegroundColor Red
        return $null
    }
}

$results = @()

# Scan major folders
$foldersToScan = @(
    @{Path="C:\Windows"; Name="Windows"},
    @{Path="C:\Program Files"; Name="Program Files"},
    @{Path="C:\Program Files (x86)"; Name="Program Files (x86)"},
    @{Path="C:\ProgramData"; Name="ProgramData"},
    @{Path="C:\Users\varsh\Documents"; Name="Documents"},
    @{Path="C:\Users\varsh\Downloads"; Name="Downloads"},
    @{Path="C:\Users\varsh\OneDrive"; Name="OneDrive"},
    @{Path="C:\Users\varsh\AppData"; Name="AppData"},
    @{Path="C:\Users\varsh\Videos"; Name="Videos"},
    @{Path="C:\Users\varsh\Pictures"; Name="Pictures"},
    @{Path="C:\Users\varsh\Music"; Name="Music"},
    @{Path="C:\Users\varsh\Desktop"; Name="Desktop"},
    @{Path="C:\Users\varsh\.ollama"; Name=".ollama"},
    @{Path="C:\Users\varsh\.embedder"; Name=".embedder"},
    @{Path="C:\Users\varsh\.vscode"; Name=".vscode"},
    @{Path="C:\Users\varsh\.cursor"; Name=".cursor"},
    @{Path="C:\Users\varsh\.docker"; Name=".docker"},
    @{Path="C:\Users\varsh\.android"; Name=".android"},
    @{Path="C:\Users\varsh\.gradle"; Name=".gradle"},
    @{Path="C:\Users\varsh\.m2"; Name=".m2"},
    @{Path="C:\Users\varsh\.nuget"; Name=".nuget"}
)

foreach ($folder in $foldersToScan) {
    if (Test-Path $folder.Path) {
        $result = Get-FolderSizeWithProgress -path $folder.Path -name $folder.Name
        if ($result) {
            $results += $result
        }
    } else {
        Write-Host "⊘ Skipping: $($folder.Name) (not found)" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 2: Checking for Hidden/System Folders" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check for common hidden folders
$hiddenFolders = @(
    @{Path="C:\`$Recycle.Bin"; Name="Recycle Bin"},
    @{Path="C:\System Volume Information"; Name="System Volume Information"},
    @{Path="C:\pagefile.sys"; Name="Page File"},
    @{Path="C:\hiberfil.sys"; Name="Hibernation File"},
    @{Path="C:\swapfile.sys"; Name="Swap File"},
    @{Path="C:\Windows.old"; Name="Windows.old"},
    @{Path="C:\`$Windows.~BT"; Name="Windows Update Cache"},
    @{Path="C:\`$Windows.~WS"; Name="Windows Setup Files"}
)

foreach ($folder in $hiddenFolders) {
    if (Test-Path $folder.Path) {
        if ((Get-Item $folder.Path -Force).PSIsContainer) {
            $result = Get-FolderSizeWithProgress -path $folder.Path -name $folder.Name
            if ($result) {
                $results += $result
            }
        } else {
            # It's a file
            $size = (Get-Item $folder.Path -Force).Length / 1GB
            $sizeGB = [math]::Round($size, 2)
            Write-Host "📄 $($folder.Name): $sizeGB GB" -ForegroundColor $(if($sizeGB -gt 10){'Yellow'}else{'White'})
            $results += [PSCustomObject]@{
                Name = $folder.Name
                Path = $folder.Path
                SizeGB = $sizeGB
                Time = 0
            }
        }
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 3: Checking Other Root Folders" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Get all other root folders we haven't scanned yet
$scannedPaths = $results | ForEach-Object { $_.Path }
$allRootFolders = Get-ChildItem C:\ -Directory -Force -ErrorAction SilentlyContinue | 
                  Where-Object { $_.FullName -notin $scannedPaths -and $_.Name -notmatch '^\$' }

foreach ($folder in $allRootFolders) {
    $result = Get-FolderSizeWithProgress -path $folder.FullName -name $folder.Name
    if ($result) {
        $results += $result
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  SCAN COMPLETE - RESULTS" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Sort and display results
$sortedResults = $results | Sort-Object SizeGB -Descending

Write-Host "Top 20 Space Consumers:" -ForegroundColor Cyan
Write-Host ""
$sortedResults | Select-Object -First 20 | Format-Table Name, @{Label="Size (GB)"; Expression={$_.SizeGB}; FormatString="N2"}, @{Label="Scan Time (s)"; Expression={$_.Time}; FormatString="N1"} -AutoSize

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  SUMMARY" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$totalScanned = ($results | Measure-Object -Property SizeGB -Sum).Sum
$driveUsed = 947.51
$missing = $driveUsed - $totalScanned

Write-Host "Total scanned:        $([math]::Round($totalScanned, 2)) GB" -ForegroundColor White
Write-Host "Drive used:           $driveUsed GB" -ForegroundColor White
Write-Host "Unaccounted for:      $([math]::Round($missing, 2)) GB" -ForegroundColor $(if($missing -gt 100){'Red'}elseif($missing -gt 50){'Yellow'}else{'Green'})
Write-Host ""

if ($missing -gt 50) {
    Write-Host "⚠️  Large amount of unaccounted space detected!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Possible reasons:" -ForegroundColor Yellow
    Write-Host "  • System restore points" -ForegroundColor White
    Write-Host "  • Windows Update files" -ForegroundColor White
    Write-Host "  • Virtual memory (pagefile.sys)" -ForegroundColor White
    Write-Host "  • Hibernation file (hiberfil.sys)" -ForegroundColor White
    Write-Host "  • Shadow copies / VSS" -ForegroundColor White
    Write-Host "  • Folders requiring admin access" -ForegroundColor White
    Write-Host ""
    Write-Host "To investigate further:" -ForegroundColor Cyan
    Write-Host "  1. Run this script as Administrator" -ForegroundColor White
    Write-Host "  2. Check System Restore: sysdm.cpl → System Protection" -ForegroundColor White
    Write-Host "  3. Check Windows Update: C:\Windows\SoftwareDistribution" -ForegroundColor White
    Write-Host "  4. Use WinDirStat or TreeSize for visual analysis" -ForegroundColor White
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  RECOMMENDATIONS" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Provide recommendations based on findings
$largestFolders = $sortedResults | Select-Object -First 5

foreach ($folder in $largestFolders) {
    if ($folder.SizeGB -gt 50) {
        Write-Host "📁 $($folder.Name): $($folder.SizeGB) GB" -ForegroundColor Yellow
        
        switch ($folder.Name) {
            "Windows" {
                Write-Host "   → Run Disk Cleanup: cleanmgr /d C:" -ForegroundColor White
                Write-Host "   → Check Windows.old folder" -ForegroundColor White
            }
            "Downloads" {
                Write-Host "   → Manually review and delete old files" -ForegroundColor White
                Write-Host "   → Move large files to external drive" -ForegroundColor White
            }
            "OneDrive" {
                Write-Host "   → Enable Files On-Demand" -ForegroundColor White
                Write-Host "   → Move to external drive" -ForegroundColor White
            }
            "AppData" {
                Write-Host "   → Already cleaned caches" -ForegroundColor Green
                Write-Host "   → Check for large application data" -ForegroundColor White
            }
            ".ollama" {
                Write-Host "   → Remove unused models: ollama rm <model>" -ForegroundColor White
            }
            "Program Files" {
                Write-Host "   → Uninstall unused applications" -ForegroundColor White
            }
            default {
                Write-Host "   → Review contents manually" -ForegroundColor White
            }
        }
        Write-Host ""
    }
}

Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Export results to CSV
$exportPath = "disk-space-analysis.csv"
$results | Export-Csv -Path $exportPath -NoTypeInformation
Write-Host "✅ Results exported to: $exportPath" -ForegroundColor Green
Write-Host ""

# Offer to open large folders
$response = Read-Host "Open largest folder in Explorer? (y/n)"
if ($response -eq 'y' -and $largestFolders.Count -gt 0) {
    explorer $largestFolders[0].Path
}
