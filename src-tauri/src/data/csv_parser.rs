//! CSV parser for electrochemical data files (AnalyteX, Gamry, CHI, etc.)

use std::path::Path;

/// Detected file format
#[derive(Debug, Clone, PartialEq)]
pub enum DataFormat {
    GenericCSV,
    AnalyteX,
    GamryDTA,
    CHI,
}

/// Detect the format of an electrochemical data file
pub fn detect_format(path: &Path) -> DataFormat {
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    match ext.as_str() {
        "dta" => DataFormat::GamryDTA,
        "chi" | "bin" => DataFormat::CHI,
        _ => {
            // Check content for AnalyteX markers
            if let Ok(content) = std::fs::read_to_string(path) {
                if content.contains("AnalyteX") || content.contains("VidyuthLabs") {
                    DataFormat::AnalyteX
                } else {
                    DataFormat::GenericCSV
                }
            } else {
                DataFormat::GenericCSV
            }
        }
    }
}
