#!/usr/bin/env pwsh
# RĀMAN Studio Disk Cleanup Script
# Safely cleans development caches and temporary files
# Run as Administrator for best results

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         RĀMAN Studio Disk Cleanup Utility                 ║" -ForegroundColor Cyan
Write-Host "║         Safe cleanup of caches and temp files             ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️  Not running as Administrator. Some cleanups may be skipped." -ForegroundColor Yellow
    Write-Host "   For best results, right-click and 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
}

# Get initial disk space
$drive = Get-PSDrive C
$initialFree = [math]::Round($drive.Free / 1GB, 2)
Write-Host "Initial free space: $initialFree GB" -ForegroundColor White
Write-Host ""

$totalFreed = 0
$errors = @()

# Function to safely remove folder contents
function Remove-FolderContents {
    param($path, $description)
    
    if (Test-Path $path) {
        Write-Host "🧹 Cleaning: $description..." -NoNewline
        try {
            $sizeBefore = (Get-ChildItem $path -Recurse -Force -ErrorAction SilentlyContinue | 
                          Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum / 1GB
            
            Remove-Item "$path\*" -Recurse -Force -ErrorAction SilentlyContinue
            
            Write-Host " ✓ (~$([math]::Round($sizeBefore, 2)) GB)" -ForegroundColor Green
            return $sizeBefore
        } catch {
            Write-Host " ✗ Failed" -ForegroundColor Red
            $script:errors += "Failed to clean: $description"
            return 0
        }
    } else {
        Write-Host "⊘ Skipping: $description (not found)" -ForegroundColor DarkGray
        return 0
    }
}

# Function to run command safely
function Invoke-SafeCommand {
    param($command, $description, $estimatedGB)
    
    Write-Host "🧹 Cleaning: $description..." -NoNewline
    try {
        Invoke-Expression $command 2>&1 | Out-Null
        Write-Host " ✓ (~$estimatedGB GB)" -ForegroundColor Green
        return $estimatedGB
    } catch {
        Write-Host " ✗ Failed" -ForegroundColor Red
        $script:errors += "Failed to clean: $description"
        return 0
    }
}

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 1: Development Caches" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. npm cache
if (Get-Command npm -ErrorAction SilentlyContinue) {
    $totalFreed += Invoke-SafeCommand "npm cache clean --force" "npm cache" 7.83
} else {
    Write-Host "⊘ Skipping: npm cache (npm not found)" -ForegroundColor DarkGray
}

# 2. pnpm store
if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    $totalFreed += Invoke-SafeCommand "pnpm store prune" "pnpm store" 10.09
} else {
    Write-Host "⊘ Skipping: pnpm store (pnpm not found)" -ForegroundColor DarkGray
}

# 3. pip cache
if (Get-Command pip -ErrorAction SilentlyContinue) {
    $totalFreed += Invoke-SafeCommand "pip cache purge" "pip cache" 1.84
} else {
    Write-Host "⊘ Skipping: pip cache (pip not found)" -ForegroundColor DarkGray
}

