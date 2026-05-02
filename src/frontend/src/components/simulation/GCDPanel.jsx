import React, { useState, useRef, useEffect, useCallback } from 'react';

const DEFAULT = {
  Cdl_F: 1e-3,
  C_pseudo_F: 0,
  Rs_ohm: 5.0,
  Rct_ohm: 50.0,
  current_mA: 1.0,
  V_min: 0,
  V_max: 1.0,
  n_cycles: 5,
  active_mass_mg: 1.0,
};

const PRESETS = {
  'EDLC — Carbon': { Cdl_F: 5e-3, C_pseudo_F: 0, Rs_ohm: 2, Rct_ohm: 10, current_mA: 1, V_max: 1.0, active_mass_mg: 1.0 },
  'Pseudocap — MnO₂': { Cdl_F: 2e-3, C_pseudo_F: 8e-3, Rs_ohm: 5, Rct_ohm: 30, current_mA: 0.5, V_max: 0.8, active_mass_mg: 1.0 },
  'High-Rate EDLC': { Cdl_F: 10e-3, C_pseudo_F: 0, Rs_ohm: 0.5, Rct_ohm: 2, current_mA: 5, V_max: 1.0, active_mass_mg: 2.0 },
  'rGO Electrode': { Cdl_F: 3e-3, C_pseudo_F: 2e-3, Rs_ohm: 3, Rct_ohm: 15, current_mA: 1, V_max: 1.0, active_mass_mg: 0.5 },
};

// ── Client-side GCD simulation ──────────────────────────────────
function simulateGCDLocal(params) {
  const { Cdl_F, C_pseudo_F, Rs_ohm, Rct_ohm, current_mA, V_min, V_max, n_cycles, active_mass_mg } = params;
  const C_total = Cdl_F + C_pseudo_F;
  const I = current_mA * 1e-3; // A
  const R_total = Rs_ohm + Rct_ohm * 0.1;
  const V_range = V_max - V_min;
  const mass_kg = active_mass_mg * 1e-6;

  const dt = C_total * V_range / (I * 400);
  const time = [], voltage = [], current = [];
  let V = V_min, t = 0, charging = true, cycle = 0;
  const cycleData = [];
  let cycleStart = t, chargeT = 0, dischargeT = 0;

  const maxSteps = n_cycles * 900;
  for (let step = 0; step < maxSteps && cycle < n_cycles; step++) {
    const iApplied = charging ? I : -I;
    const dV = iApplied * dt / C_total;
    V += dV - V * 1e-5 * dt;

    if (charging && V >= V_max) {
      V = V_max;
      charging = false;
      chargeT = t - cycleStart;
    }
    if (!charging && V <= V_min) {
      V = V_min;
      charging = true;
      dischargeT = t - cycleStart - chargeT;
      
      const Cs = mass_kg > 0 ? (I * dischargeT) / (mass_kg * 1e3 * V_range) : 0;
      const E_Wh_kg = 0.5 * Cs * V_range * V_range / 3.6;
      const P_W_kg = dischargeT > 0 ? E_Wh_kg * 3600 / dischargeT : 0;
      const eta = chargeT > 0 ? (dischargeT / chargeT) * 100 : 0;

      cycleData.push({
        cycle: cycle + 1,
        t_charge: chargeT,
        t_discharge: dischargeT,
        Cs_F_g: Cs,
        E_Wh_kg,
        P_W_kg,
        eta_pct: eta,
      });

      cycle++;
      cycleStart = t;
      chargeT = 0;
      dischargeT = 0;
    }

    time.push(t);
    voltage.push(V);
    current.push(iApplied * 1e3);
    t += dt;
  }

  const avgCs = cycleData.length > 0
    ? cycleData.reduce((a, c) => a + c.Cs_F_g, 0) / cycleData.length : 0;
  const avgE = cycleData.length > 0
    ? cycleData.reduce((a, c) => a + c.E_Wh_kg, 0) / cycleData.length : 0;
  const avgP = cycleData.length > 0
    ? cycleData.reduce((a, c) => a + c.P_W_kg, 0) / cycleData.length : 0;
  const avgEta = cycleData.length > 0
    ? cycleData.reduce((a, c) => a + c.eta_pct, 0) / cycleData.length : 0;

  return {
    engine: 'js-fallback',
    time, voltage, current,
    cycleData,
    summary: {
      Cs_F_g: avgCs,
      E_Wh_kg: avgE,
      P_W_kg: avgP,
      eta_pct: avgEta,
      ESR: R_total,
      IR_drop: 2 * I * R_total,
    },
  };
}

