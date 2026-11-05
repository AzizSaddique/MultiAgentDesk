#[tauri::command]
fn get_agentdesk_status() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "status": "ready",
        "shell": "Tauri 2",
        "version": "0.1.0",
        "platform": std::env::consts::OS,
        "arch": std::env::consts::ARCH
    }))
}

#[tauri::command]
fn get_session_token() -> Result<String, String> {
    if let Ok(token) = std::env::var("AGENTDESK_SESSION_TOKEN") {
        let trimmed = token.trim().to_string();
        if !trimmed.is_empty() {
            return Ok(trimmed);
        }
    }
    let candidate_paths = [
        std::path::PathBuf::from("storage/.session_token"),
        std::path::PathBuf::from("../storage/.session_token"),
    ];
    for path in &candidate_paths {
        if path.is_file() {
            if let Ok(content) = std::fs::read_to_string(path) {
                let trimmed = content.trim().to_string();
                if !trimmed.is_empty() {
                    return Ok(trimmed);
                }
            }
        }
    }
    Err("Session token not found".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![get_agentdesk_status, get_session_token])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
