# 🚀 Deploy VANL Now - 3 Simple Steps

## ⚡ Fastest Method (5 minutes)

### Step 1: Push to GitHub

```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "Deploy VANL"
git branch -M main

# Create repository on GitHub.com, then:
git remote add origin https://github.com/YOUR_USERNAME/vanl.git
git push -u origin main
```

### Step 2: Deploy on Render.com

1. Go to **https://render.com**
2. Click **"Get Started for Free"**
3. Sign up with your GitHub account
4. Click **"New +"** → **"Web Service"**
5. Select your `vanl` repository
6. Render will auto-detect `render.yaml`
7. Click **"Create Web Service"**

### Step 3: Share with Researchers

Your API is now live at:
- **API**: `https://vanl-api.onrender.com`
- **Docs**: `https://vanl-api.onrender.com/docs`
- **Frontend**: `https://vanl-api.onrender.com/`

Give researchers the **RESEARCHER_GUIDE.md** file!

---

## 🎯 Alternative: Deploy Locally (30 seconds)

### For Same Network Access:

```bash
# Start server
python -m uvicorn vanl.backend.main:app --host 0.0.0.0 --port 8000

# Find your IP address
ipconfig  # Windows
# or
ifconfig  # Mac/Linux

# Share with researchers:
# http://YOUR_IP:8000
```

---

## ✅ Verify Deployment

```bash
# Test health endpoint
curl https://vanl-api.onrender.com/api/health

# Should return:
# {"status": "healthy", "service": "VANL", "version": "1.0.0"}
```

---

## 📱 Quick Test

### Python:
```python
import requests

response = requests.post(
    "https://vanl-api.onrender.com/api/simulate",
    json={"Rs": 10, "Rct": 100, "Cdl": 1e-5, "sigma_warburg": 50, "n_cpe": 0.9}
)

print(response.json())
```

### Browser:
Go to: `https://vanl-api.onrender.com/docs`

---

## 🆘 Troubleshooting

### "Repository not found"
- Make sure repository is public on GitHub
- Or grant Render access to private repos

### "Build failed"
- Check Render logs in dashboard
- Verify `vanl/requirements.txt` exists

### "Service unavailable"
- First request after 15 min takes ~30s (cold start)
- This is normal for free tier

---

## 🎓 Next Steps

1. ✅ Share `RESEARCHER_GUIDE.md` with your team
2. ✅ Test all endpoints at `/docs`
3. ✅ (Optional) Set up custom domain
4. ✅ (Optional) Add API key authentication

---

**That's it! Your researchers can now use VANL from anywhere! 🎉**

