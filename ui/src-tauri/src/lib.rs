use tauri::Manager;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Bonjour {}! Bienvenue sur AgentOS Desktop.", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![greet])
        .setup(|app| {
            let _window = app.get_webview_window("main").unwrap();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running AgentOS Desktop");
}
