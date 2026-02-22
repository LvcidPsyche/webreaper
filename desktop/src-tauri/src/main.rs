// WebReaper Desktop — Tauri 2.x sidecar management
//
// Spawns the FastAPI server as a sidecar process and manages its lifecycle.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

struct ServerState {
    process: Mutex<Option<Child>>,
}

#[tauri::command]
fn start_sidecar(state: State<ServerState>) -> Result<String, String> {
    let mut proc = state.process.lock().map_err(|e| e.to_string())?;

    if proc.is_some() {
        return Ok("Server already running".to_string());
    }

    // Try bundled binary first, fall back to python -m server.main
    let child = Command::new("python3")
        .args(["-m", "server.main"])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .spawn()
        .map_err(|e| format!("Failed to start server: {}", e))?;

    *proc = Some(child);
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
            // Auto-start sidecar on app launch
            let state = app.state::<ServerState>();
            let _ = start_sidecar(state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state = window.state::<ServerState>();
                let _ = stop_sidecar(state);
            }
        })
        .run(tauri::generate_context!())
        .expect("error running WebReaper desktop app");
}
