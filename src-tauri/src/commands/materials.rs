use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Material properties from Materials Project API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MaterialInfo {
    pub material_id: Option<String>,
    pub formula: String,
    pub band_gap: Option<f64>,
    pub formation_energy: Option<f64>,
    pub energy_above_hull: Option<f64>,
    pub is_stable: Option<bool>,
    pub density: Option<f64>,
}

/// Supercapacitor performance prediction
#[derive(Debug, Serialize)]
pub struct SupercapPrediction {
    pub specific_capacitance_f_g: f64,
    pub voltage_window_v: f64,
    pub energy_density_wh_kg: f64,
    pub stability_score: f64,
}

/// Sensor performance prediction
#[derive(Debug, Serialize)]
pub struct SensorPrediction {
    pub sensitivity_ua_mm_cm2: f64,
    pub lod_um: f64,
    pub linear_range_mm: [f64; 2],
    pub response_time_s: f64,
    pub stability_score: f64,
}

/// Predict supercapacitor performance from material properties
fn predict_supercap(band_gap: f64, e_hull: f64, _density: f64) -> SupercapPrediction {
    let cap = if band_gap < 0.5 {
        200.0 + (0.5 - band_gap) * 400.0
    } else if band_gap < 2.0 {
        100.0 + (2.0 - band_gap) * 66.0
    } else {
        (100.0 - (band_gap - 2.0) * 30.0).max(10.0)
    };

    let stability = (100.0 - e_hull * 1000.0).max(0.0);

    let vw = if band_gap > 0.0 {
        (3.0 - band_gap * 0.5).min(1.5)
    } else {
        1.0
    };

    let energy = 0.5 * cap * vw * vw / 3.6;

    SupercapPrediction {
        specific_capacitance_f_g: (cap * 10.0).round() / 10.0,
        voltage_window_v: (vw * 100.0).round() / 100.0,
        energy_density_wh_kg: (energy * 10.0).round() / 10.0,
        stability_score: (stability * 10.0).round() / 10.0,
    }
}

/// Predict sensor performance from material properties
fn predict_sensor(band_gap: f64, e_hull: f64) -> SensorPrediction {
    let sensitivity = if band_gap < 1.0 {
        50.0 + (1.0 - band_gap) * 100.0
    } else {
        (50.0 - (band_gap - 1.0) * 20.0).max(5.0)
    };

    let lod = (10.0 - sensitivity * 0.05).max(0.01);
    let response = (15.0 - sensitivity * 0.05).max(1.0);
    let stability = (100.0 - e_hull * 1000.0).max(0.0);

    SensorPrediction {
        sensitivity_ua_mm_cm2: (sensitivity * 10.0).round() / 10.0,
        lod_um: (lod * 1000.0).round() / 1000.0,
        linear_range_mm: [
            (lod * 1e-3 * 10000.0).round() / 10000.0,
            (sensitivity * 0.1 * 100.0).round() / 100.0,
        ],
        response_time_s: (response * 10.0).round() / 10.0,
        stability_score: (stability * 10.0).round() / 10.0,
    }
}

/// Built-in electrode material database (no API key needed)
fn get_builtin_materials() -> Vec<MaterialInfo> {
    vec![
        MaterialInfo {
            material_id: Some("mp-19770".into()),
            formula: "Fe2O3".into(),
            band_gap: Some(2.0),
            formation_energy: Some(-2.89),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(5.24),
        },
        MaterialInfo {
            material_id: Some("mp-19306".into()),
            formula: "MnO2".into(),
            band_gap: Some(0.7),
            formation_energy: Some(-2.47),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(5.03),
        },
        MaterialInfo {
            material_id: Some("mp-19009".into()),
            formula: "NiO".into(),
            band_gap: Some(3.1),
            formation_energy: Some(-2.18),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(6.67),
        },
        MaterialInfo {
            material_id: Some("mp-18748".into()),
            formula: "Co3O4".into(),
            band_gap: Some(1.5),
            formation_energy: Some(-2.03),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(6.11),
        },
        MaterialInfo {
            material_id: Some("mp-856".into()),
            formula: "RuO2".into(),
            band_gap: Some(0.0),
            formation_energy: Some(-1.46),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(6.97),
        },
        MaterialInfo {
            material_id: Some("mp-25".into()),
            formula: "TiO2".into(),
            band_gap: Some(3.0),
            formation_energy: Some(-3.36),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(4.25),
        },
        MaterialInfo {
            material_id: Some("mp-1143".into()),
            formula: "V2O5".into(),
            band_gap: Some(2.3),
            formation_energy: Some(-2.66),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(3.36),
        },
        MaterialInfo {
            material_id: Some("mp-66".into()),
            formula: "C".into(),
            band_gap: Some(0.0),
            formation_energy: Some(0.0),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(2.27),
        },
        MaterialInfo {
            material_id: Some("mp-1245".into()),
            formula: "WO3".into(),
            band_gap: Some(2.6),
            formation_energy: Some(-2.78),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(7.16),
        },
        MaterialInfo {
            material_id: Some("mp-2657".into()),
            formula: "SnO2".into(),
            band_gap: Some(3.4),
            formation_energy: Some(-2.58),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(6.95),
        },
        MaterialInfo {
            material_id: Some("mp-704645".into()),
            formula: "rGO".into(),
            band_gap: Some(0.0),
            formation_energy: Some(0.0),
            energy_above_hull: Some(0.0),
            is_stable: Some(true),
            density: Some(1.80),
        },
        MaterialInfo {
            material_id: None,
            formula: "Fe2O3/rGO".into(),
            band_gap: Some(0.8),
            formation_energy: Some(-1.5),
            energy_above_hull: Some(0.01),
            is_stable: Some(true),
            density: Some(3.5),
        },
    ]
}

#[tauri::command]
pub fn search_electrode_materials(
    category: Option<String>,
) -> Result<Vec<serde_json::Value>, String> {
    let materials = get_builtin_materials();

    let results: Vec<serde_json::Value> = materials
        .iter()
        .map(|m| {
            let bg = m.band_gap.unwrap_or(0.0);
            let eh = m.energy_above_hull.unwrap_or(0.0);
            let d = m.density.unwrap_or(5.0);

            let supercap = predict_supercap(bg, eh, d);
            let sensor = predict_sensor(bg, eh);

            serde_json::json!({
                "material": m,
                "supercapacitor": supercap,
                "sensor": sensor,
            })
        })
        .collect();

    Ok(results)
}

#[tauri::command]
pub fn predict_material_performance(
    formula: String,
    band_gap: f64,
    energy_above_hull: f64,
    density: f64,
) -> Result<serde_json::Value, String> {
    let supercap = predict_supercap(band_gap, energy_above_hull, density);
    let sensor = predict_sensor(band_gap, energy_above_hull);

    Ok(serde_json::json!({
        "formula": formula,
        "supercapacitor": supercap,
        "sensor": sensor,
    }))
}
