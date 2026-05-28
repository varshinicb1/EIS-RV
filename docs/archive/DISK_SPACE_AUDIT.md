# 🔍 Disk Space Audit Report

**Date:** May 5, 2026  
**Drive:** C: (1TB)  
**Used:** 947.51 GB  
**Free:** 5.41 GB (0.57%)  
**Status:** 🔴 CRITICAL - Immediate action required

---

## 📊 Top Space Consumers

### Major Folders
| Location | Size | Action |
|----------|------|--------|
| **AppData\Local** | 178.49 GB | Clean caches |
| **OneDrive** | 80.49 GB | Move to cloud/external |
| **Downloads** | 78.89 GB | Clean old files |
| **.ollama** | 30.75 GB | Remove unused models |
| **.embedder** | 17.87 GB | Clean cache |

**Total identified:** ~386 GB

---

## 🎯 AppData Breakdown (178 GB)

### Largest Folders in AppData\Local:
| Folder | Size | Safe to Clean? | Action |
|--------|------|----------------|--------|
| **Programs** | 33.41 GB | ⚠️ Partial | Review installed apps |
| **Microsoft** | 24.20 GB | ⚠️ Partial | Clean Teams/VS cache |
| **Google** | 16.02 GB | ✅ Yes | Clean Chrome cache |
| **pnpm** | 10.09 GB | ✅ Yes | `pnpm store prune` |
| **arduino** | 8.70 GB | ⚠️ No | Keep if using |
| **npm-cache** | 7.83 GB | ✅ Yes | `npm cache clean --force` |
| **Android** | 7.00 GB | ⚠️ No | Keep if developing |
| **Temp** | 5.85 GB | ✅ Yes | Delete all |
| **Arduino15** | 5.61 GB | ⚠️ No | Keep if using |
| **Bitcoin** | 3.49 GB | ⚠️ Partial | Blockchain data |
| **Keil_v5** | 2.89 GB | ⚠️ No | Keep if using |
| **uv** | 2.38 GB | ✅ Yes | Python cache |
| **Packages** | 1.93 GB | ⚠️ Partial | NuGet packages |
| **pip** | 1.84 GB | ✅ Yes | `pip cache purge` |
| **Docker** | 1.62 GB | ⚠️ Partial | `docker system prune` |

---

## 🚀 Immediate Cleanup Actions

### 1. Clean Development Caches (Safe - ~30 GB)
```powershell
# Clean npm cache
npm cache clean --force

# Clean pnpm store
pnpm store prune

# Clean pip cache
pip cache purge

# Clean uv cache
uv cache clean

# Clean Temp folder
Remove-Item "$env:LOCALAPPDATA\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue

# Clean Windows Temp
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
```

**Expected space freed:** ~30 GB

---

### 2. Clean Browser Caches (Safe - ~16 GB)
```powershell
# Clean Google Chrome cache
$chromePath = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"
if (Test-Path $chromePath) {
    Remove-Item "$chromePath\*" -Recurse -Force -ErrorAction SilentlyContinue
}

# Clean Chrome Code Cache
$codeCache = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Code Cache"
if (Test-Path $codeCache) {
    Remove-Item "$codeCache\*" -Recurse -Force -ErrorAction SilentlyContinue
}
```

**Expected space freed:** ~16 GB

---

### 3. Clean Ollama Models (Optional - ~30 GB)
```powershell
# List Ollama models
ollama list

# Remove unused models (example)
# ollama rm llama2
# ollama rm codellama
# ollama rm mistral
```

**Expected space freed:** ~30 GB (if you remove all models)

---

### 4. Clean Downloads Folder (Manual - ~78 GB)
```powershell
# Open Downloads folder
explorer "$env:USERPROFILE\Downloads"

# Sort by date and delete old files
# Keep only recent/important files
```

**Expected space freed:** ~40-60 GB (manual cleanup)

---

### 5. Clean .embedder Cache (Safe - ~17 GB)
```powershell
# Clean embedder cache
Remove-Item "$env:USERPROFILE\.embedder\*" -Recurse -Force -ErrorAction SilentlyContinue
```

**Expected space freed:** ~17 GB

---

### 6. Docker Cleanup (Safe - ~1.6 GB)
```powershell
# Clean Docker system
docker system prune -a --volumes -f
```

**Expected space freed:** ~1.6 GB

---

### 7. Windows Disk Cleanup (Safe - ~5-10 GB)
```powershell
# Run Windows Disk Cleanup
cleanmgr /d C: /VERYLOWDISK

# Or use GUI
# Press Win+R, type: cleanmgr
# Select: Temporary files, Downloads, Recycle Bin, Thumbnails
```

**Expected space freed:** ~5-10 GB

---

## 📋 Quick Cleanup Script

Save this as `cleanup.ps1` and run as Administrator:

