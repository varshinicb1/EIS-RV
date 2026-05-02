import React, { useState, useCallback } from 'react';

const CATEGORIES = {
  capacitance:     { label: 'Capacitance',        units: ['F', 'mF', 'µF', 'nF', 'pF'] },
  specific_capacitance: { label: 'Specific Cap.', units: ['F/g', 'mF/g', 'F/kg'] },
  areal_capacitance:    { label: 'Areal Cap.',    units: ['F/cm²', 'µF/cm²', 'mF/cm²'] },
  current:         { label: 'Current',             units: ['A', 'mA', 'µA', 'nA'] },
  current_density: { label: 'Current Density',     units: ['A/cm²', 'mA/cm²', 'µA/cm²', 'A/m²'] },
  resistance:      { label: 'Resistance',          units: ['Ω', 'mΩ', 'kΩ', 'MΩ'] },
  asr:             { label: 'Area Resistance',     units: ['Ω·cm²', 'mΩ·cm²', 'kΩ·cm²'] },
  potential:       { label: 'Potential',            units: ['V', 'mV', 'µV'] },
  frequency:       { label: 'Frequency',           units: ['Hz', 'kHz', 'MHz', 'rad/s'] },
  concentration:   { label: 'Concentration',       units: ['M', 'mM', 'µM', 'nM', 'pM'] },
  diffusion:       { label: 'Diffusion Coeff.',    units: ['cm²/s', 'm²/s'] },
  energy_density:  { label: 'Energy Density',      units: ['Wh/kg', 'mWh/g', 'kWh/kg', 'J/g', 'kJ/kg'] },
  power_density:   { label: 'Power Density',       units: ['W/kg', 'mW/g', 'kW/kg'] },
};

// Client-side conversion (mirrors backend logic)
const FACTORS = {
  capacitance:     { F: 1, mF: 1e-3, 'µF': 1e-6, nF: 1e-9, pF: 1e-12 },
  specific_capacitance: { 'F/g': 1, 'mF/g': 1e-3, 'F/kg': 1e-3 },
  areal_capacitance:    { 'F/cm²': 1, 'µF/cm²': 1e-6, 'mF/cm²': 1e-3 },
  current:         { A: 1, mA: 1e-3, 'µA': 1e-6, nA: 1e-9 },
  current_density: { 'A/cm²': 1, 'mA/cm²': 1e-3, 'µA/cm²': 1e-6, 'A/m²': 1e-4 },
  resistance:      { 'Ω': 1, 'mΩ': 1e-3, 'kΩ': 1e3, 'MΩ': 1e6 },
  asr:             { 'Ω·cm²': 1, 'mΩ·cm²': 1e-3, 'kΩ·cm²': 1e3 },
  potential:       { V: 1, mV: 1e-3, 'µV': 1e-6 },
  frequency:       { Hz: 1, kHz: 1e3, MHz: 1e6, 'rad/s': 0.15915494309189535 },
  concentration:   { M: 1, mM: 1e-3, 'µM': 1e-6, nM: 1e-9, pM: 1e-12 },
  diffusion:       { 'cm²/s': 1, 'm²/s': 1e4 },
  energy_density:  { 'Wh/kg': 1, 'mWh/g': 1, 'kWh/kg': 1e3, 'J/g': 1/3.6, 'kJ/kg': 1/3.6 },
  power_density:   { 'W/kg': 1, 'mW/g': 1, 'kW/kg': 1e3 },
};

function convertLocal(value, from, to, category) {
  const f = FACTORS[category];
  if (!f || !f[from] || !f[to]) return null;
  return (value * f[from]) / f[to];
}

