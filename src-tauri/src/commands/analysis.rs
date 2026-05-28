use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
pub struct AnalysisResult {
    pub technique: String,
    pub metrics: serde_json::Value,
    pub plots: Vec<String>,
    pub output_dir: String,
    pub success: bool,
    pub error: Option<String>,
}

/// Run the Python analysis engine on an uploaded data file.
/// The Python scripts from Electrochem-Suite handle auto-detection,
/// metric extraction, and publication-grade plot generation.
#[tauri::command]
pub fn run_analysis(
    file_path: String,
    style: Option<String>,
    output_dir: Option<String>,
) -> Result<AnalysisResult, String> {
    let input = PathBuf::from(&file_path);
    if !input.exists() {
        return Err(format!("Input file not found: {}", file_path));
    }

    // Determine output directory
    let out_dir = output_dir
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            let mut p = input.parent().unwrap_or(&PathBuf::from(".")).to_path_buf();
            p.push("analysis_output");
            p
        });

    std::fs::create_dir_all(&out_dir)
        .map_err(|e| format!("Failed to create output dir: {}", e))?;

    // Find Python interpreter
    let python = find_python().ok_or("Python not found. Install Python 3.11+ to use the analysis engine.")?;

    // Path to the analysis engine scripts
    let engine_dir = find_analysis_engine()
        .ok_or("Analysis engine scripts not found")?;

    let script = engine_dir.join("run_job.py");
    if !script.exists() {
        return Err("run_job.py not found in analysis engine".into());
    }

    // Build command
    let mut cmd = Command::new(&python);
    cmd.arg(&script)
        .arg("--input").arg(&file_path)
        .arg("--output").arg(out_dir.to_str().unwrap_or("."))
        .arg("--style").arg(style.as_deref().unwrap_or("nature"))
        .current_dir(&engine_dir);

    // Add PYTHONPATH
    cmd.env("PYTHONPATH", engine_dir.to_str().unwrap_or("."));

    let output = cmd.output().map_err(|e| format!("Failed to run analysis: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Ok(AnalysisResult {
            technique: "unknown".into(),
            metrics: serde_json::Value::Null,
            plots: vec![],
            output_dir: out_dir.to_string_lossy().to_string(),
            success: false,
            error: Some(format!("Analysis failed: {}", stderr)),
        });
    }

    // Try to parse JSON output from the script
    let result: serde_json::Value = serde_json::from_str(&stdout)
        .unwrap_or_else(|_| serde_json::json!({ "raw_output": stdout }));

    let technique = result.get("technique")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    let plots: Vec<String> = result.get("plots")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
        .unwrap_or_default();

    Ok(AnalysisResult {
        technique,
        metrics: result.get("metrics").cloned().unwrap_or(serde_json::Value::Null),
        plots,
        output_dir: out_dir.to_string_lossy().to_string(),
        success: true,
        error: None,
    })
}

/// List available plot style presets
#[tauri::command]
pub fn list_plot_styles() -> Vec<String> {
    vec![
        "nature".into(),
        "science".into(),
        "acs".into(),
        "ieee".into(),
        "elsevier".into(),
        "rsc".into(),
        "reference".into(),
        "minimal".into(),
        "modern".into(),
        "grayscale".into(),
        "colorblind".into(),
        "dark".into(),
        "high_contrast".into(),
        "presentation".into(),
        "seaborn_white".into(),
    ]
}

/// List example datasets that ship with the application
#[tauri::command]
pub fn list_example_datasets() -> Vec<serde_json::Value> {
    let datasets = vec![
        serde_json::json!({
            "name": "EIS - Bare GCE",
            "file": "EIS BARE GCE.xlsx",
            "technique": "EIS",
            "description": "Electrochemical impedance spectroscopy of bare glassy carbon electrode"
        }),
        serde_json::json!({
            "name": "EIS - Ferric Oxide",
            "file": "EIS FERRIC OXIDE.xlsx",
            "technique": "EIS",
            "description": "EIS of Fe2O3 modified electrode"
        }),
        serde_json::json!({
            "name": "EIS - FOG (Fe2O3/rGO)",
            "file": "EIS FOG.xlsx",
            "technique": "EIS",
            "description": "EIS of ferric oxide-graphene nanocomposite electrode"
        }),
        serde_json::json!({
            "name": "EIS - rGO",
            "file": "EIS rGO.xlsx",
            "technique": "EIS",
            "description": "EIS of reduced graphene oxide electrode"
        }),
        serde_json::json!({
            "name": "DPV - Uric Acid (FOG)",
            "file": "dpv UA FOG.xlsx",
            "technique": "DPV",
            "description": "Differential pulse voltammetry of uric acid on FOG electrode"
        }),
        serde_json::json!({
            "name": "pH Study",
            "file": "pH study.xlsx",
            "technique": "CV",
            "description": "pH optimization study for biosensor"
        }),
        serde_json::json!({
            "name": "Concentration Study",
            "file": "GOMUTRA CONCENTRATION STUDIES.xlsx",
            "technique": "DPV",
            "description": "Concentration study in real sample matrix"
        }),
    ];
    datasets
}

fn find_python() -> Option<String> {
    // Try common Python locations on Windows
    for name in &["python", "python3", "python3.12", "python3.11"] {
        if let Ok(output) = Command::new(name).arg("--version").output() {
            if output.status.success() {
                return Some(name.to_string());
            }
        }
    }
    None
}

fn find_analysis_engine() -> Option<PathBuf> {
    // Look relative to the executable
    if let Ok(exe) = std::env::current_exe() {
        let base = exe.parent()?;
        // Development: analysis_engine/python/ relative to repo root
        for ancestor in [base, base.parent()?, base.parent()?.parent()?].iter() {
            let candidate = ancestor.join("analysis_engine").join("python");
            if candidate.exists() {
                return Some(candidate);
            }
        }
    }
    // Fallback: look in current directory
    let cwd = std::env::current_dir().ok()?;
    let candidate = cwd.join("analysis_engine").join("python");
    if candidate.exists() {
        return Some(candidate);
    }
    None
}