// ── GCD Waveform Plot ───────────────────────────────────────────
function GCDPlot({ data }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !data) return;
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    const pad = { t: 12, r: 16, b: 36, l: 52 };
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    
    ctx.fillStyle = '#111214';
    ctx.fillRect(0, 0, W, H);

    const { time, voltage } = data;
    if (!time || time.length < 2) return;

    const xMin = 0, xMax = time[time.length - 1];
    const yMin = Math.min(...voltage) * 0.95;
    const yMax = Math.max(...voltage) * 1.05;

    // Grid
    ctx.strokeStyle = '#1e2024'; ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = pad.t + ph * i / 5;
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
      const x = pad.l + pw * i / 5;
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
    }

    ctx.strokeStyle = '#383c42'; ctx.lineWidth = 1;
    ctx.strokeRect(pad.l, pad.t, pw, ph);

    // Ticks
    ctx.fillStyle = '#6b7280'; ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (let i = 0; i <= 5; i++) {
      ctx.fillText((yMax - (yMax - yMin) * i / 5).toFixed(2), pad.l - 5, pad.t + ph * i / 5);
    }
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let i = 0; i <= 5; i++) {
      ctx.fillText((xMax * i / 5).toFixed(1), pad.l + pw * i / 5, pad.t + ph + 5);
    }

    ctx.fillStyle = '#9aa0a6'; ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Time (s)', pad.l + pw / 2, H - 4);
    ctx.save(); ctx.translate(12, pad.t + ph / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText('Voltage (V)', 0, 0);
    ctx.restore();

    // Draw — downsample if too many points
    const step = Math.max(1, Math.floor(time.length / 2000));
    ctx.strokeStyle = '#3ddc84'; ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < time.length; i += step) {
      const x = pad.l + (time[i] / xMax) * pw;
      const y = pad.t + ((yMax - voltage[i]) / (yMax - yMin)) * ph;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  }, [data]);

  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />;
}

