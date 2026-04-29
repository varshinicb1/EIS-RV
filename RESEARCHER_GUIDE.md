# VANL - Researcher Quick Start Guide

## 🎯 What is VANL?

VANL (Virtual Autonomous Nanomaterials Lab) is a web-based simulation platform for:
- **Electrochemical devices** (supercapacitors, batteries, biosensors)
- **Printed electronics** (ink formulation, printing optimization)
- **Material discovery** (composition optimization, property prediction)

**No installation required** - just use your web browser!

---

## 🌐 Access VANL

### Web Interface
**URL**: https://vanl-api.onrender.com

### API Documentation
**Interactive Docs**: https://vanl-api.onrender.com/docs

---

## 🚀 Quick Examples

### Example 1: Simulate Electrochemical Impedance (EIS)

**Using Web Interface:**
1. Go to https://vanl-api.onrender.com/docs
2. Find `POST /api/simulate`
3. Click "Try it out"
4. Enter parameters:
   ```json
   {
     "Rs": 10,
     "Rct": 100,
     "Cdl": 0.00001,
     "sigma_warburg": 50,
     "n_cpe": 0.9
   }
   ```
5. Click "Execute"
6. View Nyquist and Bode plots in response

**Using Python:**
```python
import requests
import matplotlib.pyplot as plt

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

# Plot Nyquist
plt.figure(figsize=(8, 6))
plt.plot(data['nyquist']['Z_real'], data['nyquist']['Z_imag_neg'], 'o-')
plt.xlabel("Z' (Ω)")
plt.ylabel("-Z'' (Ω)")
plt.title("Nyquist Plot")
plt.axis('equal')
plt.grid(True)
plt.show()
```

**Using MATLAB:**
```matlab
url = 'https://vanl-api.onrender.com/api/simulate';
data = struct('Rs', 10, 'Rct', 100, 'Cdl', 1e-5, ...
              'sigma_warburg', 50, 'n_cpe', 0.9);
options = weboptions('MediaType', 'application/json');
response = webwrite(url, data, options);

% Plot Nyquist
figure;
plot(response.nyquist.Z_real, response.nyquist.Z_imag_neg, 'o-');
xlabel('Z'' (\Omega)');
ylabel('-Z'''' (\Omega)');
title('Nyquist Plot');
axis equal;
grid on;
```

---

### Example 2: Design a Conductive Ink

**Using Web Interface:**
1. Go to https://vanl-api.onrender.com/docs
2. Find `POST /api/pe/ink/simulate`
3. Enter parameters:
   ```json
   {
     "filler_material": "graphene",
     "filler_loading_wt_pct": 10,
     "particle_size_nm": 500,
     "aspect_ratio": 100,
     "primary_solvent": "water",
     "print_method": "screen_printing"
   }
   ```

**Using Python:**
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/pe/ink/simulate",
    json={
        "filler_material": "graphene",
        "filler_loading_wt_pct": 10,
        "particle_size_nm": 500,
        "aspect_ratio": 100,
        "primary_solvent": "water",
        "print_method": "screen_printing"
    }
)

ink = response.json()
print(f"Viscosity: {ink['viscosity_mPas']} mPa·s")
print(f"Sheet Resistance: {ink['sheet_resistance_ohm_sq']} Ω/□")
print(f"Conductivity: {ink['conductivity_S_m']} S/m")
print(f"Printability Score: {ink['printability_score']}")
```

---

### Example 3: Optimize Material Composition

**Using Python:**
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/optimize",
    json={
        "materials": ["graphene", "MnO2", "carbon_black"],
        "n_iterations": 20,
        "weight_Rct": 0.4,
        "weight_Rs": 0.2,
        "weight_capacitance": 0.4,
        "max_cost": 3.0
    }
)

result = response.json()
best = result["best_result"]

print("Optimal Composition:")
for material, fraction in best["composition"].items():
    print(f"  {material}: {fraction*100:.1f}%")

print(f"\nPredicted Performance:")
print(f"  Rct: {best['eis_params']['Rct_ohm']} Ω")
print(f"  Capacitance: {best['eis_params']['Cdl_F']*1000} mF")
```

---

### Example 4: Design a Glucose Biosensor

**Using Python:**
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/pe/biosensor/simulate",
    json={
        "analyte": "glucose",
        "sensor_type": "amperometric",
        "electrode_material": "carbon_black",
        "modifier": "enzyme",
        "area_mm2": 7.07,
        "enzyme_loading_U_cm2": 10.0,
        "pH": 7.4,
        "applied_potential_V": 0.6
    }
)

biosensor = response.json()
print(f"Sensitivity: {biosensor['sensitivity_uA_mM']} µA/mM")
print(f"LOD: {biosensor['LOD_uM']} µM")
print(f"Linear Range: {biosensor['linear_range_mM']} mM")
print(f"Response Time: {biosensor['response_time_s']} s")
```

---

### Example 5: Simulate a Printed Battery

**Using Python:**
```python
response = requests.post(
    "https://vanl-api.onrender.com/api/pe/battery/simulate",
    json={
        "chemistry": "zinc_MnO2",
        "electrode_area_cm2": 1.0,
        "cathode_loading_mg_cm2": 10.0,
        "anode_loading_mg_cm2": 8.0,
        "C_rate": 0.5
    }
)

