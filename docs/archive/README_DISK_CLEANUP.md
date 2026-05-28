# 🚨 URGENT: Disk Space Cleanup Required

**Your C: drive has only 5.41 GB free out of 953 GB (0.57%)**

This is blocking file operations and causing the save feature to fail.

---

## 🎯 Quick Fix (5 minutes)

Run this command in PowerShell (as Administrator):

```powershell
cd EIS-RV
.\cleanup-disk.ps1
```

**This will automatically clean:**
- npm cache (7.83 GB)
- pnpm store (10.09 GB)
- pip cache (1.84 GB)
- uv cache (2.38 GB)
- Temp folders (5.85 GB)
- .embedder cache (17.87 GB)
- Browser caches (~10 GB)
- Docker images (1.6 GB)

**Expected space freed: ~55 GB**

---

## 📊 What's Taking Up Space?

### Top Offenders:
1. **AppData\Local** - 178.49 GB
   - Programs: 33.41 GB
   - Microsoft: 24.20 GB
   - Google Chrome: 16.02 GB
   - pnpm: 10.09 GB
   - arduino: 8.70 GB
   - npm-cache: 7.83 GB

2. **OneDrive** - 80.49 GB
   - Consider moving to external drive

3. **Downloads** - 78.89 GB
   - Clean old files manually

4. **.ollama** - 30.75 GB
   - Remove unused AI models

5. **.embedder** - 17.87 GB
   - Cache can be safely deleted

**Total identified: ~386 GB**

---

## 🚀 Step-by-Step Cleanup

### Step 1: Run Automated Cleanup (5 min)
```powershell
# Open PowerShell as Administrator
# Right-click PowerShell → Run as Administrator

cd C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV
.\cleanup-disk.ps1
```

This will free up ~55 GB automatically.

---

### Step 2: Clean Downloads Folder (10 min)
```powershell
# Open Downloads folder
explorer "$env:USERPROFILE\Downloads"

# Sort by date (oldest first)
# Delete files older than 3 months
# Keep only important files
```

**Target: Free 40-50 GB**

---

### Step 3: Remove Unused Ollama Models (2 min)
```powershell
# List installed models
ollama list

# Remove models you don't use
ollama rm llama2
ollama rm codellama
ollama rm mistral
# etc.
```

**Target: Free 20-30 GB**

---

### Step 4: Run Windows Disk Cleanup (5 min)
```powershell
# Run Windows cleanup utility
cleanmgr /d C: /VERYLOWDISK

# Select:
# ✓ Temporary files
# ✓ Downloads folder
# ✓ Recycle Bin
# ✓ Thumbnails
# ✓ Windows Update Cleanup
```

**Target: Free 5-10 GB**

---

## 📈 Expected Results

| Action | Time | Space Freed |
|--------|------|-------------|
| Automated cleanup | 5 min | ~55 GB |
| Downloads cleanup | 10 min | ~50 GB |
| Ollama models | 2 min | ~30 GB |
| Windows cleanup | 5 min | ~10 GB |
| **TOTAL** | **22 min** | **~145 GB** |

**Final free space: ~150 GB (16% of drive)**

---

## ✅ After Cleanup

Once you have at least 50 GB free:

### 1. Hard Refresh Browser
```
Press: Ctrl + Shift + R
```

This will load the latest frontend code with the save/load feature.

### 2. Test the Application
1. Open: http://localhost:5173
2. Go to: Unified Spectroscopy
3. Upload your spectrum file
4. Click "Save Analysis"
5. Enter a name and save
6. Refresh page - analysis should persist

### 3. Verify Backend Processing
The backend is already working correctly:
- ✅ Baseline correction
- ✅ Normalization
- ✅ Peak detection
- ✅ Material identification

Look for "Corrected" in the plot metadata to confirm.

---

## 🔧 Detailed Audit

For a complete breakdown of what's using space, see:
- **DISK_SPACE_AUDIT.md** - Full audit report with recommendations

---

## 🎯 Priority Actions

### IMMEDIATE (Do Now):
1. ✅ Run `cleanup-disk.ps1`
2. ✅ Clean Downloads folder
3. ✅ Remove unused Ollama models

### SHORT TERM (This Week):
1. Move OneDrive to external drive
2. Review installed applications
3. Set up automatic cleanup schedule

### LONG TERM (This Month):
1. Consider upgrading to larger drive
2. Move package manager caches to external drive
3. Set up cloud backup for old projects

---

## 📞 Need Help?

If the cleanup script fails or you need assistance:

1. Check the error messages in the script output
2. Try running individual commands manually
3. Ensure you're running PowerShell as Administrator
4. Check if any applications are using the files

---

## 🎉 Success Criteria

After cleanup, you should have:
- ✅ At least 100 GB free space
- ✅ Save/load feature working
- ✅ No file operation errors
- ✅ Faster system performance

---

**Generated:** May 5, 2026  
**Status:** 🔴 CRITICAL  
**Action:** Run cleanup script NOW  
**Priority:** HIGHEST

**Next:** Run `.\cleanup-disk.ps1` in PowerShell as Administrator
