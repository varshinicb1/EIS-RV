pub mod engine;
pub mod commands;
pub mod data;

use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            commands::eis::simulate_eis,
            commands::cv::simulate_cv,
            commands::drt::compute_drt,
            commands::drt::kramers_kronig_test,
            commands::fitting::fit_circuit,
            commands::data::import_csv,
            commands::data::export_csv,
            commands::data::read_text_file,
            commands::project::create_project,
            commands::project::save_project,
            commands::project::load_project,
            commands::analysis::run_analysis,
            commands::analysis::list_plot_styles,
            commands::analysis::list_example_datasets,
            commands::materials::search_electrode_materials,
            commands::materials::predict_material_performance,
        ])
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                let window = app.get_webview_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running RAMAN Studio");
}
