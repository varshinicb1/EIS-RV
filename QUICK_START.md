# 🚀 VANL Quick Start - 5 Minutes to Live API

## For You (Lab Administrator)

### Deploy Now (5 minutes)
```bash
# 1. Push to GitHub (if not already done)
git push origin master

# 2. Go to https://render.com
# 3. Sign up with GitHub (free, no credit card)
# 4. Click "New +" → "Web Service"
# 5. Select your "vanl" repository
# 6. Click "Create Web Service"
# 7. Wait 2 minutes for build

# Done! Your API is live at:
# https://vanl-api.onrender.com
```

### Share with Researchers
Give them:
- **RESEARCHER_GUIDE.md** (complete usage guide)
- **API URL**: `https://vanl-api.onrender.com`
- **Docs URL**: `https://vanl-api.onrender.com/docs`

---

## For Researchers

### Access VANL
- **Interactive Docs**: https://vanl-api.onrender.com/docs
- **Try examples in browser** (no coding required)
- **Use from Python/MATLAB** (see examples below)

### Quick Examples

#### 1. Simulate EIS (Python)
```python
import requests

response = requests.post(
    "https://vanl-api.onrender.com/api/simulate",
    json={"Rs": 10, "Rct": 100, "Cdl": 1e-5, "sigma_warburg": 50, "n_cpe": 0.9}
)

data = response.json()
print(f"Capacitance: {data['eis_params']['Cdl_F']*1000} mF")
```

#### 2. Design Conductive Ink
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/pe/ink/simulate",
    json={
        "filler_material": "graphene",
        "filler_loading_wt_pct": 10,
        "print_method": "screen_printing"
    }
)

ink = response.json()
print(f"Conductivity: {ink['conductivity_S_m']} S/m")
print(f"Printability: {ink['printability_score']}")
```

#### 3. Optimize Materials
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/optimize",
    json={
        "materials": ["graphene", "MnO2", "carbon_black"],
        "n_iterations": 20
    }
)

result = response.json()
print("Optimal composition:", result["best_result"]["composition"])
```

#### 4. Design Biosensor
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/pe/biosensor/simulate",
    json={
        "analyte": "glucose",
        "sensor_type": "amperometric",
        "modifier": "enzyme"
    }
)

sensor = response.json()
print(f"Sensitivity: {sensor['sensitivity_uA_mM']} µA/mM")
print(f"LOD: {sensor['LOD_uM']} µM")
```

#### 5. Simulate Battery
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/pe/battery/simulate",
    json={"chemistry": "zinc_MnO2", "C_rate": 0.5}
)

battery = response.json()
print(f"Capacity: {battery['delivered_capacity_mAh']} mAh")
print(f"Energy: {battery['energy_mWh']} mWh")
```

### MATLAB Example
```matlab
url = 'https://vanl-api.onrender.com/api/simulate';
data = struct('Rs', 10, 'Rct', 100, 'Cdl', 1e-5, ...
              'sigma_warburg', 50, 'n_cpe', 0.9);
options = weboptions('MediaType', 'application/json');
response = webwrite(url, data, options);

% Plot Nyquist
plot(response.nyquist.Z_real, response.nyquist.Z_imag_neg, 'o-');
xlabel('Z'' (\Omega)'); ylabel('-Z'''' (\Omega)');
```

---

## What You Get

### 8 Physics Engines
1. **EIS** - Electrochemical Impedance
2. **CV** - Cyclic Voltammetry
3. **GCD** - Charge-Discharge
4. **Ink** - Conductive Ink Design
5. **Biosensor** - Sensor Performance
6. **Battery** - Energy Storage
7. **Supercapacitor** - Power Storage
8. **Materials** - 50+ Database

### Key Features
- 🌐 Web-based (no installation)
- 📊 Interactive docs
- 🔬 Physics-validated
- 🎨 Visualizations included
- 🤖 Bayesian optimization
- 🆓 Completely free

---

## Important Notes

### First Request is Slow
- Free tier "spins down" after 15 min
- First request takes ~30 seconds
- This is **normal** - just wait
- Subsequent requests are fast

### No Installation Required
- Just use the URL
- Works from any device
- No API key needed (yet)

### Get Help
- Read **RESEARCHER_GUIDE.md** for details
- Check `/docs` endpoint for all options
- Contact your lab administrator

---

## Status

✅ **195 tests passing**  
✅ **All engines working**  
✅ **Documentation complete**  
✅ **Ready to deploy**  

**Cost**: $0 (Free forever)  
**Time to deploy**: 5 minutes  
**Time to first simulation**: 30 seconds  

---

## Quick Links

### Documentation
- **RESEARCHER_GUIDE.md** - Complete usage guide
- **DEPLOY_NOW.md** - Deployment instructions
- **START_HERE.md** - Overview

### After Deployment
- **API**: https://vanl-api.onrender.com
- **Docs**: https://vanl-api.onrender.com/docs
- **Health**: https://vanl-api.onrender.com/api/health

---

**Questions?** Read RESEARCHER_GUIDE.md or ask your lab administrator.

**Ready to simulate?** Go to the `/docs` endpoint and start exploring!

🚀 **Happy Simulating!**
