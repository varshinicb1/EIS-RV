use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::Manager;

static PYTHON_RUNNING: AtomicBool = AtomicBool::new(false);

fn start_python_backend(app_handle: &tauri::AppHandle) -> Result<std::process::Child, String> {
    let resource_dir = app_handle.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    let is_dev = cfg!(debug_assertions);

    let (cmd, args, cwd) = if is_dev {
        let repo_root = resource_dir.parent()
            .and_then(|p| p.parent())
            .unwrap_or(&resource_dir)
            .to_path_buf();
        (
            if cfg!(windows) { "python" } else { "python3" }.to_string(),
            vec![
                "-m".to_string(), "uvicorn".to_string(),
                "src.backend.api.server:app".to_string(),
                "--host".to_string(), "127.0.0.1".to_string(),
                "--port".to_string(), "8000".to_string(),
                "--log-level".to_string(), "info".to_string(),
            ],
            repo_root,
        )
    } else {
        let python_exe = if cfg!(windows) {
            resource_dir.join("python").join("python.exe")
        } else {
            resource_dir.join("bin").join("python3")
        };
        let cmd_str = if python_exe.exists() {
            python_exe.to_string_lossy().to_string()
        } else {
            (if cfg!(windows) { "python" } else { "python3" }).to_string()
        };
        (
            cmd_str,
            vec![
                "-m".to_string(), "uvicorn".to_string(),
                "src.backend.api.server:app".to_string(),
                "--host".to_string(), "127.0.0.1".to_string(),
                "--port".to_string(), "8000".to_string(),
            ],
            resource_dir.clone(),
        )
    };

    let mut child = Command::new(&cmd)
        .args(&args)
        .current_dir(&cwd)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn Python backend: {}", e))?;

    PYTHON_RUNNING.store(true, Ordering::SeqCst);

    // Log Python output
    if let Some(stdout) = child.stdout.take() {
        std::thread::spawn(move || {
            let reader = std::io::BufReader::new(stdout);
            for line in std::io::BufRead::lines(reader) {
                if let Ok(line) = line {
                    println!("[Python] {}", line);
                }
            }
        });
    }
    if let Some(stderr) = child.stderr.take() {
        std::thread::spawn(move || {
            let reader = std::io::BufReader::new(stderr);
            for line in std::io::BufRead::lines(reader) {
                if let Ok(line) = line {
                    eprintln!("[Python STDERR] {}", line);
                }
            }
        });
    }

    Ok(child)
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();

            std::thread::spawn(move || {
                match start_python_backend(&handle) {
                    Ok(mut child) => {
                        let _ = child.wait();
                        PYTHON_RUNNING.store(false, Ordering::SeqCst);
                    }
                    Err(e) => {
                        eprintln!("[RAMAN] Failed to start Python backend: {}", e);
                    }
                }
            });

            // Wait a moment for the backend to start
            std::thread::sleep(std::time::Duration::from_secs(3));

            #[cfg(debug_assertions)]
            {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.open_devtools();
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running RAMAN Studio");
}
