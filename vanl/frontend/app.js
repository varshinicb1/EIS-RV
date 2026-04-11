/**
 * VANL — Virtual Autonomous Nanomaterials Lab
 * Digital Twin for Printed Electronics
 *
 * ALL data comes from physics engines via API.
 * NO fabricated values. NO placeholder data.
 */

const API = window.location.origin + '/api';
const PE_API = window.location.origin + '/api/pe';

// ─── Plotly defaults ───
function theme(extra = {}) {
    return {
        paper_bgcolor: '#0d1117',
        plot_bgcolor: '#0d1117',
        font: { family: 'IBM Plex Mono, monospace', color: '#8b949e', size: 11 },
        margin: { t: 10, b: 42, l: 56, r: 16 },
        xaxis: {
            gridcolor: '#21262d', zerolinecolor: '#30363d',
            linecolor: '#30363d', tickfont: { size: 10 },
            ...extra.xaxis,
        },
        yaxis: {
            gridcolor: '#21262d', zerolinecolor: '#30363d',
            linecolor: '#30363d', tickfont: { size: 10 },
            ...extra.yaxis,
        },
        showlegend: extra.showlegend || false,
        ...extra,
    };
}

const PCFG = { displayModeBar: false, responsive: true };

let materialsCache = [];

// ═══════════════════════════════════════════════════════════════════
//   INIT
// ═══════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupSliderSync();
    checkHealth();
    loadMaterialsDB();
});

function setupTabs() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        });
    });
}

function setupSliderSync() {
    const pairs = [
        ['eis-Rs', 'eis-Rs-val', 'linear'],
        ['eis-Rct', 'eis-Rct-val', 'linear'],
        ['eis-Cdl', 'eis-Cdl-val', 'log'],
        ['eis-sigma', 'eis-sigma-val', 'linear'],
        ['eis-ncpe', 'eis-ncpe-val', 'linear'],
        ['cv-Ef', 'cv-Ef-val', 'linear'],
        ['cv-k0', 'cv-k0-val', 'log'],
        ['cv-alpha', 'cv-alpha-val', 'linear'],
        ['cv-sr', 'cv-sr-val', 'linear'],
        ['gcd-Rs', 'gcd-Rs-val', 'linear'],
        ['gcd-Rct', 'gcd-Rct-val', 'linear'],
        ['ink-loading', 'ink-loading-val', 'linear'],
    ];

    pairs.forEach(([sliderId, numId, mode]) => {
        const slider = document.getElementById(sliderId);
        const num = document.getElementById(numId);
        if (!slider || !num) return;

        slider.addEventListener('input', () => {
            if (mode === 'log') {
                num.value = parseFloat(Math.pow(10, parseFloat(slider.value)).toPrecision(3));
            } else {
                num.value = slider.value;
            }
        });

        num.addEventListener('change', () => {
            if (mode === 'log') {
                slider.value = Math.log10(parseFloat(num.value) || 1e-5);
            } else {
                slider.value = num.value;
            }
        });
    });
}

async function checkHealth() {
    try {
        const r = await fetch(API + '/health');
        const d = await r.json();
        const badge = document.getElementById('api-status');
        badge.textContent = 'API Online';
        badge.className = 'status-badge online';
    } catch {
        const badge = document.getElementById('api-status');
        badge.textContent = 'API Offline';
        badge.className = 'status-badge offline';
    }
}

// ═══════════════════════════════════════════════════════════════════
//   MATERIALS DB
// ═══════════════════════════════════════════════════════════════════

async function loadMaterialsDB() {
    try {
        const r = await fetch(API + '/materials/full');
        const d = await r.json();
        materialsCache = d.materials;
        document.getElementById('material-count').textContent = d.count + ' materials';
        document.getElementById('mat-db-count').textContent = d.count + ' materials';

        const select = document.getElementById('mat-category-filter');
        if (d.categories) {
            Object.entries(d.categories).sort().forEach(([cat, count]) => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = `${cat} (${count})`;
                select.appendChild(opt);
            });
        }

        renderMaterialsTable(materialsCache);
        populateCompSelects();
    } catch (e) {
        console.error('Failed to load materials:', e);
    }
}