// ── Equations Section ─────────────────────────────────────────
function EquationCard({ title, description, fields, calculate, resultLabels }) {
  const [params, setParams] = useState(() => {
    const init = {};
    fields.forEach(f => { init[f.key] = f.default ?? 0; });
    return init;
  });
  const [result, setResult] = useState(null);

  const run = () => {
    const r = calculate(params);
    setResult(r);
  };

  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div className="card-header">
        <div>
          <div className="card-title">{title}</div>
          <div className="card-subtitle">{description}</div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        {fields.map(f => (
          <div className="input-group" key={f.key}>
            <span className="input-label">{f.label} <span className="input-unit">[{f.unit}]</span></span>
            <input className="input-field" type="number" step={f.step || 'any'}
              value={params[f.key]}
              onChange={e => setParams(p => ({ ...p, [f.key]: parseFloat(e.target.value) || 0 }))} />
          </div>
        ))}
      </div>
      <button className="btn btn-primary btn-sm" style={{ marginTop: 6 }} onClick={run}>
        Calculate
      </button>
      {result && (
        <div className="grid-3" style={{ marginTop: 8 }}>
          {resultLabels.map(r => (
            <div className="stat-card" key={r.key}>
              <div className="stat-value" style={{ fontSize: 14 }}>
                {typeof result[r.key] === 'number' ? result[r.key].toExponential(3) : result[r.key]}
              </div>
              <div className="stat-label">{r.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ToolkitPanel() {
  const [category, setCategory] = useState('capacitance');
  const [value, setValue] = useState(1.0);
  const [fromUnit, setFromUnit] = useState('F');
  const [toUnit, setToUnit] = useState('µF');
  const [convResult, setConvResult] = useState(null);

  const doConvert = useCallback(() => {
    const result = convertLocal(value, fromUnit, toUnit, category);
    setConvResult(result);
  }, [value, fromUnit, toUnit, category]);

  const catInfo = CATEGORIES[category];

  return (
    <div className="simulation-layout animate-in">
      <div className="card" style={{ overflow: 'auto' }}>
        {/* Unit Converter */}
        <div className="card-header">
          <div>
            <div className="card-title">Unit Converter</div>
            <div className="card-subtitle">Electrochemistry unit conversions</div>
          </div>
        </div>

        <div className="input-group">
          <span className="input-label">Category</span>
          <select className="input-field" value={category}
            onChange={e => {
              const c = e.target.value;
              setCategory(c);
              const units = CATEGORIES[c].units;
              setFromUnit(units[0]);
              setToUnit(units[1] || units[0]);
              setConvResult(null);
            }}>
            {Object.entries(CATEGORIES).map(([key, val]) => (
              <option key={key} value={key}>{val.label}</option>
            ))}
          </select>
        </div>

        <div className="input-group">
          <span className="input-label">Value</span>
          <input className="input-field" type="number" step="any"
            value={value} onChange={e => setValue(parseFloat(e.target.value) || 0)} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 6, alignItems: 'end', marginBottom: 8 }}>
          <div className="input-group" style={{ marginBottom: 0 }}>
            <span className="input-label">From</span>
            <select className="input-field" value={fromUnit}
              onChange={e => setFromUnit(e.target.value)}>
              {catInfo.units.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <span style={{ color: 'var(--text-tertiary)', padding: '0 4px', fontSize: 14 }}>→</span>
          <div className="input-group" style={{ marginBottom: 0 }}>
            <span className="input-label">To</span>
            <select className="input-field" value={toUnit}
              onChange={e => setToUnit(e.target.value)}>
              {catInfo.units.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
        </div>

        <button className="btn btn-primary" style={{ width: '100%' }} onClick={doConvert}>
          Convert
        </button>

        {convResult !== null && (
          <div className="stat-card" style={{ marginTop: 10, textAlign: 'center' }}>
            <div className="stat-value" style={{ fontSize: 18 }}>
              {Math.abs(convResult) > 1e6 || (Math.abs(convResult) < 1e-3 && convResult !== 0)
                ? convResult.toExponential(4)
                : convResult.toPrecision(6)}
            </div>
            <div className="stat-label">{toUnit}</div>
          </div>
        )}

        {/* Quick Reference */}
        <div style={{ marginTop: 16, borderTop: '1px solid var(--border-primary)', paddingTop: 10 }}>
          <div className="card-title" style={{ fontSize: 11, marginBottom: 6 }}>Quick Reference</div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.8, fontFamily: 'var(--font-data)' }}>
            <div>F = 96485.33 C/mol</div>
            <div>R = 8.3145 J/(mol·K)</div>
            <div>RT/F (25°C) = 25.69 mV</div>
            <div>1 eV = 96.485 kJ/mol</div>
            <div>1 Wh = 3600 J</div>
          </div>
        </div>
      </div>

      {/* Right panel — Equations */}
      <div style={{ overflow: 'auto' }}>
        <EquationCard
          title="Randles-Ševčík Equation"
          description="Peak current in cyclic voltammetry (25°C)"
          fields={[
            { key: 'n', label: 'n (electrons)', unit: '—', default: 1, step: 1 },
            { key: 'A', label: 'Area', unit: 'cm²', default: 0.0707, step: 0.001 },
            { key: 'D', label: 'Diffusion coeff.', unit: 'cm²/s', default: 7.6e-6, step: 1e-7 },
            { key: 'C', label: 'Concentration', unit: 'M', default: 0.005, step: 0.001 },
            { key: 'v', label: 'Scan rate', unit: 'V/s', default: 0.05, step: 0.01 },
          ]}
          calculate={p => {
            const ip = 2.69e5 * Math.pow(p.n, 1.5) * p.A * Math.sqrt(p.D) * p.C * Math.sqrt(p.v);
            return { ip_A: ip, ip_mA: ip * 1e3, ip_uA: ip * 1e6 };
          }}
          resultLabels={[
            { key: 'ip_A', label: 'ip (A)' },
            { key: 'ip_mA', label: 'ip (mA)' },
            { key: 'ip_uA', label: 'ip (µA)' },
          ]}
        />

        <EquationCard
          title="Nernst Equation"
          description="Equilibrium potential E = E⁰ + (RT/nF) ln(Cox/Cred)"
          fields={[
            { key: 'E0', label: 'E⁰', unit: 'V', default: 0.34, step: 0.01 },
            { key: 'n', label: 'n (electrons)', unit: '—', default: 2, step: 1 },
            { key: 'Cox', label: '[Ox]', unit: 'M', default: 0.01, step: 0.001 },
            { key: 'Cred', label: '[Red]', unit: 'M', default: 0.001, step: 0.001 },
            { key: 'T', label: 'Temperature', unit: 'K', default: 298.15, step: 1 },
          ]}
          calculate={p => {
            if (p.Cox <= 0 || p.Cred <= 0) return { E_V: 'N/A', E_mV: 'N/A', RT_nF: 'N/A' };
            const RT_nF = (8.3145 * p.T) / (p.n * 96485.33);
            const E = p.E0 + RT_nF * Math.log(p.Cox / p.Cred);
            return { E_V: E, E_mV: E * 1000, RT_nF: RT_nF * 1000 };
          }}
          resultLabels={[
            { key: 'E_V', label: 'E (V)' },
            { key: 'E_mV', label: 'E (mV)' },
            { key: 'RT_nF', label: 'RT/nF (mV)' },
          ]}
        />

        <EquationCard
          title="Cottrell Equation"
          description="Current in chronoamperometry: i = nFAD½C / (πt)½"
          fields={[
            { key: 'n', label: 'n (electrons)', unit: '—', default: 1, step: 1 },
            { key: 'A', label: 'Area', unit: 'cm²', default: 0.0707, step: 0.001 },
            { key: 'D', label: 'Diffusion coeff.', unit: 'cm²/s', default: 7.6e-6, step: 1e-7 },
            { key: 'C', label: 'Concentration', unit: 'M', default: 0.005, step: 0.001 },
            { key: 't', label: 'Time', unit: 's', default: 1.0, step: 0.1 },
          ]}
          calculate={p => {
            const F = 96485.33;
            const i = p.n * F * p.A * Math.sqrt(p.D) * p.C / Math.sqrt(Math.PI * p.t);
            return { i_A: i, i_mA: i * 1e3, i_uA: i * 1e6 };
          }}
          resultLabels={[
            { key: 'i_A', label: 'i (A)' },
            { key: 'i_mA', label: 'i (mA)' },
            { key: 'i_uA', label: 'i (µA)' },
          ]}
        />

        <EquationCard
          title="Specific Capacitance (from GCD)"
          description="Cs = I × Δt / (m × ΔV)"
          fields={[
            { key: 'I', label: 'Current', unit: 'A', default: 0.001, step: 0.0001 },
            { key: 'dt', label: 'Discharge time', unit: 's', default: 100, step: 1 },
            { key: 'm', label: 'Active mass', unit: 'g', default: 0.001, step: 0.0001 },
            { key: 'dV', label: 'Voltage window', unit: 'V', default: 1.0, step: 0.1 },
          ]}
          calculate={p => {
            const Cs = (p.I * p.dt) / (p.m * p.dV);
            const E = 0.5 * Cs * p.dV * p.dV / 3.6;
            const P = p.dt > 0 ? E * 3600 / p.dt : 0;
            return { Cs_Fg: Cs, E_Whkg: E, P_Wkg: P };
          }}
          resultLabels={[
            { key: 'Cs_Fg', label: 'Cs (F/g)' },
            { key: 'E_Whkg', label: 'E (Wh/kg)' },
            { key: 'P_Wkg', label: 'P (W/kg)' },
          ]}
        />
      </div>
    </div>
  );
}
