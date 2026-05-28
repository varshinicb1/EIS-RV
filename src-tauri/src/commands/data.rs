use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
pub struct ImportedData {
    pub filename: String,
    pub columns: Vec<String>,
    pub data: Vec<Vec<f64>>,
    pub n_rows: usize,
    pub n_cols: usize,
}

#[tauri::command]
pub fn import_csv(file_path: String) -> Result<ImportedData, String> {
    let path = PathBuf::from(&file_path);
    if !path.exists() {
        return Err(format!("File not found: {}", file_path));
    }

    let mut reader = csv::ReaderBuilder::new()
        .flexible(true)
        .has_headers(true)
        .from_path(&path)
        .map_err(|e| format!("Failed to open CSV: {}", e))?;

    let headers: Vec<String> = reader
        .headers()
        .map_err(|e| format!("Failed to read headers: {}", e))?
        .iter()
        .map(|h| h.trim().to_string())
        .collect();

    let n_cols = headers.len();
    let mut columns: Vec<Vec<f64>> = vec![Vec::new(); n_cols];
    let mut n_rows = 0;

    for result in reader.records() {
        let record = result.map_err(|e| format!("CSV parse error at row {}: {}", n_rows + 1, e))?;
        for (i, field) in record.iter().enumerate() {
            if i < n_cols {
                let val: f64 = field.trim().parse().unwrap_or(f64::NAN);
                columns[i].push(val);
            }
        }
        n_rows += 1;
    }

    let filename = path
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();

    Ok(ImportedData {
        filename,
        columns: headers,
        data: columns,
        n_rows,
        n_cols,
    })
}

#[tauri::command]
pub fn export_csv(
    file_path: String,
    headers: Vec<String>,
    data: Vec<Vec<f64>>,
) -> Result<(), String> {
    let mut writer = csv::Writer::from_path(&file_path)
        .map_err(|e| format!("Failed to create CSV: {}", e))?;

    // Write headers
    writer
        .write_record(&headers)
        .map_err(|e| format!("Failed to write headers: {}", e))?;

    // Write data rows
    if !data.is_empty() {
        let n_rows = data[0].len();
        for row in 0..n_rows {
            let record: Vec<String> = data
                .iter()
                .map(|col| {
                    if row < col.len() {
                        format!("{:.6e}", col[row])
                    } else {
                        String::new()
                    }
                })
                .collect();
            writer
                .write_record(&record)
                .map_err(|e| format!("Failed to write row {}: {}", row, e))?;
        }
    }

    writer
        .flush()
        .map_err(|e| format!("Failed to flush CSV: {}", e))?;

    Ok(())
}

#[tauri::command]
pub fn read_text_file(file_path: String) -> Result<String, String> {
    fs::read_to_string(&file_path).map_err(|e| format!("Failed to read file: {}", e))
}
