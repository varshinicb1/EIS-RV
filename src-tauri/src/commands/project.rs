use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::fs;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub description: String,
    pub created_at: String,
    pub modified_at: String,
    pub version: String,
    pub datasets: Vec<DatasetEntry>,
    pub simulations: Vec<SimulationEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatasetEntry {
    pub id: String,
    pub name: String,
    pub data_type: String,
    pub columns: Vec<String>,
    pub data: Vec<Vec<f64>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationEntry {
    pub id: String,
    pub sim_type: String,
    pub name: String,
    pub params: serde_json::Value,
    pub results: serde_json::Value,
    pub created_at: String,
}

impl Project {
    pub fn new(name: String, description: String) -> Self {
        let now = Utc::now().to_rfc3339();
        Self {
            id: Uuid::new_v4().to_string(),
            name,
            description,
            created_at: now.clone(),
            modified_at: now,
            version: "3.0.0".to_string(),
            datasets: Vec::new(),
            simulations: Vec::new(),
        }
    }
}

#[tauri::command]
pub fn create_project(name: String, description: String) -> Result<Project, String> {
    Ok(Project::new(name, description))
}

#[tauri::command]
pub fn save_project(file_path: String, project: Project) -> Result<(), String> {
    let json = serde_json::to_string_pretty(&project)
        .map_err(|e| format!("Failed to serialize project: {}", e))?;

    fs::write(&file_path, json).map_err(|e| format!("Failed to write project file: {}", e))?;

    Ok(())
}

#[tauri::command]
pub fn load_project(file_path: String) -> Result<Project, String> {
    let json =
        fs::read_to_string(&file_path).map_err(|e| format!("Failed to read project file: {}", e))?;

    let project: Project =
        serde_json::from_str(&json).map_err(|e| format!("Failed to parse project file: {}", e))?;

    Ok(project)
}
