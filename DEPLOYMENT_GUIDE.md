# VANL Deployment Guide - Free Hosting

## 🎯 Quick Deploy (5 minutes)

VANL is configured for **completely free** deployment on multiple platforms.

---

## Option 1: Render.com (Recommended - Easiest)

### Why Render?
- ✅ **100% Free** (750 hours/month)
- ✅ Automatic HTTPS
- ✅ Custom domain support
- ✅ Auto-deploy from GitHub
- ✅ No credit card required

### Steps:

1. **Push to GitHub** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial VANL deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/vanl.git
   git push -u origin main
   ```

2. **Deploy on Render**:
   - Go to https://render.com
   - Click "Get Started for Free"
   - Sign up with GitHub
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect `render.yaml`
   - Click "Create Web Service"

3. **Access Your API**:
   - URL: `https://vanl-api.onrender.com`
   - Docs: `https://vanl-api.onrender.com/docs`
   - Frontend: `https://vanl-api.onrender.com/`

### ⚠️ Free Tier Limitations:
- Spins down after 15 min of inactivity (first request takes ~30s to wake up)
- 750 hours/month (enough for continuous use)
- 512 MB RAM (sufficient for VANL)

---

## Option 2: Railway.app (Alternative)

### Why Railway?
- ✅ **$5 free credit/month** (enough for ~500 hours)
- ✅ Faster cold starts than Render
- ✅ Better performance
- ✅ No credit card for trial

### Steps:

1. **Install Railway CLI**:
   ```bash
   npm install -g @railway/cli
   # or
   curl -fsSL https://railway.app/install.sh | sh
   ```

2. **Deploy**:
   ```bash
   railway login
   railway init
   railway up
   ```

3. **Get URL**:
   ```bash
   railway domain
   ```

---

## Option 3: Fly.io (Best Performance)

### Why Fly.io?
- ✅ **Free tier**: 3 shared-cpu VMs
- ✅ Global edge network
- ✅ Best cold start performance
- ✅ No credit card required

### Steps:

1. **Install Fly CLI**:
   ```bash
   # Windows (PowerShell)
   iwr https://fly.io/install.ps1 -useb | iex
   
   # Mac/Linux
   curl -L https://fly.io/install.sh | sh
   ```

2. **Deploy**:
   ```bash
   fly auth signup
   fly launch
   # Follow prompts, select free tier
   fly deploy
   ```

3. **Access**:
   ```bash
   fly open
   ```

---

## Option 4: Heroku (Classic)

### Why Heroku?
- ✅ **Free tier** (550-1000 hours/month)
- ✅ Most mature platform
- ✅ Extensive documentation

### Steps:

1. **Install Heroku CLI**:
   ```bash
   # Download from: https://devcli.heroku.com/install
   ```

2. **Deploy**:
   ```bash
   heroku login
   heroku create vanl-app
   git push heroku main
   heroku open
   ```

---

## Option 5: Local Network (Instant - No Internet Required)

### For Lab/Office Use:

1. **Start Server**:
   ```bash
   python -m uvicorn vanl.backend.main:app --host 0.0.0.0 --port 8000
   ```

2. **Find Your IP**:
   ```bash
   # Windows
   ipconfig
   
   # Mac/Linux
   ifconfig | grep "inet "
   ```

3. **Share with Researchers**:
   - URL: `http://YOUR_IP:8000`
   - Example: `http://192.168.1.100:8000`

---

## 🔒 Adding Basic Authentication (Optional)

### Simple API Key Protection:

1. **Create `.env` file**:
   ```bash
   cp .env.example .env
   ```

2. **Add to `.env`**:
   ```
   API_KEY=your-secret-key-here
   ```

3. **Update `main.py`** (I can do this if you want):
   ```python
   from fastapi import Security, HTTPException
   from fastapi.security import APIKeyHeader
   
   api_key_header = APIKeyHeader(name="X-API-Key")
   
   def verify_api_key(api_key: str = Security(api_key_header)):
       if api_key != os.getenv("API_KEY"):
           raise HTTPException(status_code=403, detail="Invalid API Key")
   ```