function renderMaterialsTable(materials) {
    const tbody = document.getElementById('materials-tbody');
    tbody.innerHTML = '';
    materials.forEach(m => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${m.name}</td>
            <td>${m.formula}</td>
            <td><span class="cat-badge cat-${m.category}">${m.category}</span></td>
            <td>${fmt(m.conductivity_S_m)}</td>
            <td>${fmt(m.theoretical_surface_area_m2_g)}</td>
            <td>${fmt(m.density_g_cm3)}</td>
            <td>${fmt(m.bandgap_eV)}</td>
            <td>${fmt(m.theoretical_capacitance_F_g)}</td>
            <td>${m.cost_per_gram_USD != null ? '$' + m.cost_per_gram_USD.toFixed(2) : '—'}</td>
            <td>${m.pseudocapacitive ? 'Yes' : '—'}</td>
            <td class="sources-cell">${(m.source_refs || []).slice(0, 2).join(', ') || '—'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function filterMaterials() {
    const cat = document.getElementById('mat-category-filter').value;
    const pseudo = document.getElementById('mat-pseudocap-filter').checked;
    let filtered = materialsCache;
    if (cat) filtered = filtered.filter(m => m.category === cat);
    if (pseudo) filtered = filtered.filter(m => m.pseudocapacitive);
    renderMaterialsTable(filtered);
}

function populateCompSelects() {
    document.querySelectorAll('.comp-mat').forEach(sel => {
        const current = sel.value;
        sel.innerHTML = '';
        materialsCache.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.name;
            opt.textContent = `${m.name} (${m.formula})`;
            sel.appendChild(opt);
        });
        if (current) sel.value = current;
    });
}

// ═══════════════════════════════════════════════════════════════════
//   EIS SIMULATION
// ═══════════════════════════════════════════════════════════════════

let eisData = null;
let eisPlotMode = 'nyquist';

async function runEIS() {
    const btn = document.getElementById('btn-eis-run');
    btn.disabled = true; btn.classList.add('loading');
    try {
        const body = {
            Rs: parseFloat(document.getElementById('eis-Rs-val').value),
            Rct: parseFloat(document.getElementById('eis-Rct-val').value),
            Cdl: parseFloat(document.getElementById('eis-Cdl-val').value),
            sigma_warburg: parseFloat(document.getElementById('eis-sigma-val').value),
            n_cpe: parseFloat(document.getElementById('eis-ncpe-val').value),
            freq_min: parseFloat(document.getElementById('eis-fmin').value),
            freq_max: parseFloat(document.getElementById('eis-fmax').value),
            n_points: 100,
        };
        const r = await fetch(API + '/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        eisData = await r.json();
        plotEIS();
        showEISResults();
    } catch (e) { alert('EIS simulation failed: ' + e.message); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
}

function plotEIS() {
    if (!eisData) return;
    const div = document.getElementById('eis-plot');
    if (eisPlotMode === 'nyquist') {
        const negImag = eisData.Z_imag ? eisData.Z_imag.map(v => -v) : (eisData.nyquist ? eisData.nyquist.y : []);
        Plotly.newPlot(div, [{ x: eisData.Z_real || (eisData.nyquist ? eisData.nyquist.x : []), y: negImag, mode: 'lines+markers', marker: { size: 3, color: '#58a6ff' }, line: { color: '#58a6ff', width: 1.5 } }], theme({ xaxis: { title: "Z' (\u03a9)" }, yaxis: { title: "-Z'' (\u03a9)", scaleanchor: 'x' } }), PCFG);
    } else if (eisPlotMode === 'bode-mag') {
        Plotly.newPlot(div, [{ x: eisData.frequencies, y: eisData.Z_magnitude, mode: 'lines+markers', marker: { size: 3, color: '#d29922' }, line: { color: '#d29922', width: 1.5 } }], theme({ xaxis: { title: 'Frequency (Hz)', type: 'log' }, yaxis: { title: '|Z| (\u03a9)', type: 'log' } }), PCFG);
    } else if (eisPlotMode === 'bode-phase') {
        Plotly.newPlot(div, [{ x: eisData.frequencies, y: eisData.Z_phase, mode: 'lines+markers', marker: { size: 3, color: '#3fb950' }, line: { color: '#3fb950', width: 1.5 } }], theme({ xaxis: { title: 'Frequency (Hz)', type: 'log' }, yaxis: { title: 'Phase (\u00b0)' } }), PCFG);
    }
}

function switchEISPlot(mode) { eisPlotMode = mode; document.querySelectorAll('#tab-eis .plot-tab').forEach(t => t.classList.remove('active')); event.target.classList.add('active'); plotEIS(); }

function showEISResults() {
    if (!eisData) return;
    const p = eisData.params || eisData.parameters || {};
    document.getElementById('eis-results').innerHTML = `
        <div class="result-row"><span class="result-label">R_s</span><span class="result-value">${fmt(p.Rs_ohm || p.Rs)} \u03a9</span></div>
        <div class="result-row"><span class="result-label">R_ct</span><span class="result-value">${fmt(p.Rct_ohm || p.Rct)} \u03a9</span></div>
        <div class="result-row"><span class="result-label">C_dl</span><span class="result-value">${sci(p.Cdl_F || p.Cdl)} F</span></div>
        <div class="result-row"><span class="result-label">\u03c3_W</span><span class="result-value">${fmt(p.sigma_warburg)} \u03a9\u00b7s^{-1/2}</span></div>
        <div class="result-row"><span class="result-label">n_CPE</span><span class="result-value">${fmt(p.n_cpe)}</span></div>
        <div class="result-row"><span class="result-label">Points</span><span class="result-value">${eisData.frequencies?.length || 0}</span></div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
//   CV SIMULATION
// ═══════════════════════════════════════════════════════════════════

let cvData = null;
let cvPlotMode = 'cv';

async function runCV() {
    const btn = document.getElementById('btn-cv-run');
    btn.disabled = true; btn.classList.add('loading');
    try {
        const body = {
            electrode_area_cm2: parseFloat(document.getElementById('cv-area').value),
            E_formal_V: parseFloat(document.getElementById('cv-Ef-val').value),
            k0_cm_s: parseFloat(document.getElementById('cv-k0-val').value),
            alpha: parseFloat(document.getElementById('cv-alpha-val').value),
            C_ox_M: parseFloat(document.getElementById('cv-Cox').value) * 1e-3,
            D_ox_cm2_s: parseFloat(document.getElementById('cv-Dox').value),
            E_start_V: parseFloat(document.getElementById('cv-Estart').value),
            E_vertex_V: parseFloat(document.getElementById('cv-Evertex').value),
            scan_rate_V_s: parseFloat(document.getElementById('cv-sr-val').value) * 1e-3,
        };
        const r = await fetch(API + '/cv/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        cvData = await r.json();
        plotCV(); showCVResults();
    } catch (e) { alert('CV simulation failed: ' + e.message); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
}

function plotCV() {
    if (!cvData) return;
    const div = document.getElementById('cv-plot');
    if (cvPlotMode === 'cv') {
        const i_mA = cvData.i_total.map(v => v * 1e3);
        Plotly.newPlot(div, [{ x: cvData.E, y: i_mA, mode: 'lines', line: { color: '#58a6ff', width: 1.5 } }], theme({ xaxis: { title: 'E (V)' }, yaxis: { title: 'i (mA)' } }), PCFG);
    } else if (cvPlotMode === 'faradaic') {
        Plotly.newPlot(div, [
            { x: cvData.E, y: cvData.i_faradaic.map(v => v * 1e3), mode: 'lines', line: { color: '#58a6ff', width: 1.5 }, name: 'Faradaic' },
            { x: cvData.E, y: cvData.i_capacitive.map(v => v * 1e3), mode: 'lines', line: { color: '#d29922', width: 1, dash: 'dot' }, name: 'Capacitive' },
        ], theme({ xaxis: { title: 'E (V)' }, yaxis: { title: 'i (mA)' }, showlegend: true, legend: { x: 0.02, y: 0.98, font: { size: 10 } } }), PCFG);
    }
}

function switchCVPlot(mode) { cvPlotMode = mode; document.querySelectorAll('#tab-cv .plot-tab').forEach(t => t.classList.remove('active')); event.target.classList.add('active'); plotCV(); }

function showCVResults() {
    if (!cvData || !cvData.analysis) return;
    const a = cvData.analysis;
    const rs = cvData.randles_sevcik || {};
    const revClass = a.reversibility?.includes('reversible') && !a.reversibility?.includes('irreversible') ? 'good' : a.reversibility?.includes('quasi') ? 'warn' : 'bad';
    document.getElementById('cv-results').innerHTML = `
        <div class="result-row"><span class="result-label">E_pa</span><span class="result-value">${a.E_pa_V?.toFixed(3) || '—'} V</span></div>
        <div class="result-row"><span class="result-label">E_pc</span><span class="result-value">${a.E_pc_V?.toFixed(3) || '—'} V</span></div>
        <div class="result-row"><span class="result-label">\u0394E_p</span><span class="result-value ${a.delta_Ep_mV < 65 ? 'good' : a.delta_Ep_mV < 200 ? 'warn' : 'bad'}">${a.delta_Ep_mV?.toFixed(1) || '—'} mV</span></div>
        <div class="result-row"><span class="result-label">E_{1/2}</span><span class="result-value">${a.E_half_V?.toFixed(3) || '—'} V</span></div>
        <div class="result-row"><span class="result-label">i_pa</span><span class="result-value">${a.i_pa_mA?.toFixed(4) || '—'} mA</span></div>
        <div class="result-row"><span class="result-label">|i_pa/i_pc|</span><span class="result-value">${a.ip_ratio?.toFixed(2) || '—'}</span></div>
        <div class="result-row"><span class="result-label">Reversibility</span><span class="result-value ${revClass}">${a.reversibility || '—'}</span></div>
        <div class="result-row"><span class="result-label">i_p (R-S)</span><span class="result-value">${sci(rs.i_p_theoretical_A)} A</span></div>
        <div class="result-row"><span class="result-label">\u03b7_coulombic</span><span class="result-value">${a.coulombic_efficiency_pct?.toFixed(1) || '—'}%</span></div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
//   GCD SIMULATION
// ═══════════════════════════════════════════════════════════════════

async function runGCD() {
    const btn = document.getElementById('btn-gcd-run');
    btn.disabled = true; btn.classList.add('loading');
    try {
        const body = {
            Cdl_F: parseFloat(document.getElementById('gcd-Cdl').value) * 1e-3,
            C_pseudo_F: parseFloat(document.getElementById('gcd-Cpseudo').value) * 1e-3,
            Rs_ohm: parseFloat(document.getElementById('gcd-Rs-val').value),
            Rct_ohm: parseFloat(document.getElementById('gcd-Rct-val').value),
            current_A: parseFloat(document.getElementById('gcd-I').value) * 1e-3,
            active_mass_mg: parseFloat(document.getElementById('gcd-mass').value),
            V_min: parseFloat(document.getElementById('gcd-Vmin').value),
            V_max: parseFloat(document.getElementById('gcd-Vmax').value),
            n_cycles: parseInt(document.getElementById('gcd-cycles').value),
        };
        const r = await fetch(API + '/gcd/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await r.json();
        plotGCD(data); showGCDResults(data);
    } catch (e) { alert('GCD simulation failed: ' + e.message); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
}

function plotGCD(data) {
    Plotly.newPlot(document.getElementById('gcd-plot'), [{ x: data.time_s, y: data.voltage_V, mode: 'lines', line: { color: '#3fb950', width: 1.5 } }], theme({ xaxis: { title: 'Time (s)' }, yaxis: { title: 'Voltage (V)' } }), PCFG);
}

function showGCDResults(data) {
    const s = data.summary;
    let cycleRows = '';
    (data.cycle_data || []).forEach(c => {
        cycleRows += `<div class="result-row"><span class="result-label">Cycle ${c.cycle}</span><span class="result-value">${c.specific_capacitance_F_g.toFixed(1)} F/g | \u03b7=${c.coulombic_efficiency_pct.toFixed(0)}%</span></div>`;
    });
    document.getElementById('gcd-results').innerHTML = `
        <div class="result-row"><span class="result-label">C_specific</span><span class="result-value good">${s.specific_capacitance_F_g} F/g</span></div>
        <div class="result-row"><span class="result-label">Energy</span><span class="result-value">${s.energy_density_Wh_kg} Wh/kg</span></div>
        <div class="result-row"><span class="result-label">Power</span><span class="result-value">${s.power_density_W_kg} W/kg</span></div>
        <div class="result-row"><span class="result-label">\u03b7_coulombic</span><span class="result-value ${s.coulombic_efficiency_pct > 95 ? 'good' : 'warn'}">${s.coulombic_efficiency_pct}%</span></div>
        <div class="result-row"><span class="result-label">IR Drop</span><span class="result-value">${(s.IR_drop_V * 1000).toFixed(1)} mV</span></div>
        <div class="result-row"><span class="result-label">Retention</span><span class="result-value ${s.capacity_retention_pct > 95 ? 'good' : 'warn'}">${s.capacity_retention_pct}%</span></div>
        ${cycleRows}
    `;
}

// ═══════════════════════════════════════════════════════════════════
//   INK ENGINE
// ═══════════════════════════════════════════════════════════════════

let inkData = null;
let inkPlotMode = 'rheology';

async function runInkSim() {
    const btn = document.getElementById('btn-ink-run');
    btn.disabled = true; btn.classList.add('loading');
    try {
        const body = {
            filler_material: document.getElementById('ink-filler').value,
            filler_loading_wt_pct: parseFloat(document.getElementById('ink-loading-val').value),
            particle_size_nm: parseFloat(document.getElementById('ink-psize').value),
            aspect_ratio: parseFloat(document.getElementById('ink-ar').value),
            primary_solvent: document.getElementById('ink-solvent').value,
            print_method: document.getElementById('ink-method').value,
            binder_type: document.getElementById('ink-binder').value,
            binder_wt_pct: parseFloat(document.getElementById('ink-binder-pct').value),
            surfactant_wt_pct: parseFloat(document.getElementById('ink-surfactant-pct').value),
        };
        const [simR, rheoR] = await Promise.all([
            fetch(PE_API + '/ink/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
            fetch(PE_API + '/ink/rheology', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
        ]);
        inkData = { props: await simR.json(), rheology: await rheoR.json() };
        plotInk();
        showInkResults();
    } catch (e) { alert('Ink simulation failed: ' + e.message); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
}

function plotInk() {
    if (!inkData) return;
    const div = document.getElementById('ink-plot');
    if (inkPlotMode === 'rheology' && inkData.rheology) {
        const r = inkData.rheology;
        Plotly.newPlot(div, [{ x: r.shear_rate, y: r.viscosity_Pas.map(v => v * 1e3), mode: 'lines', line: { color: '#58a6ff', width: 2 }, name: 'Viscosity' }], theme({
            xaxis: { title: 'Shear Rate (s⁻¹)', type: 'log' },
            yaxis: { title: 'Viscosity (mPa·s)', type: 'log' },
            shapes: r.print_window ? [{
                type: 'rect', xref: 'x', yref: 'paper',
                x0: r.print_window.shear_rate_min, x1: r.print_window.shear_rate_max,
                y0: 0, y1: 1, fillcolor: 'rgba(63,185,80,0.08)',
                line: { color: 'rgba(63,185,80,0.3)', dash: 'dot' },
            }] : [],
        }), PCFG);
    } else if (inkPlotMode === 'percolation') {
        // Quick percolation plot from properties
        const p = inkData.props;
        const phi_c = p.percolation_threshold_vol_pct;
        const x = [], y = [];
        for (let i = 0; i <= 30; i++) {
            const phi = i * 0.5;
            x.push(phi);
            y.push(phi > phi_c ? Math.pow(10, (phi - phi_c) * 0.3) : 1e-10);
        }
        Plotly.newPlot(div, [{ x, y, mode: 'lines+markers', marker: { size: 3, color: '#d29922' }, line: { color: '#d29922', width: 2 } }], theme({
            xaxis: { title: 'Filler Loading (vol%)' },
            yaxis: { title: 'Conductivity (S/m)', type: 'log' },
            shapes: [{ type: 'line', x0: phi_c, x1: phi_c, y0: 0, y1: 1, yref: 'paper', line: { color: '#f85149', dash: 'dash', width: 1.5 } }],
        }), PCFG);
    } else if (inkPlotMode === 'printability') {
        const p = inkData.props;
        const Z = p.Z_parameter;
        const cats = ['Viscosity', 'Surface Tension', 'Z-Parameter', 'Stability', 'Overall'];
        const vals = [
            Math.min(p.viscosity_mPas / 50, 1),
            Math.min(p.surface_tension_mN_m / 72, 1),
            Z > 1 && Z < 10 ? 0.9 : Z > 0.5 ? 0.5 : 0.2,
            Math.min(p.shelf_life_days / 90, 1),
            p.printability_score,
        ];
        Plotly.newPlot(div, [{ type: 'scatterpolar', r: vals.concat([vals[0]]), theta: cats.concat([cats[0]]), fill: 'toself', fillcolor: 'rgba(88,166,255,0.15)', line: { color: '#58a6ff', width: 2 } }], {
            polar: { radialaxis: { visible: true, range: [0, 1], gridcolor: '#21262d', linecolor: '#30363d' }, angularaxis: { gridcolor: '#21262d', linecolor: '#30363d' }, bgcolor: '#0d1117' },
            paper_bgcolor: '#0d1117', font: { family: 'IBM Plex Mono', color: '#8b949e', size: 10 }, margin: { t: 20, b: 20, l: 60, r: 60 }, showlegend: false,
        }, PCFG);
    }
}

function switchInkPlot(mode) { inkPlotMode = mode; document.querySelectorAll('#tab-ink .plot-tab').forEach(t => t.classList.remove('active')); event.target.classList.add('active'); plotInk(); }

function showInkResults() {
    if (!inkData) return;
    const p = inkData.props;
    document.getElementById('ink-results').innerHTML = `
        <div class="result-row"><span class="result-label">Viscosity</span><span class="result-value">${p.viscosity_mPas} mPa·s</span></div>
        <div class="result-row"><span class="result-label">Surface Tension</span><span class="result-value">${p.surface_tension_mN_m} mN/m</span></div>
        <div class="result-row"><span class="result-label">Z-Parameter</span><span class="result-value ${p.Z_parameter >= 1 && p.Z_parameter <= 10 ? 'good' : 'warn'}">${p.Z_parameter}</span></div>
        <div class="result-row"><span class="result-label">Printability</span><span class="result-value ${p.printability_score > 0.7 ? 'good' : p.printability_score > 0.3 ? 'warn' : 'bad'}">${(p.printability_score * 100).toFixed(0)}%</span></div>
        <div class="result-row"><span class="result-label">Sheet Resistance</span><span class="result-value">${p.sheet_resistance_ohm_sq < 1e6 ? p.sheet_resistance_ohm_sq.toFixed(1) + ' Ω/□' : '>1MΩ/□'}</span></div>
        <div class="result-row"><span class="result-label">Conductivity</span><span class="result-value">${sci(p.conductivity_S_m)} S/m</span></div>
        <div class="result-row"><span class="result-label">Dry Film</span><span class="result-value">${p.dry_film_thickness_um} µm</span></div>
        <div class="result-row"><span class="result-label">Percolation</span><span class="result-value ${p.above_percolation ? 'good' : 'bad'}">${p.above_percolation ? 'Above' : 'Below'} (φ_c=${p.percolation_threshold_vol_pct}%)</span></div>
        <div class="result-row"><span class="result-label">Shelf Life</span><span class="result-value">${p.shelf_life_days} days</span></div>
        <div class="result-row"><span class="result-label">Drying Time</span><span class="result-value">${p.drying_time_s} s</span></div>
        <div class="result-row"><span class="result-label">Coffee Ring</span><span class="result-value ${p.coffee_ring_risk === 'low' ? 'good' : p.coffee_ring_risk === 'medium' ? 'warn' : 'bad'}">${p.coffee_ring_risk}</span></div>
    `;
    // Recommendations
    let recHtml = '';
    (p.recommendations || []).forEach(r => { recHtml += `<div class="result-row"><span class="result-label">💡</span><span class="result-value" style="color:#d29922;font-size:10px;">${r}</span></div>`; });
    (p.warnings || []).forEach(w => { recHtml += `<div class="result-row"><span class="result-label">⚠️</span><span class="result-value" style="color:#f85149;font-size:10px;">${w}</span></div>`; });
    document.getElementById('ink-recommendations').innerHTML = recHtml;
}

// ═══════════════════════════════════════════════════════════════════
//   SUPERCAPACITOR DEVICE
// ═══════════════════════════════════════════════════════════════════

let scData = null;
let scPlotMode = 'ragone';

async function runSupercap() {
    const btn = document.getElementById('btn-sc-run');
    btn.disabled = true; btn.classList.add('loading');
    try {
        const body = {
            material: document.getElementById('sc-material').value,
            capacitance_F_g: parseFloat(document.getElementById('sc-cap').value),
            mass_mg: parseFloat(document.getElementById('sc-mass').value),
            area_mm2: parseFloat(document.getElementById('sc-area').value),
            thickness_um: parseFloat(document.getElementById('sc-thick').value),
            electrolyte: document.getElementById('sc-elec').value,
            voltage_V: parseFloat(document.getElementById('sc-voltage').value),
        };
        const r = await fetch(PE_API + '/supercap/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        scData = await r.json();
        plotSC(); showSCResults();
    } catch (e) { alert('Supercap simulation failed: ' + e.message); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
}

function plotSC() {
    if (!scData) return;
    const div = document.getElementById('sc-plot');
    if (scPlotMode === 'ragone' && scData.ragone) {
        Plotly.newPlot(div, [{ x: scData.ragone.P_W_kg, y: scData.ragone.E_Wh_kg, mode: 'lines+markers', marker: { size: 4, color: '#d29922' }, line: { color: '#d29922', width: 2 } }], theme({ xaxis: { title: 'Power Density (W/kg)', type: 'log' }, yaxis: { title: 'Energy Density (Wh/kg)', type: 'log' } }), PCFG);
    } else if (scPlotMode === 'gcd' && scData.gcd) {
        Plotly.newPlot(div, [{ x: scData.gcd.time_s, y: scData.gcd.voltage_V, mode: 'lines', line: { color: '#3fb950', width: 1.5 } }], theme({ xaxis: { title: 'Time (s)' }, yaxis: { title: 'Voltage (V)' } }), PCFG);
    } else if (scPlotMode === 'eis' && scData.eis) {
        Plotly.newPlot(div, [{ x: scData.eis.Z_real, y: scData.eis.Z_imag_neg, mode: 'lines+markers', marker: { size: 3, color: '#58a6ff' }, line: { color: '#58a6ff', width: 1.5 } }], theme({ xaxis: { title: "Z' (Ω)" }, yaxis: { title: "-Z'' (Ω)" } }), PCFG);
    }
}

function switchSCPlot(mode) { scPlotMode = mode; document.querySelectorAll('#tab-supercap .plot-tab').forEach(t => t.classList.remove('active')); event.target.classList.add('active'); plotSC(); }

function showSCResults() {
    if (!scData) return;
    document.getElementById('sc-results').innerHTML = `
        <div class="result-row"><span class="result-label">C_device</span><span class="result-value good">${scData.C_device_mF} mF</span></div>
        <div class="result-row"><span class="result-label">C_specific</span><span class="result-value">${scData.C_specific_F_g} F/g</span></div>
        <div class="result-row"><span class="result-label">C_areal</span><span class="result-value">${scData.C_areal_mF_cm2} mF/cm²</span></div>
        <div class="result-row"><span class="result-label">Energy</span><span class="result-value">${scData.energy_Wh_kg} Wh/kg</span></div>
        <div class="result-row"><span class="result-label">Power</span><span class="result-value">${scData.power_W_kg} W/kg</span></div>
        <div class="result-row"><span class="result-label">ESR</span><span class="result-value">${scData.ESR_ohm} Ω</span></div>
        <div class="result-row"><span class="result-label">Retention @1k</span><span class="result-value ${scData.retention_1000_cycles_pct > 90 ? 'good' : 'warn'}">${scData.retention_1000_cycles_pct}%</span></div>
        <div class="result-row"><span class="result-label">Retention @10k</span><span class="result-value ${scData.retention_10000_cycles_pct > 80 ? 'good' : 'warn'}">${scData.retention_10000_cycles_pct}%</span></div>
        <div class="result-row"><span class="result-label">V after 24h</span><span class="result-value">${scData.voltage_after_24h_pct}%</span></div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
//   BATTERY
// ═══════════════════════════════════════════════════════════════════

let batData = null;
let batPlotMode = 'discharge';

async function runBattery() {
    const btn = document.getElementById('btn-bat-run');
    btn.disabled = true; btn.classList.add('loading');
    try {
        const body = {
            chemistry: document.getElementById('bat-chem').value,
            area_cm2: parseFloat(document.getElementById('bat-area').value),
            cathode_thickness_um: parseFloat(document.getElementById('bat-cthick').value),
            cathode_loading_mg_cm2: parseFloat(document.getElementById('bat-cload').value),
            anode_thickness_um: parseFloat(document.getElementById('bat-athick').value),
            anode_loading_mg_cm2: parseFloat(document.getElementById('bat-aload').value),
            C_rate: parseFloat(document.getElementById('bat-crate').value),
            n_cells_series: parseInt(document.getElementById('bat-ncells').value),
        };
        const r = await fetch(PE_API + '/battery/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        batData = await r.json();
        plotBat(); showBatResults();
    } catch (e) { alert('Battery simulation failed: ' + e.message); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
}

function plotBat() {
    if (!batData) return;
    const div = document.getElementById('bat-plot');
    if (batPlotMode === 'discharge' && batData.discharge_curve) {
        const dc = batData.discharge_curve;
        Plotly.newPlot(div, [{ x: dc.capacity_mAh, y: dc.voltage_V, mode: 'lines', line: { color: '#3fb950', width: 2 } }], theme({ xaxis: { title: 'Capacity (mAh)' }, yaxis: { title: 'Voltage (V)' } }), PCFG);
    } else if (batPlotMode === 'rate' && batData.rate_capability) {
        const rates = Object.keys(batData.rate_capability);
        const vals = Object.values(batData.rate_capability);
        Plotly.newPlot(div, [{ x: rates, y: vals, type: 'bar', marker: { color: rates.map((_, i) => `hsl(${200 + i * 20}, 70%, 55%)`) } }], theme({ xaxis: { title: 'C-Rate' }, yaxis: { title: 'Capacity Retention (%)' } }), PCFG);
    } else if (batPlotMode === 'ragone' && batData.ragone) {
        Plotly.newPlot(div, [{ x: batData.ragone.P_W_kg, y: batData.ragone.E_Wh_kg, mode: 'lines+markers', marker: { size: 4, color: '#bc8cff' }, line: { color: '#bc8cff', width: 2 } }], theme({ xaxis: { title: 'Power (W/kg)', type: 'log' }, yaxis: { title: 'Energy (Wh/kg)', type: 'log' } }), PCFG);
    } else if (batPlotMode === 'eis' && batData.eis) {
        Plotly.newPlot(div, [{ x: batData.eis.Z_real, y: batData.eis.Z_imag_neg, mode: 'lines+markers', marker: { size: 3, color: '#58a6ff' }, line: { color: '#58a6ff', width: 1.5 } }], theme({ xaxis: { title: "Z' (Ω)" }, yaxis: { title: "-Z'' (Ω)" } }), PCFG);
    }
}

function switchBatPlot(mode) { batPlotMode = mode; document.querySelectorAll('#tab-battery .plot-tab').forEach(t => t.classList.remove('active')); event.target.classList.add('active'); plotBat(); }

function showBatResults() {
    if (!batData) return;
    document.getElementById('bat-results').innerHTML = `
        <div class="result-row"><span class="result-label">Capacity</span><span class="result-value good">${batData.delivered_capacity_mAh} mAh</span></div>
        <div class="result-row"><span class="result-label">Utilization</span><span class="result-value ${batData.utilization_pct > 80 ? 'good' : 'warn'}">${batData.utilization_pct}%</span></div>
        <div class="result-row"><span class="result-label">Energy</span><span class="result-value">${batData.energy_mWh} mWh</span></div>
        <div class="result-row"><span class="result-label">Energy Density</span><span class="result-value">${batData.energy_density_Wh_kg} Wh/kg</span></div>
        <div class="result-row"><span class="result-label">Areal Energy</span><span class="result-value">${batData.areal_energy_mWh_cm2} mWh/cm²</span></div>
        <div class="result-row"><span class="result-label">OCV</span><span class="result-value">${batData.OCV_V} V</span></div>
        <div class="result-row"><span class="result-label">Avg. Discharge V</span><span class="result-value">${batData.avg_discharge_V} V</span></div>
        <div class="result-row"><span class="result-label">R_internal</span><span class="result-value">${batData.internal_resistance_ohm} Ω</span></div>
        <div class="result-row"><span class="result-label">Power</span><span class="result-value">${batData.power_mW} mW</span></div>
        <div class="result-row"><span class="result-label">Self-Discharge</span><span class="result-value">${batData.self_discharge_pct_per_month}%/month</span></div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
//   BIOSENSOR
// ═══════════════════════════════════════════════════════════════════

let bioData = null;
let bioPlotMode = 'calibration';

async function runBiosensor() {
    const btn = document.getElementById('btn-bio-run');
    btn.disabled = true; btn.classList.add('loading');
    try {
        const body = {
            analyte: document.getElementById('bio-analyte').value,
            sensor_type: document.getElementById('bio-type').value,
            electrode_material: document.getElementById('bio-electrode').value,
            modifier: document.getElementById('bio-modifier').value,
            area_mm2: parseFloat(document.getElementById('bio-area').value),
            enzyme_loading_U_cm2: parseFloat(document.getElementById('bio-enzyme').value),
            pH: parseFloat(document.getElementById('bio-ph').value),
            applied_potential_V: parseFloat(document.getElementById('bio-potential').value),
        };
        const r = await fetch(PE_API + '/biosensor/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        bioData = await r.json();
        plotBio(); showBioResults();
    } catch (e) { alert('Biosensor simulation failed: ' + e.message); }
    finally { btn.disabled = false; btn.classList.remove('loading'); }
}

function plotBio() {
    if (!bioData) return;
    const div = document.getElementById('bio-plot');
    if (bioPlotMode === 'calibration' && bioData.calibration) {
        const c = bioData.calibration;
        Plotly.newPlot(div, [{ x: c.concentrations_mM, y: c.responses_uA, mode: 'lines+markers', marker: { size: 4, color: '#3fb950' }, line: { color: '#3fb950', width: 2 }, name: 'Response' }], theme({ xaxis: { title: 'Concentration (mM)', type: 'log' }, yaxis: { title: 'Current (µA)' } }), PCFG);
    } else if (bioPlotMode === 'chronoamp' && bioData.chronoamperometry) {
        const ca = bioData.chronoamperometry;
        Plotly.newPlot(div, [{ x: ca.t_s, y: ca.i_uA, mode: 'lines', line: { color: '#d29922', width: 1.5 } }], theme({ xaxis: { title: 'Time (s)' }, yaxis: { title: 'Current (µA)' } }), PCFG);
    } else if (bioPlotMode === 'dpv' && bioData.dpv) {
        const d = bioData.dpv;
        Plotly.newPlot(div, [{ x: d.E_V, y: d.i_uA, mode: 'lines', line: { color: '#bc8cff', width: 2 } }], theme({ xaxis: { title: 'Potential (V)' }, yaxis: { title: 'Current (µA)' } }), PCFG);
    } else if (bioPlotMode === 'eis' && bioData.eis) {
        const e = bioData.eis;
        Plotly.newPlot(div, [
            { x: e.baseline.Z_real, y: e.baseline.Z_imag_neg, mode: 'lines+markers', marker: { size: 3, color: '#58a6ff' }, line: { color: '#58a6ff', width: 1.5 }, name: 'Baseline' },
            { x: e.with_analyte.Z_real, y: e.with_analyte.Z_imag_neg, mode: 'lines+markers', marker: { size: 3, color: '#f85149' }, line: { color: '#f85149', width: 1.5, dash: 'dot' }, name: 'With Analyte' },
        ], theme({ xaxis: { title: "Z' (Ω)" }, yaxis: { title: "-Z'' (Ω)" }, showlegend: true, legend: { x: 0.6, y: 0.95, font: { size: 10 } } }), PCFG);
    }
}

function switchBioPlot(mode) { bioPlotMode = mode; document.querySelectorAll('#tab-biosensor .plot-tab').forEach(t => t.classList.remove('active')); event.target.classList.add('active'); plotBio(); }

function showBioResults() {
    if (!bioData) return;
    document.getElementById('bio-results').innerHTML = `
        <div class="result-row"><span class="result-label">Sensitivity</span><span class="result-value good">${bioData.sensitivity_uA_mM} µA/mM</span></div>
        <div class="result-row"><span class="result-label">Sensitivity (area)</span><span class="result-value">${bioData.sensitivity_uA_mM_cm2} µA·mM⁻¹·cm⁻²</span></div>
        <div class="result-row"><span class="result-label">LOD</span><span class="result-value ${bioData.LOD_uM < 10 ? 'good' : bioData.LOD_uM < 100 ? 'warn' : 'bad'}">${bioData.LOD_uM} µM</span></div>
        <div class="result-row"><span class="result-label">LOQ</span><span class="result-value">${bioData.LOQ_uM} µM</span></div>
        <div class="result-row"><span class="result-label">Linear Range</span><span class="result-value">${bioData.calibration?.slope ? bioData.calibration.concentrations_mM?.[0]?.toFixed(3) + '–' + bioData.calibration.concentrations_mM?.[bioData.calibration.concentrations_mM.length-1]?.toFixed(1) + ' mM' : '—'}</span></div>
        <div class="result-row"><span class="result-label">R²</span><span class="result-value ${bioData.calibration?.R_squared > 0.99 ? 'good' : 'warn'}">${bioData.calibration?.R_squared}</span></div>
        <div class="result-row"><span class="result-label">K_m</span><span class="result-value">${bioData.Km_mM} mM</span></div>
        <div class="result-row"><span class="result-label">Response Time</span><span class="result-value">${bioData.response_time_s} s</span></div>
        <div class="result-row"><span class="result-label">ΔR_ct</span><span class="result-value">${bioData.Rct_change_pct}%</span></div>
        <div class="result-row"><span class="result-label">Peak I</span><span class="result-value">${bioData.peak_current_uA} µA @ ${bioData.peak_potential_V}V</span></div>
        <div class="result-row"><span class="result-label">Op. Stability</span><span class="result-value">${bioData.operational_stability_hours} h</span></div>
        <div class="result-row"><span class="result-label">Shelf Life</span><span class="result-value">${bioData.shelf_life_days} days</span></div>
    `;
}

// ═══════════════════════════════════════════════════════════════════
//   PREDICTION
// ═══════════════════════════════════════════════════════════════════

async function runPredict() {
    try {
        const comp = {};
        document.querySelectorAll('#predict-composition .comp-row').forEach(row => {
            const name = row.querySelector('.comp-mat').value;
            const frac = parseFloat(row.querySelector('.comp-frac').value);
            if (name && frac > 0) comp[name] = frac;
        });
        const body = { composition: comp, synthesis: { method: document.getElementById('predict-method').value, temperature_C: parseFloat(document.getElementById('predict-temp').value), duration_hours: parseFloat(document.getElementById('predict-duration').value) } };
        const r = await fetch(API + '/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await r.json();
        const traces = [{ x: data.eis_data?.Z_real || [], y: data.eis_data?.Z_imag_neg || [], mode: 'lines+markers', marker: { size: 3, color: '#58a6ff' }, line: { color: '#58a6ff', width: 1.5 }, name: 'Predicted' }];
        if (data.eis_upper_band && data.eis_lower_band) {
            traces.push({ x: data.eis_upper_band.Z_real, y: data.eis_upper_band.Z_imag_neg, mode: 'lines', line: { color: 'rgba(88,166,255,0.3)', width: 1, dash: 'dot' }, name: 'Upper 90% CI' });
            traces.push({ x: data.eis_lower_band.Z_real, y: data.eis_lower_band.Z_imag_neg, mode: 'lines', line: { color: 'rgba(88,166,255,0.3)', width: 1, dash: 'dot' }, name: 'Lower 90% CI' });
        }
        Plotly.newPlot(document.getElementById('predict-plot'), traces, theme({ xaxis: { title: "Z' (\u03a9)" }, yaxis: { title: "-Z'' (\u03a9)", scaleanchor: 'x' }, showlegend: traces.length > 1, legend: { x: 0.6, y: 0.95, font: { size: 10 } } }), PCFG);
        const ep = data.eis_params || {}; const desc = data.descriptors || {};
        document.getElementById('predict-results').innerHTML = `
            <div class="result-row"><span class="result-label">R_s</span><span class="result-value">${fmt(ep.Rs)} \u03a9</span></div>
            <div class="result-row"><span class="result-label">R_ct</span><span class="result-value">${fmt(ep.Rct)} \u03a9</span></div>
            <div class="result-row"><span class="result-label">C_dl</span><span class="result-value">${sci(ep.Cdl)} F</span></div>
            <div class="result-row"><span class="result-label">\u03c3_W</span><span class="result-value">${fmt(ep.sigma_warburg)}</span></div>
            <div class="result-row"><span class="result-label">Porosity</span><span class="result-value">${fmt(desc.porosity)}</span></div>
            <div class="result-row"><span class="result-label">BET SA</span><span class="result-value">${fmt(desc.surface_area_m2_g)} m\u00b2/g</span></div>
            <div class="result-row"><span class="result-label">Conductivity</span><span class="result-value">${sci(desc.conductivity_S_m)} S/m</span></div>
        `;
    } catch (e) { alert('Prediction failed: ' + e.message); }
}

function addCompRow() {
    const container = document.getElementById('predict-composition');
    const row = document.createElement('div'); row.className = 'comp-row';
    row.innerHTML = `<select class="comp-mat"></select><input type="number" class="comp-frac" value="0.0" step="0.05" min="0" max="1">`;
    container.appendChild(row); populateCompSelects();
}

function addCostRow() {
    const container = document.getElementById('cost-composition');
    const row = document.createElement('div'); row.className = 'comp-row';
    row.innerHTML = `<select class="comp-mat"></select><input type="number" class="comp-frac" value="0.0" step="0.05" min="0" max="1">`;
    container.appendChild(row); populateCompSelects();
}

// ═══════════════════════════════════════════════════════════════════
//   COST ANALYSIS
// ═══════════════════════════════════════════════════════════════════

async function runCostEstimate() {
    try {
        const comp = {};
        document.querySelectorAll('#cost-composition .comp-row').forEach(row => {
            const name = row.querySelector('.comp-mat').value;
            const frac = parseFloat(row.querySelector('.comp-frac').value);
            if (name && frac > 0) comp[name] = frac;
        });
        const mass = parseFloat(document.getElementById('cost-mass').value);
        const r = await fetch(API + `/cost/estimate?mass_g=${mass}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(comp) });
        const data = await r.json();
        let rows = '';
        (data.breakdown || []).forEach(b => { rows += `<div class="result-row"><span class="result-label">${b.material} (${(b.fraction*100).toFixed(0)}%)</span><span class="result-value">${b.mass_g}g × $${b.unit_cost_USD_g}/g = $${b.cost_USD}</span></div>`; });
        const su = data.scale_up || {};
        document.getElementById('cost-results').innerHTML = `
            <div class="result-row"><span class="result-label">Total (${mass}g)</span><span class="result-value good">$${data.total_cost_USD}</span></div>
            ${rows}
            <div class="result-row" style="margin-top:8px;"><span class="result-label">Scale 10g</span><span class="result-value">$${su['10g']}</span></div>
            <div class="result-row"><span class="result-label">Scale 100g (30% disc.)</span><span class="result-value">$${su['100g']}</span></div>
            <div class="result-row"><span class="result-label">Scale 1kg (60% disc.)</span><span class="result-value">$${su['1kg']}</span></div>
        `;
    } catch (e) { alert('Cost estimation failed: ' + e.message); }
}

// ═══════════════════════════════════════════════════════════════════
//   RESEARCH PIPELINE
// ═══════════════════════════════════════════════════════════════════

async function loadPipelineStats() {
    try {
        const r = await fetch(API + '/pipeline/stats');
        const data = await r.json();
        const div = document.getElementById('pipeline-stats');
        if (data.status !== 'ok') { div.innerHTML = `<div class="result-row"><span class="result-label">Status</span><span class="result-value bad">${data.message || 'Database not found'}</span></div>`; return; }
        let matRows = ''; (data.top_materials || []).slice(0, 10).forEach(m => { matRows += `<div class="result-row"><span class="result-label">${m.component}</span><span class="result-value">${m.paper_count} papers (conf: ${m.avg_confidence})</span></div>`; });
        let synRows = ''; (data.synthesis_methods || []).forEach(s => { synRows += `<div class="result-row"><span class="result-label">${s.method}</span><span class="result-value">${s.paper_count} papers</span></div>`; });
        div.innerHTML = `
            <div class="result-row"><span class="result-label">Total Papers</span><span class="result-value good">${data.total_papers}</span></div>
            <div class="result-row"><span class="result-label">Processed</span><span class="result-value">${data.processed_papers}</span></div>
            <div class="result-row"><span class="result-label">Materials</span><span class="result-value">${data.total_materials}</span></div>
            <div class="result-row"><span class="result-label">Unique Materials</span><span class="result-value">${data.unique_materials}</span></div>
            <div class="result-row"><span class="result-label">EIS Records</span><span class="result-value">${data.total_eis_records}</span></div>
            <div class="result-row"><span class="result-label">Synthesis Records</span><span class="result-value">${data.total_synthesis}</span></div>
            <div style="margin-top:12px;font-size:12px;font-weight:600;color:#8b949e;">Top Materials</div>${matRows}
            <div style="margin-top:12px;font-size:12px;font-weight:600;color:#8b949e;">Synthesis Methods</div>${synRows}
        `;
    } catch (e) { document.getElementById('pipeline-stats').innerHTML = `<div class="result-row"><span class="result-label">Error</span><span class="result-value bad">${e.message}</span></div>`; }
}

// ═══════════════════════════════════════════════════════════════════
//   UTILITIES
// ═══════════════════════════════════════════════════════════════════

function fmt(v, digits = 3) {
    if (v == null || v === undefined) return '\u2014';
    if (typeof v === 'number') {
        if (Math.abs(v) >= 1e4 || (Math.abs(v) < 0.01 && v !== 0)) return v.toExponential(digits - 1);
        return v.toFixed(digits);
    }
    return String(v);
}

function sci(v) {
    if (v == null || v === undefined) return '\u2014';
    if (typeof v !== 'number') return String(v);
    return v.toExponential(3);
}