// ── Main GCD Panel ──────────────────────────────────────────────
export default function GCDPanel() {
  const [params, setParams] = useState(DEFAULT);
  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);

  const update = (k, v) => setParams(p => ({ ...p, [k]: v }));
  const loadPreset = (name) => {
    const p = PRESETS[name];
    if (p) setParams(prev => ({ ...prev, ...p }));
  };

  const simulate = useCallback(async () => {
    setComputing(true);
    try {
      const api = window.raman?.api;
      if (api) {
        const res = await api.call('/api/simulate/gcd', params);
        setResult(res);
      } else {
        try {
          const res = await fetch('http://127.0.0.1:8000/api/v2/gcd', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params),
          });
          if (res.ok) { setResult(await res.json()); return; }
        } catch {}
        await new Promise(r => setTimeout(r, 50));
        setResult(simulateGCDLocal(params));
      }
    } catch {
      setResult(simulateGCDLocal(params));
    } finally {
      setComputing(false);
    }
  }, [params]);

  const exportCSV = useCallback(() => {
    if (!result?.time) return;
    let csv = 'Time_s,Voltage_V,Current_mA\n';
    const step = Math.max(1, Math.floor(result.time.length / 5000));
    for (let i = 0; i < result.time.length; i += step) {
      csv += `${result.time[i]?.toFixed(6) ?? ''},${result.voltage[i]?.toFixed(6) ?? ''},${result.current[i]?.toFixed(4) ?? ''}\n`;
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'gcd_data.csv'; a.click();
    URL.revokeObjectURL(url);
  }, [result]);

  return (
    <div className="simulation-layout animate-in">
      <div className="card" style={{ overflow: 'auto' }}>
        <div className="card-header">
          <div>
            <div className="card-title">GCD Parameters</div>
            <div className="card-subtitle">Galvanostatic charge-discharge</div>
          </div>
        </div>

        <div style={{ marginBottom: 10 }}>
          <div className="input-label" style={{ marginBottom: 4 }}>Presets</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {Object.keys(PRESETS).map(n => (
              <button key={n} className="btn btn-sm btn-secondary" style={{ fontSize: 9 }}
                onClick={() => loadPreset(n)}>{n}</button>
            ))}
          </div>
        </div>

        {[
          ['Cdl_F', 'Cdl (Double-layer)', 'F', 1e-6, 1, 1e-4],
          ['C_pseudo_F', 'Cpseudo', 'F', 0, 1, 1e-4],
          ['Rs_ohm', 'Rs (Solution)', 'Ω', 0.1, 100, 0.5],
          ['Rct_ohm', 'Rct (Charge transfer)', 'Ω', 0.1, 500, 1],
          ['current_mA', 'Current', 'mA', 0.01, 100, 0.1],
          ['active_mass_mg', 'Active Mass', 'mg', 0.01, 100, 0.1],
          ['V_min', 'V min', 'V', -1, 2, 0.05],
          ['V_max', 'V max', 'V', 0, 3, 0.05],
          ['n_cycles', 'Cycles', '', 1, 50, 1],
        ].map(([key, label, unit, min, max, step]) => (
          <div className="input-group" key={key}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="input-label">{label}</span>
              {unit && <span className="input-unit">{unit}</span>}
            </div>
            <input className="input-field" type="number"
              value={params[key]} min={min} max={max} step={step}
              onChange={e => update(key, parseFloat(e.target.value) || 0)} />
          </div>
        ))}

        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <button className="btn btn-primary btn-lg" style={{ flex: 1 }}
            onClick={simulate} disabled={computing}>
            {computing ? 'Computing...' : 'Run GCD'}
          </button>
          {result && <button className="btn btn-secondary btn-lg" onClick={exportCSV}>CSV</button>}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {result?.summary && (
          <div className="grid-4">
            {[
              [result.summary.Cs_F_g?.toFixed(1), 'Cs (F/g)'],
              [result.summary.E_Wh_kg?.toFixed(3), 'E (Wh/kg)'],
              [result.summary.P_W_kg?.toFixed(1), 'P (W/kg)'],
              [result.summary.eta_pct?.toFixed(1) + '%', 'Coul. Eff.'],
            ].map(([v, l], i) => (
              <div className="stat-card" key={i}>
                <div className="stat-value" style={{ fontSize: 16 }}>{v}</div>
                <div className="stat-label">{l}</div>
              </div>
            ))}
          </div>
        )}

        <div className="plot-container" style={{ flex: 1 }}>
          <div className="plot-header">
            <span className="plot-title">Charge-Discharge Waveform</span>
            {result?.engine && <span className="input-unit">engine: {result.engine}</span>}
          </div>
          <div className="plot-canvas">
            <GCDPlot data={result} />
          </div>
        </div>

        {result?.cycleData?.length > 0 && (
          <div className="card">
            <div className="card-title" style={{ marginBottom: 8 }}>Per-Cycle Analysis</div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cycle</th><th>Cs (F/g)</th><th>E (Wh/kg)</th>
                  <th>P (W/kg)</th><th>η (%)</th><th>t_dis (s)</th>
                </tr>
              </thead>
              <tbody>
                {result.cycleData.map(c => (
                  <tr key={c.cycle}>
                    <td className="mono">{c.cycle}</td>
                    <td className="mono">{c.Cs_F_g?.toFixed(2)}</td>
                    <td className="mono">{c.E_Wh_kg?.toFixed(4)}</td>
                    <td className="mono">{c.P_W_kg?.toFixed(1)}</td>
                    <td className="mono">{c.eta_pct?.toFixed(1)}</td>
                    <td className="mono">{c.t_discharge?.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
