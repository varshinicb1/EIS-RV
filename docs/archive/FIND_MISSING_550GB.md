# 🔍 Finding the Missing 550 GB

**Current Status:**
- Drive size: 953 GB
- Used: 947.51 GB
- Free: 5.41 GB
- **Accounted for: ~400 GB**
- **Missing: ~550 GB** ❓

---

## 📊 What We Know (400 GB Accounted)

| Location | Size | Status |
|----------|------|--------|
| AppData | 178 GB | Cleaned to 136 GB |
| OneDrive | 80 GB | Needs manual review |
| Downloads | 79 GB | Needs manual cleanup |
| .ollama | 31 GB | Remove unused models |
| .embedder | 18 GB | Cleaned |
| **Subtotal** | **~386 GB** | |

---

## 🎯 Where is the Missing 550 GB?

### Most Likely Culprits:

### 1. **Windows Folder** (100-200 GB possible)
- **C:\Windows\WinSxS** - Component store (can be 20-50 GB)
- **C:\Windows\Installer** - MSI installers (can be 10-30 GB)
- **C:\Windows\SoftwareDistribution** - Windows Update (can be 10-20 GB)
- **C:\Windows.old** - Previous Windows installation (can be 20-50 GB)
- **C:\Windows\Temp** - Temporary files

**Check:**
```powershell
# Run as Administrator
Get-ChildItem C:\Windows -Directory | ForEach-Object {
    $size = (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
    [PSCustomObject]@{Folder=$_.Name; SizeGB=[math]::Round($size,2)}
} | Sort-Object SizeGB -Descending | Select-Object -First 10
```

---

### 2. **Program Files** (50-100 GB possible)
- **C:\Program Files** - 64-bit applications
- **C:\Program Files (x86)** - 32-bit applications

**Check:**
```powershell
Get-ChildItem "C:\Program Files" -Directory | ForEach-Object {
    $size = (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
    [PSCustomObject]@{App=$_.Name; SizeGB=[math]::Round($size,2)}
} | Where-Object {$_.SizeGB -gt 1} | Sort-Object SizeGB -Descending
```

---

### 3. **ProgramData** (20-50 GB possible)
- Hidden folder containing application data
- Can contain large caches and databases

**Check:**
```powershell
Get-ChildItem "C:\ProgramData" -Directory -Force | ForEach-Object {
    $size = (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
    [PSCustomObject]@{Folder=$_.Name; SizeGB=[math]::Round($size,2)}
} | Where-Object {$_.SizeGB -gt 1} | Sort-Object SizeGB -Descending
```

---

### 4. **System Files** (20-40 GB possible)
- **pagefile.sys** - Virtual memory (usually 16-32 GB)
- **hiberfil.sys** - Hibernation file (usually 8-16 GB)
- **swapfile.sys** - Swap file (usually 256 MB - 2 GB)

**Check:**
```powershell
# Run as Administrator
Get-ChildItem C:\ -File -Force -ErrorAction SilentlyContinue | 
    Where-Object {$_.Name -match 'sys$'} | 
    Select-Object Name, @{Name="SizeGB";Expression={[math]::Round($_.Length/1GB,2)}}
```

---

### 5. **System Restore / Shadow Copies** (50-100 GB possible)
- System restore points
- Volume Shadow Copies (VSS)
- Previous versions of files

**Check:**
```powershell
# Check System Restore usage
vssadmin list shadowstorage

# Or use GUI
# Control Panel → System → System Protection
```

---

### 6. **Virtual Machines / Docker** (50-200 GB possible)
- **C:\Users\varsh\.docker** - Docker images and containers
- **C:\Users\varsh\VirtualBox VMs** - VirtualBox VMs
- **C:\Users\varsh\Documents\Virtual Machines** - VMware VMs
- **C:\ProgramData\Docker** - Docker data

**Check:**
```powershell
# Docker
docker system df

# Check VM folders
Get-ChildItem "C:\Users\varsh" -Directory | Where-Object {$_.Name -match 'virtual|vm|docker'}
```

---

### 7. **Development Tools** (20-50 GB possible)
- **C:\Users\varsh\.gradle** - Gradle cache
- **C:\Users\varsh\.m2** - Maven repository
- **C:\Users\varsh\.nuget** - NuGet packages
- **C:\Users\varsh\.android** - Android SDK
- **C:\Users\varsh\.vscode** - VS Code extensions
- **C:\Users\varsh\.cursor** - Cursor extensions

---

### 8. **Hidden User Folders** (50-100 GB possible)
- **C:\Users\varsh\Videos** - Video files
- **C:\Users\varsh\Pictures** - Photos
- **C:\Users\varsh\Music** - Music files
- **C:\Users\varsh\3D Objects** - 3D models
- **C:\Users\varsh\Saved Games** - Game saves

---

## 🚀 How to Find It

### Method 1: Use the Script (Recommended)
```powershell
# Run as Administrator for best results
cd EIS-RV
.\find-missing-space.ps1
```

This will:
- Scan all major folders
- Check hidden/system folders
- Generate a report
- Export results to CSV

**Time:** 10-30 minutes

---

### Method 2: Use WinDirStat (Visual)
1. Download: https://windirstat.net/
2. Install and run as Administrator
3. Select C: drive
4. Wait for scan (10-20 minutes)
5. See visual treemap of disk usage

**Best for:** Visual analysis

---

