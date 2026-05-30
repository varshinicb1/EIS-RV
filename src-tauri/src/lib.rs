use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use tauri::{Emitter, Manager};
use tauri_plugin_updater::UpdaterExt;

static PYTHON_RUNNING: AtomicBool = AtomicBool::new(false);
static PYTHON_PID: Mutex<Option<u32>> = Mutex::new(None);

fn find_python() -> Option<PathBuf> {
    let candidates = if cfg!(windows) {
        vec!["python.exe", "python3.exe", "py.exe"]
    } else {
        vec!["python3", "python"]
    };
    for name in &candidates {
        if let Ok(output) = Command::new(name).args(&["--version"]).output() {
            if output.status.success() {
                return Some(PathBuf::from(name));
            }
        }
    }
    None
}

fn find_repo_root() -> Option<PathBuf> {
    // Try to find the repo root by looking for src/backend/api/server.py
    // relative to the executable location
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(|p| p.to_path_buf());
        // Walk up from exe directory (e.g. target/release/) looking for repo root
        for _ in 0..5 {
            if let Some(ref d) = dir {
                if d.join("src").join("backend").join("api").join("server.py").exists() {
                    return Some(d.clone());
                }
                dir = d.parent().map(|p| p.to_path_buf());
            }
        }
    }
    // Also check current working directory
    if let Ok(cwd) = std::env::current_dir() {
        if cwd.join("src").join("backend").join("api").join("server.py").exists() {
            return Some(cwd);
        }
    }
    None
}

fn kill_python_backend() {
    let mut guard = PYTHON_PID.lock().unwrap();
    if let Some(pid) = *guard {
        #[cfg(windows)]
        {
            // Force kill the tree (uvicorn child processes too)
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .status();
        }
        #[cfg(not(windows))]
        {
            let _ = Command::new("kill").args(["-TERM", &pid.to_string()]).status();
            std::thread::sleep(std::time::Duration::from_millis(200));
            let _ = Command::new("kill").args(["-9", &pid.to_string()]).status();
        }
        *guard = None;
        PYTHON_RUNNING.store(false, Ordering::SeqCst);
        eprintln!("[RAMAN] Python sidecar terminated (pid {})", pid);
    }
}

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
        // Production: try bundled Python first, validate it works, then fall
        // back to any Python found on PATH.
        let bundled_python = resource_dir.join("python").join("python.exe");
        let bundled_ok = bundled_python.exists() && {
            Command::new(&bundled_python)
                .args(&["-c", "import sys"])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .map(|s| s.success())
                .unwrap_or(false)
        };
        let cmd_str = if bundled_ok {
            bundled_python.to_string_lossy().to_string()
        } else {
            match find_python() {
                Some(p) => p.to_string_lossy().to_string(),
                None => return Err(
                    "Python is not installed.\n\n".to_string()
                    + "RĀMAN Studio requires Python 3.11 or newer.\n"
                    + "Download it from https://python.org/downloads",
                ),
            }
        };

        // Production: ALWAYS use the resource_dir as cwd. This guarantees that
        // the bundled "src/backend", "models/Raman-Qwen-Agent", and "data/cleaned/fog"
        // (copied by tauri.conf.json resources) are discoverable by relative paths
        // used in agent_routes (ADAPTER_DIR), lab_routes FOG searches, and uvicorn module.
        // find_repo_root is retained only for dev edge cases.
        let backend_cwd = resource_dir.clone();

        (
            cmd_str,
            vec![
                "-m".to_string(), "uvicorn".to_string(),
                "src.backend.api.server:app".to_string(),
                "--host".to_string(), "127.0.0.1".to_string(),
                "--port".to_string(), "8000".to_string(),
            ],
            backend_cwd,
        )
    };

    let mut command = Command::new(&cmd);
    command
        .args(&args)
        .current_dir(&cwd)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        // Ensure imports resolve to bundled src/ + any wheels in python/
        .env("PYTHONPATH", cwd.to_string_lossy().to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }

    let mut child = command.spawn()
        .map_err(|e| format!("Failed to start Python backend: {}\n\nMake sure Python and uvicorn are installed:\n  pip install uvicorn fastapi", e))?;

    // Record PID for clean shutdown on app exit / window close (fixes sidecar lifecycle leak)
    {
        let pid = child.id();
        let mut guard = PYTHON_PID.lock().unwrap();
        *guard = Some(pid);
    }
    PYTHON_RUNNING.store(true, Ordering::SeqCst);

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