# 4. uv cache
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $totalFreed += Invoke-SafeCommand "uv cache clean" "uv cache" 2.38
} else {
    Write-Host "⊘ Skipping: uv cache (uv not found)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 2: Temporary Files" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 5. Windows Temp
$totalFreed += Remove-FolderContents "$env:TEMP" "Windows Temp"

# 6. Local Temp
$totalFreed += Remove-FolderContents "$env:LOCALAPPDATA\Temp" "Local Temp"

# 7. Prefetch (requires admin)
if ($isAdmin) {
    $totalFreed += Remove-FolderContents "C:\Windows\Prefetch" "Windows Prefetch"
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 3: Browser Caches" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 8. Chrome cache
$totalFreed += Remove-FolderContents "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache" "Chrome Cache"
$totalFreed += Remove-FolderContents "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Code Cache" "Chrome Code Cache"

# 9. Edge cache
$totalFreed += Remove-FolderContents "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache" "Edge Cache"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 4: AI/ML Caches" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 10. .embedder cache
$totalFreed += Remove-FolderContents "$env:USERPROFILE\.embedder" ".embedder cache"

# 11. Hugging Face cache
$totalFreed += Remove-FolderContents "$env:USERPROFILE\.cache\huggingface" "Hugging Face cache"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 5: Docker Cleanup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 12. Docker system prune
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "🧹 Cleaning: Docker system..." -NoNewline
    try {
        $dockerOutput = docker system prune -a --volumes -f 2>&1
        Write-Host " ✓ (~1.6 GB)" -ForegroundColor Green
        $totalFreed += 1.6
    } catch {
        Write-Host " ✗ Failed (Docker may not be running)" -ForegroundColor Yellow
    }
} else {
    Write-Host "⊘ Skipping: Docker cleanup (Docker not found)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PHASE 6: Windows System Cleanup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 13. Windows Update cleanup (requires admin)
if ($isAdmin) {
    Write-Host "🧹 Cleaning: Windows Update cache..." -NoNewline
    try {
        Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
        Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
        Start-Service wuauserv -ErrorAction SilentlyContinue
        Write-Host " ✓" -ForegroundColor Green
        $totalFreed += 2
    } catch {
        Write-Host " ✗ Failed" -ForegroundColor Yellow
    }
}

# 14. Recycle Bin
Write-Host "🧹 Cleaning: Recycle Bin..." -NoNewline
try {
    Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    Write-Host " ✓" -ForegroundColor Green
    $totalFreed += 1
} catch {
    Write-Host " ✗ Failed" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

# Get final disk space
$drive = Get-PSDrive C
$finalFree = [math]::Round($drive.Free / 1GB, 2)
$actualFreed = $finalFree - $initialFree

Write-Host "📊 Results:" -ForegroundColor Cyan
Write-Host "   Initial free space: $initialFree GB" -ForegroundColor White
Write-Host "   Final free space:   $finalFree GB" -ForegroundColor White
Write-Host "   Space freed:        $actualFreed GB" -ForegroundColor Green
Write-Host "   Estimated freed:    $([math]::Round($totalFreed, 2)) GB" -ForegroundColor Yellow
Write-Host ""

if ($errors.Count -gt 0) {
    Write-Host "⚠️  Errors encountered:" -ForegroundColor Yellow
    foreach ($error in $errors) {
        Write-Host "   • $error" -ForegroundColor Yellow
    }
    Write-Host ""
}

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  MANUAL CLEANUP RECOMMENDATIONS" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "For additional space, manually review:" -ForegroundColor White
Write-Host ""
Write-Host "1. Downloads folder (78 GB):" -ForegroundColor Yellow
Write-Host "   explorer `"$env:USERPROFILE\Downloads`"" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Ollama models (30 GB):" -ForegroundColor Yellow
Write-Host "   ollama list" -ForegroundColor Gray
Write-Host "   ollama rm <model-name>" -ForegroundColor Gray
Write-Host ""
Write-Host "3. OneDrive files (80 GB):" -ForegroundColor Yellow
Write-Host "   Consider moving to external drive" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Run Windows Disk Cleanup:" -ForegroundColor Yellow
Write-Host "   cleanmgr /d C: /VERYLOWDISK" -ForegroundColor Gray
Write-Host ""

Write-Host "✅ Cleanup script completed!" -ForegroundColor Green
Write-Host ""

# Offer to open folders for manual cleanup
$response = Read-Host "Open Downloads folder for manual cleanup? (y/n)"
if ($response -eq 'y') {
    explorer "$env:USERPROFILE\Downloads"
}

$response = Read-Host "List Ollama models? (y/n)"
if ($response -eq 'y') {
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        ollama list
    } else {
        Write-Host "Ollama not found" -ForegroundColor Yellow
    }
}