battery = response.json()
print(f"Capacity: {battery['delivered_capacity_mAh']} mAh")
print(f"Energy: {battery['energy_mWh']} mWh")
print(f"Voltage: {battery['nominal_V']} V")
print(f"Energy Density: {battery['energy_density_Wh_kg']} Wh/kg")
```

---

## 📚 Available Endpoints

### Core Electrochemistry
- `GET /api/health` - Check if API is running
- `GET /api/materials` - List all materials in database
- `POST /api/simulate` - Simulate EIS from circuit parameters
- `POST /api/predict` - Predict EIS from material composition
- `POST /api/optimize` - Optimize material composition
- `POST /api/cv/simulate` - Simulate cyclic voltammetry
- `POST /api/gcd/simulate` - Simulate galvanostatic charge-discharge

### Printed Electronics
- `POST /api/pe/ink/simulate` - Ink formulation & rheology
- `POST /api/pe/supercap/simulate` - Supercapacitor device
- `POST /api/pe/battery/simulate` - Printed battery
- `POST /api/pe/biosensor/simulate` - Biosensor performance

### Research Pipeline
- `GET /api/pipeline/stats` - Database statistics
- `POST /api/pipeline/search` - Search literature data

---

## 🔍 Material Database

### Available Materials (50+)

**Carbon Materials:**
- graphene, reduced_graphene_oxide, graphene_oxide
- CNT, SWCNT, MWCNT
- carbon_black, activated_carbon, graphite

**Metal Oxides:**
- MnO2, NiO, Fe2O3, Fe3O4, Co3O4, RuO2
- TiO2, ZnO, V2O5, CuO, WO3, SnO2

**Conducting Polymers:**
- PEDOT_PSS, polyaniline, polypyrrole

**Battery Materials:**
- LiFePO4, LiCoO2, NMC_811, Li4Ti5O12

**View Full List:**
```python
response = requests.get("https://vanl-api.onrender.com/api/materials")
materials = response.json()
for mat in materials:
    print(f"{mat['name']}: {mat['conductivity_S_m']} S/m")
```

---

## 💡 Tips & Best Practices

### 1. Start with Interactive Docs
- Go to `/docs` endpoint
- Try examples directly in browser
- See all parameters and responses

### 2. Use Reasonable Parameters
- **EIS**: Rs (1-100 Ω), Rct (10-10000 Ω), Cdl (1e-6 to 1e-3 F)
- **Ink**: Loading (1-20 wt%), particle size (100-1000 nm)
- **Battery**: C-rate (0.1-2.0), area (0.5-5 cm²)

### 3. Check Response Status
```python
response = requests.post(url, json=data)
if response.status_code == 200:
    result = response.json()
else:
    print(f"Error: {response.status_code}")
    print(response.text)
```

### 4. Save Results
```python
import json

# Save to file
with open('results.json', 'w') as f:
    json.dump(result, f, indent=2)

# Load later
with open('results.json', 'r') as f:
    result = json.load(f)
```

### 5. Batch Processing
```python
compositions = [
    {"graphene": 0.7, "MnO2": 0.3},
    {"graphene": 0.6, "MnO2": 0.4},
    {"graphene": 0.5, "MnO2": 0.5},
]

results = []
for comp in compositions:
    response = requests.post(
        "https://vanl-api.onrender.com/api/predict",
        json={"composition": comp, "synthesis": {...}}
    )
    results.append(response.json())
```

---

## ⚠️ Important Notes

### First Request May Be Slow
- Free tier "spins down" after 15 min of inactivity
- First request takes ~30 seconds to wake up
- Subsequent requests are fast (<1 second)

### Rate Limits
- No hard limits on free tier
- Please be reasonable (don't spam thousands of requests)
- For heavy batch processing, contact admin

### Data Privacy
- All simulations are stateless (not stored)
- No personal data collected
- Results are not logged

---

## 🆘 Troubleshooting

### Issue: "Connection Error"
**Solution**: Check if URL is correct and you have internet access

### Issue: "422 Validation Error"
**Solution**: Check parameter names and types in `/docs`

### Issue: "Slow Response"
**Solution**: First request after inactivity is slow (cold start). Wait 30s.

### Issue: "Unexpected Results"
**Solution**: 
- Check parameter ranges (see Tips section)
- Verify units (Ω, F, S/m, etc.)
- Review physics in `/docs` descriptions

---

## 📖 Further Reading

### Documentation
- **API Docs**: https://vanl-api.onrender.com/docs
- **GitHub**: [Link to repository]
- **Paper**: [Link to publication]

### Physics Background
- Bard & Faulkner - "Electrochemical Methods"
- Conway - "Electrochemical Supercapacitors"
- Derby - "Inkjet Printing of Functional Materials"

---

## 📧 Support

**Questions?** Contact your lab administrator or check:
- API documentation at `/docs`
- GitHub Issues
- Lab Slack/Teams channel

---

**Happy Simulating! 🚀**