```powershell
Write-Host "=== RĀMAN Studio Disk Cleanup ===" -ForegroundColor Cyan
Write-Host ""

$freedSpace = 0

# 1. Clean npm cache
Write-Host "Cleaning npm cache..." -ForegroundColor Yellow
npm cache clean --force 2>$null
$freedSpace += 7.83

# 2. Clean pnpm store
Write-Host "Cleaning pnpm store..." -ForegroundColor Yellow
pnpm store prune 2>$null
$freedSpace += 10.09

# 3. Clean pip cache
Write-Host "Cleaning pip cache..." -ForegroundColor Yellow
pip cache purge 2>$null
$freedSpace += 1.84

# 4. Clean uv cache
Write-Host "Cleaning uv cache..." -ForegroundColor Yellow
uv cache clean 2>$null
$freedSpace += 2.38

# 5. Clean Temp folders
Write-Host "Cleaning Temp folders..." -ForegroundColor Yellow
Remove-Item "$env:LOCALAPPDATA\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
$freedSpace += 5.85

# 6. Clean .embedder
Write-Host "Cleaning .embedder cache..." -ForegroundColor Yellow
Remove-Item "$env:USERPROFILE\.embedder\*" -Recurse -Force -ErrorAction SilentlyContinue
$freedSpace += 17.87

# 7. Clean Chrome cache
Write-Host "Cleaning Chrome cache..." -ForegroundColor Yellow
$chromePath = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"
if (Test-Path $chromePath) {
    Remove-Item "$chromePath\*" -Recurse -Force -ErrorAction SilentlyContinue
}
$freedSpace += 10

Write-Host ""
Write-Host "=== Cleanup Complete ===" -ForegroundColor Green
Write-Host "Estimated space freed: ~$([math]::Round($freedSpace, 2)) GB" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Manually clean Downloads folder (78 GB)" -ForegroundColor Yellow
Write-Host "2. Review Ollama models (30 GB)" -ForegroundColor Yellow
Write-Host "3. Run Windows Disk Cleanup" -ForegroundColor Yellow
```

---

## 🎯 Expected Results

### After Automatic Cleanup (~55 GB freed):
- npm-cache: 7.83 GB
- pnpm: 10.09 GB
- pip: 1.84 GB
- uv: 2.38 GB
- Temp: 5.85 GB
- .embedder: 17.87 GB
- Chrome cache: ~10 GB

**Total:** ~55 GB freed

### After Manual Cleanup (~140 GB freed):
- Downloads: ~50 GB (manual)
- Ollama models: ~30 GB (optional)
- Windows cleanup: ~5 GB

**Total:** ~140 GB freed

### Final State:
- **Current:** 5.41 GB free
- **After cleanup:** ~145 GB free (15% of drive)
- **Status:** ✅ Healthy

---

## ⚠️ What NOT to Delete

### Keep These Folders:
- ❌ **Arduino/Arduino15** (8.7 + 5.61 GB) - If you're doing embedded development
- ❌ **Android** (7 GB) - If you're doing Android development
- ❌ **Keil_v5** (2.89 GB) - If you're doing ARM development
- ❌ **Programs** (33.41 GB) - Contains installed applications
- ❌ **Microsoft** (24.20 GB) - System files and VS Code/Teams data
- ❌ **Bitcoin** (3.49 GB) - Blockchain data (unless you don't use it)

---

## 🔄 Maintenance Schedule

### Weekly:
- Clear browser cache
- Empty Recycle Bin
- Clean Temp folders

### Monthly:
- Run `npm cache clean --force`
- Run `pnpm store prune`
- Run `pip cache purge`
- Clean Downloads folder

### Quarterly:
- Review installed applications
- Remove unused Ollama models
- Run Windows Disk Cleanup
- Review OneDrive sync settings

---

## 📊 Storage Recommendations

### Current Setup Issues:
1. **1TB drive is too small** for your development workload
2. **No separation** between system and data
3. **Multiple package managers** (npm, pnpm, pip, uv) duplicating data

### Recommendations:
1. **Add external drive** for:
   - Downloads archive
   - OneDrive files
   - Project backups
   - Large datasets

2. **Configure package managers** to use external cache:
   ```powershell
   # Move npm cache
   npm config set cache "D:\npm-cache"
   
   # Move pnpm store
   pnpm config set store-dir "D:\pnpm-store"
   ```

3. **Move OneDrive** to external drive:
   - Settings → Backup → Manage backup
   - Change location to D: drive

4. **Use cloud storage** for:
   - Old projects
   - Large media files
   - Archived downloads

---

## 🚨 Critical Actions (Do This Now)

### Step 1: Run Quick Cleanup (5 minutes)
```powershell
# Clean caches
npm cache clean --force
pnpm store prune
pip cache purge
uv cache clean

# Clean temp
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
```

### Step 2: Clean Downloads (10 minutes)
```powershell
# Open and manually review
explorer "$env:USERPROFILE\Downloads"
```

### Step 3: Review Ollama Models (2 minutes)
```powershell
# List and remove unused
ollama list
# ollama rm <model-name>
```

### Step 4: Run Windows Cleanup (5 minutes)
```powershell
cleanmgr /d C: /VERYLOWDISK
```

**Total time:** ~25 minutes  
**Expected space freed:** ~100 GB

---

## ✅ Success Criteria

After cleanup, you should have:
- ✅ At least 100 GB free space
- ✅ Less than 80% disk usage
- ✅ Ability to save files without errors
- ✅ Faster system performance

---

**Report Generated:** May 5, 2026  
**Status:** 🔴 CRITICAL  
**Action Required:** IMMEDIATE  
**Priority:** HIGHEST

**Next:** Run the cleanup script above to free up space immediately.