### Method 3: Use TreeSize Free (Fast)
1. Download: https://www.jam-software.com/treesize_free
2. Install and run as Administrator
3. Select C: drive
4. Instant results with drill-down

**Best for:** Quick analysis

---

### Method 4: Use Windows Storage Sense
1. Press Win + I (Settings)
2. Go to System → Storage
3. Click "Show more categories"
4. Review each category

**Best for:** Quick overview

---

### Method 5: Manual PowerShell Scan
```powershell
# Run as Administrator
Write-Host "Scanning C:\ folders..." -ForegroundColor Cyan

Get-ChildItem C:\ -Directory -Force -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -notmatch '^\$' } | 
    ForEach-Object {
        $name = $_.Name
        Write-Host "Scanning: $name..." -NoNewline
        $size = (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | 
                Measure-Object -Property Length -Sum).Sum / 1GB
        $sizeGB = [math]::Round($size, 2)
        Write-Host " $sizeGB GB"
        [PSCustomObject]@{Folder=$name; SizeGB=$sizeGB}
    } | Sort-Object SizeGB -Descending | Format-Table -AutoSize
```

---

## 🎯 Quick Checks (Do These First)

### 1. Check Windows.old (Previous Windows Installation)
```powershell
if (Test-Path "C:\Windows.old") {
    $size = (Get-ChildItem "C:\Windows.old" -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
    Write-Host "Windows.old: $([math]::Round($size, 2)) GB"
    Write-Host "To remove: cleanmgr /d C: → Select 'Previous Windows installations'"
}
```

### 2. Check System Restore
```powershell
# Run as Administrator
vssadmin list shadowstorage

# To reduce:
# Control Panel → System → System Protection → Configure → Reduce space
```

### 3. Check Windows Update Cache
```powershell
$size = (Get-ChildItem "C:\Windows\SoftwareDistribution" -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
Write-Host "Windows Update cache: $([math]::Round($size, 2)) GB"

# To clean:
# Stop-Service wuauserv
# Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force
# Start-Service wuauserv
```

### 4. Check WinSxS (Component Store)
```powershell
# Run as Administrator
Dism.exe /Online /Cleanup-Image /AnalyzeComponentStore

# To clean:
# Dism.exe /Online /Cleanup-Image /StartComponentCleanup /ResetBase
```

### 5. Check Docker
```powershell
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker system df
    # To clean: docker system prune -a --volumes
}
```

---

## 📊 Expected Findings

Based on typical Windows installations, the missing 550 GB is likely:

| Location | Estimated Size | Likelihood |
|----------|---------------|------------|
| Windows folder | 100-150 GB | High |
| Program Files | 50-100 GB | High |
| System Restore | 50-100 GB | Medium |
| Virtual Machines | 50-200 GB | Medium |
| Videos/Pictures | 50-100 GB | Medium |
| ProgramData | 20-50 GB | High |
| System files | 20-40 GB | High |
| Hidden caches | 20-50 GB | Medium |

---

## 🧹 Cleanup Recommendations

Once you find the large folders:

### Windows Folder
```powershell
# Run Disk Cleanup
cleanmgr /d C: /VERYLOWDISK

# Clean component store
Dism.exe /Online /Cleanup-Image /StartComponentCleanup /ResetBase

# Remove Windows.old
Remove-Item "C:\Windows.old" -Recurse -Force
```

### System Restore
```powershell
# Reduce System Restore space
# Control Panel → System → System Protection → Configure
# Set to 2-5% of drive (20-50 GB)
```

### Docker
```powershell
docker system prune -a --volumes -f
```

### Development Caches
```powershell
# Gradle
Remove-Item "$env:USERPROFILE\.gradle\caches" -Recurse -Force

# Maven
Remove-Item "$env:USERPROFILE\.m2\repository" -Recurse -Force

# NuGet
nuget locals all -clear
```

---

## ✅ Action Plan

### Step 1: Run the Scan Script (30 min)
```powershell
cd EIS-RV
.\find-missing-space.ps1
```

### Step 2: Review Results
- Check the CSV export
- Identify folders > 50 GB
- Prioritize by cleanup potential

### Step 3: Clean Large Folders
- Windows.old: Delete
- System Restore: Reduce to 5%
- Windows Update: Clean
- Docker: Prune
- Downloads: Manual cleanup
- OneDrive: Enable Files On-Demand

### Step 4: Verify
```powershell
Get-PSDrive C | Select-Object Used, Free
```

---

## 🎯 Expected Results

After finding and cleaning the missing 550 GB:

**Before:**
- Used: 947.51 GB
- Free: 5.41 GB

**After:**
- Used: ~600 GB
- Free: ~350 GB

**Breakdown:**
- Windows cleanup: ~100 GB
- System Restore: ~50 GB
- Docker/VMs: ~50 GB
- Downloads: ~50 GB
- OneDrive: ~80 GB (Files On-Demand)
- Other: ~20 GB

---

## 📞 Need Help?

If you can't find the missing space:

1. **Run as Administrator** - Some folders require admin access
2. **Use WinDirStat** - Visual treemap shows everything
3. **Check hidden files** - Enable "Show hidden files" in Explorer
4. **Check system files** - Enable "Show protected operating system files"
5. **Use TreeSize** - Professional tool for deep analysis

---

**Status:** 🔴 INVESTIGATION NEEDED  
**Missing:** ~550 GB  
**Action:** Run find-missing-space.ps1  
**Priority:** HIGH

**Next:** Run the script and report back with findings!
