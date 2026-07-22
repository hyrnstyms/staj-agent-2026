// src-tauri/src/lib.rs
// Asistan — Tauri v2 uygulama çekirdeği
// System tray, native file dialog ve store komutları burada tanımlanır.

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, Runtime,
};

// ─────────────────────────────────────────────────────────────────────────────
// Tauri Komutları (frontend → Rust IPC)
// ─────────────────────────────────────────────────────────────────────────────

/// Uygulamanın ana penceresini gösterir ve öne getirir.
#[tauri::command]
fn show_window(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

/// Native dosya seçici diyalogu açar; seçilen dosyanın yolunu döner.
/// Frontend, bu yolu /upload endpoint'ine göndermek için kullanır.
/// Not: Gerçek dosya okuma Rust'ta değil, frontend'de File API ile yapılır.
/// Bu komut sadece yol bilgisini döner.
#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

// ─────────────────────────────────────────────────────────────────────────────
// Uygulama Giriş Noktası
// ─────────────────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // Plugin'ler
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        // Komutlar
        .invoke_handler(tauri::generate_handler![show_window, get_app_version])
        // Kurulum
        .setup(|app| {
            setup_tray(app)?;
            Ok(())
        })
        // Pencere kapatma → tray'e küçült
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Pencereyi kapatmak yerine gizle
                window.hide().unwrap_or_default();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("Asistan başlatılırken hata oluştu");
}

// ─────────────────────────────────────────────────────────────────────────────
// System Tray Kurulumu
// ─────────────────────────────────────────────────────────────────────────────

fn setup_tray<R: Runtime>(app: &mut tauri::App<R>) -> tauri::Result<()> {
    // Tray menü öğeleri
    let show_item = MenuItem::with_id(app, "show", "Asistan'ı Aç", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Çıkış", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

    let _tray = TrayIconBuilder::with_id("main-tray")
        .icon(app.default_window_icon().unwrap().clone())
        .tooltip("Asistan — AI Asistanı")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            // Çift tıkla pencereyi aç
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}