4. **Researchers use**:
   ```bash
   curl -H "X-API-Key: your-secret-key-here" https://your-app.onrender.com/api/health
   ```

---

## 📊 Monitoring Your Deployment

### Check Health:
```bash
curl https://your-app.onrender.com/api/health
```

### View Logs:
- **Render**: Dashboard → Logs tab
- **Railway**: `railway logs`
- **Fly.io**: `fly logs`
- **Heroku**: `heroku logs --tail`

### Performance:
- **Render**: Dashboard → Metrics
- **Railway**: Dashboard → Metrics
- **Fly.io**: Dashboard → Metrics

---

## 🚀 Custom Domain (Optional - Free)

### Using Render:
1. Go to Settings → Custom Domain
2. Add your domain (e.g., `vanl.youruniversity.edu`)
3. Update DNS records as shown
4. Automatic HTTPS included!

### Using Cloudflare (Free):
1. Sign up at cloudflare.com
2. Add your domain
3. Point to your Render/Railway/Fly URL
4. Enable "Always Use HTTPS"

---

## 🔧 Troubleshooting

### Issue: "Application Error" on Render
**Solution**: Check logs in Render dashboard. Usually missing dependencies.

### Issue: Slow First Request
**Solution**: This is normal for free tiers (cold start). Consider:
- Using Railway (faster cold starts)
- Upgrading to paid tier ($7/month for always-on)
- Using a keep-alive service (e.g., UptimeRobot pings every 5 min)

### Issue: Out of Memory
**Solution**: 
- Reduce CV simulation points
- Use caching for repeated calculations
- Upgrade to paid tier (more RAM)

### Issue: Can't Access from University Network
**Solution**:
- Check if firewall blocks external APIs
- Use HTTPS (more likely to work)
- Contact IT to whitelist your domain

---

## 📈 Scaling (When You Need More)

### Free Tier Limits:
| Platform | RAM | CPU | Uptime | Cost |
|----------|-----|-----|--------|------|
| Render | 512MB | Shared | 750h/mo | $0 |
| Railway | 512MB | Shared | ~500h/mo | $0 |
| Fly.io | 256MB | Shared | Always | $0 |
| Heroku | 512MB | Shared | 550h/mo | $0 |

### Paid Upgrades (When Needed):
| Platform | RAM | CPU | Cost/Month |
|----------|-----|-----|------------|
| Render | 2GB | 1 vCPU | $7 |
| Railway | 8GB | 8 vCPU | $20 |
| Fly.io | 2GB | 2 vCPU | $12 |

---

## 🎓 For Your Researchers

### Quick Start Guide:

**API Endpoint**: `https://vanl-api.onrender.com`

**Test Connection**:
```bash
curl https://vanl-api.onrender.com/api/health
```

**Interactive Docs**:
- Swagger UI: `https://vanl-api.onrender.com/docs`
- ReDoc: `https://vanl-api.onrender.com/redoc`

**Example API Call**:
```python
import requests

# Simulate EIS
response = requests.post(
    "https://vanl-api.onrender.com/api/simulate",
    json={
        "Rs": 10,
        "Rct": 100,
        "Cdl": 1e-5,
        "sigma_warburg": 50,
        "n_cpe": 0.9
    }
)

data = response.json()
print(f"Simulated {len(data['frequencies'])} frequency points")
```

---

## 🆘 Need Help?

1. **Check logs** in your platform dashboard
2. **Review API docs** at `/docs` endpoint
3. **Test locally** first: `python -m uvicorn vanl.backend.main:app --reload`
4. **Check GitHub Issues** for similar problems

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Platform account created (Render/Railway/Fly/Heroku)
- [ ] Service deployed
- [ ] Health check passing (`/api/health`)
- [ ] API docs accessible (`/docs`)
- [ ] Test API call successful
- [ ] URL shared with researchers
- [ ] (Optional) Custom domain configured
- [ ] (Optional) API key authentication added
- [ ] (Optional) Monitoring/alerts set up

---

**Recommended: Start with Render.com** - It's the easiest and most reliable free option!