fn build_menu<R: tauri::Runtime>(app: &tauri::AppHandle<R>) -> Result<tauri::menu::Menu<R>, Box<dyn std::error::Error>> {
    use tauri::menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};

    let new_project  = MenuItemBuilder::with_id("new-project", "New project").accelerator("CmdOrCtrl+N").build(app)?;
    let open_project = MenuItemBuilder::with_id("open-project", "Open project...").accelerator("CmdOrCtrl+O").build(app)?;
    let save_project = MenuItemBuilder::with_id("save-project", "Save project").accelerator("CmdOrCtrl+S").build(app)?;
    let save_as      = MenuItemBuilder::with_id("save-project-as", "Save project as...").accelerator("CmdOrCtrl+Shift+S").build(app)?;
    let sep1         = PredefinedMenuItem::separator(app)?;
    let open_lab     = MenuItemBuilder::with_id("open-lab-data", "Open lab data (xlsx / csv)...").build(app)?;
    let import_data  = MenuItemBuilder::with_id("import-data", "Import EIS / CV data...").build(app)?;
    let sep2         = PredefinedMenuItem::separator(app)?;
    let export_pdf   = MenuItemBuilder::with_id("export-report", "Export current report (PDF)").accelerator("CmdOrCtrl+E").build(app)?;
    let export_png   = MenuItemBuilder::with_id("export-plot", "Export plot (PNG)").accelerator("CmdOrCtrl+Shift+E").build(app)?;
    let sep3         = PredefinedMenuItem::separator(app)?;
    let quit         = PredefinedMenuItem::quit(app, None)?;

    let file_menu = SubmenuBuilder::new(app, "File")
        .item(&new_project).item(&open_project).item(&save_project).item(&save_as)
        .item(&sep1).item(&open_lab).item(&import_data)
        .item(&sep2).item(&export_pdf).item(&export_png)
        .item(&sep3).item(&quit)
        .build()?;

    let undo   = PredefinedMenuItem::undo(app, None)?;
    let redo   = PredefinedMenuItem::redo(app, None)?;
    let cut    = PredefinedMenuItem::cut(app, None)?;
    let copy   = PredefinedMenuItem::copy(app, None)?;
    let paste  = PredefinedMenuItem::paste(app, None)?;
    let selall = PredefinedMenuItem::select_all(app, None)?;
    let sep_e  = PredefinedMenuItem::separator(app)?;
    let settings = MenuItemBuilder::with_id("navigate-panel:profile", "Settings...").accelerator("CmdOrCtrl+,").build(app)?;

    let edit_menu = SubmenuBuilder::new(app, "Edit")
        .item(&undo).item(&redo).item(&sep_e)
        .item(&cut).item(&copy).item(&paste).item(&selall)
        .item(&sep_e).item(&settings)
        .build()?;

    let sep_v  = PredefinedMenuItem::separator(app)?;
    let light  = MenuItemBuilder::with_id("set-theme:light", "Light theme").accelerator("CmdOrCtrl+Shift+L").build(app)?;
    let dark   = MenuItemBuilder::with_id("set-theme:dark", "Dark theme").accelerator("CmdOrCtrl+Shift+D").build(app)?;
    let hc     = MenuItemBuilder::with_id("set-theme:hc", "High-contrast theme").accelerator("CmdOrCtrl+Shift+H").build(app)?;

    let view_menu = SubmenuBuilder::new(app, "View")
        .item(&sep_v)
        .item(&light).item(&dark).item(&hc)
        .build()?;

    let dash = MenuItemBuilder::with_id("navigate-panel:dashboard", "Dashboard").accelerator("CmdOrCtrl+1").build(app)?;
    let eis  = MenuItemBuilder::with_id("navigate-panel:eis", "EIS").accelerator("CmdOrCtrl+2").build(app)?;
    let cv   = MenuItemBuilder::with_id("navigate-panel:cv", "Cyclic voltammetry").accelerator("CmdOrCtrl+3").build(app)?;
    let gcd  = MenuItemBuilder::with_id("navigate-panel:gcd", "GCD").accelerator("CmdOrCtrl+4").build(app)?;
    let drt  = MenuItemBuilder::with_id("navigate-panel:drt", "DRT").accelerator("CmdOrCtrl+5").build(app)?;
    let circ = MenuItemBuilder::with_id("navigate-panel:circuit", "Circuit fitting").accelerator("CmdOrCtrl+6").build(app)?;
    let bios = MenuItemBuilder::with_id("navigate-panel:biosensor", "Biosensor").accelerator("CmdOrCtrl+7").build(app)?;
    let sep_t = PredefinedMenuItem::separator(app)?;
    let alch = MenuItemBuilder::with_id("navigate-panel:alchemi", "Materials AI").build(app)?;
    let disc = MenuItemBuilder::with_id("navigate-panel:discovery", "Discovery & AI").build(app)?;
    let alcanvas = MenuItemBuilder::with_id("navigate-panel:alchemist_canvas", "Alchemist canvas").build(app)?;
    let lab  = MenuItemBuilder::with_id("navigate-panel:lab", "Lab data").build(app)?;
    let lit  = MenuItemBuilder::with_id("navigate-panel:literature", "Literature mining").build(app)?;
    let rep  = MenuItemBuilder::with_id("navigate-panel:reports", "Reports").build(app)?;

    let tools_menu = SubmenuBuilder::new(app, "Tools")
        .item(&dash).item(&eis).item(&cv).item(&gcd).item(&drt).item(&circ).item(&bios)
        .item(&sep_t)
        .item(&alch).item(&disc).item(&alcanvas).item(&lab).item(&lit).item(&rep)
        .build()?;

    let docs    = MenuItemBuilder::with_id("open-docs", "Documentation").build(app)?;
    let issues  = MenuItemBuilder::with_id("open-issues", "Report an issue").build(app)?;
    let support = MenuItemBuilder::with_id("open-support", "Support").build(app)?;
    let sep_h   = PredefinedMenuItem::separator(app)?;
    let about   = MenuItemBuilder::with_id("open-about", "About").build(app)?;

    let help_menu = SubmenuBuilder::new(app, "Help")
        .item(&docs).item(&issues).item(&support)
        .item(&sep_h).item(&about)
        .build()?;

    let menu = MenuBuilder::new(app)
        .items(&[&file_menu, &edit_menu, &view_menu, &tools_menu, &help_menu])
        .build()?;
    Ok(menu)
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            // ── Menu ──────────────────────────────────────────
            let app_handle = app.handle();
            if let Ok(menu) = build_menu(&app_handle) {
                if let Err(e) = app.set_menu(menu) {
                    eprintln!("[RAMAN] Failed to set menu: {}", e);
                }
            }
            app.on_menu_event(|app_handle, event| {
                let id: &str = event.id.as_ref();
                let event_name = format!("menu:{}", id);
                let _ = app_handle.emit(&event_name, "");
            });

            // ── Updater ───────────────────────────────────────
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Ok(updater) = handle.updater() {
                    if let Ok(Some(update)) = updater.check().await {
                        println!("[RAMAN] Update available: {}", update.version);
                        let _ = handle.emit("update-available", update.version);
                    }
                }
            });

            // ── Python backend ────────────────────────────────
            let py_handle = app.handle().clone();
            std::thread::spawn(move || {
                match start_python_backend(&py_handle) {
                    Ok(mut child) => {
                        let _ = child.wait();
                        PYTHON_RUNNING.store(false, Ordering::SeqCst);
                    }
                    Err(e) => {
                        eprintln!("[RAMAN] Failed to start Python backend: {}", e);
                        let _ = py_handle.emit("backend-error", e);
                    }
                }
            });

            // ── Sidecar lifecycle: kill Python on any window close / app exit ─
            app.on_window_event(|event| {
                if let tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed = event.event() {
                    kill_python_backend();
                }
            });

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
