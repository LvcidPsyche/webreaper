// WebReaper Desktop — Tauri 2.x sidecar management
//
// Spawns the FastAPI server as a sidecar process and manages its lifecycle.
// Server binary resolution order:
//   1. WEBREAPER_SERVER_BIN env var (bundled PyInstaller binary)
//   2. `webreaper server` CLI command (installed via pip)
//   3. `python3 -m server.main` from project root (development fallback)

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use std::thread;
use tauri::State;

struct ServerState {
    process: Mutex<Option<Child>>,
}

fn resolve_server_command() -> (String, Vec<String>) {
    // 1. Bundled binary via env var
    if let Ok(bin) = env::var("WEBREAPER_SERVER_BIN") {
        return (bin, vec![]);
    }

    // 2. Installed `webreaper` CLI
    if which_exists("webreaper") {
        return ("webreaper".to_string(), vec!["server".to_string()]);
    }

    // 3. Development fallback
    ("python3".to_string(), vec!["-m".to_string(), "server.main".to_string()])
}

fn which_exists(name: &str) -> bool {
    Command::new("which")
        .arg(name)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

fn wait_for_server(timeout_secs: u64) -> bool {
    let client = match reqwest::blocking::Client::builder()
        .timeout(Duration::from_millis(500))
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };

    let deadline = std::time::Instant::now() + Duration::from_secs(timeout_secs);
    while std::time::Instant::now() < deadline {
        if client.get("http://127.0.0.1:8000/health").send().is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(500));
    }
    false
}

#[tauri::command]
fn start_sidecar(state: State<ServerState>) -> Result<String, String> {
    let mut proc = state.process.lock().map_err(|e| e.to_string())?;

    if proc.is_some() {
        return Ok("Server already running".to_string());
    }

    let (cmd, args) = resolve_server_command();

    let child = Command::new(&cmd)
        .args(&args)
        .current_dir(env!("CARGO_MANIFEST_DIR").to_string() + "/../../..")
        .spawn()
        .map_err(|e| format!("Failed to start server ({}): {}", cmd, e))?;

    *proc = Some(child);

    // Health-check loop: poll /health every 500ms, timeout after 15s
    if !wait_for_server(15) {
        eprintln!("[WebReaper] Warning: server health check timed out after 15s");
    }

    Ok("Server started".to_string())
}

#[tauri::command]
fn stop_sidecar(state: State<ServerState>) -> Result<String, String> {
    let mut proc = state.process.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut child) = *proc {
        child.kill().map_err(|e| format!("Failed to stop server: {}", e))?;
        *proc = None;
        Ok("Server stopped".to_string())
    } else {
        Ok("Server not running".to_string())
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(ServerState {
            process: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![start_sidecar, stop_sidecar])
        .setup(|app| {
            let state = app.state::<ServerState>();
            let _ = start_sidecar(state);
            Ok(())
        })
        .on_window_event(|window, event| {
            // Shut down sidecar on any window destruction, not just CloseRequested
            match event {
                tauri::WindowEvent::CloseRequested { .. }
                | tauri::WindowEvent::Destroyed => {
                    let state = window.state::<ServerState>();
                    let _ = stop_sidecar(state);
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error running WebReaper desktop app");
}
