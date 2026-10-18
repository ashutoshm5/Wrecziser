#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  eprintln!(">>> [Tauri] app_lib::run() starting...");
  tauri::Builder::default()
    .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
      use tauri::Manager;
      if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
        let _ = window.set_always_on_top(true);
        let _ = window.set_always_on_top(false);
      }
    }))
    .setup(|app| {
      eprintln!(">>> [Tauri] setup callback triggered");
      use tauri::Manager;
      if let Some(window) = app.get_webview_window("main") {
        eprintln!(">>> [Tauri] Window 'main' found, forcing show & focus");
        let icon_bytes = include_bytes!("../icons/128x128.png");
        if let Ok(icon) = tauri::image::Image::from_bytes(icon_bytes) {
          let _ = window.set_icon(icon);
          eprintln!(">>> [Tauri] Explicit window icon set successfully");
        }
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
        let _ = window.set_always_on_top(true);
        let _ = window.set_always_on_top(false);
      } else {
        eprintln!(">>> [Tauri] Window 'main' was not found in setup!");
      }

      std::thread::spawn(|| {
        ensure_backend_and_ollama();
      });

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while building tauri application");
}

fn ensure_backend_and_ollama() {
  use std::net::TcpStream;
  use std::time::Duration;
  use std::process::Command;

  #[cfg(windows)]
  use std::os::windows::process::CommandExt;
  #[cfg(windows)]
  const CREATE_NO_WINDOW: u32 = 0x08000000;

  // 1. Check if Backend (port 8000) is running
  let backend_up = TcpStream::connect_timeout(
    &"127.0.0.1:8000".parse().unwrap(),
    Duration::from_millis(400),
  ).is_ok();

  if !backend_up {
    eprintln!(">>> [Tauri] Backend not detected on port 8000, launching Wrecziser backend...");
    let exe_path = std::env::current_exe().unwrap_or_default();
    let mut search_dirs = Vec::new();

    if let Some(parent) = exe_path.parent() {
      search_dirs.push(parent.to_path_buf());
      if let Some(grandparent) = parent.parent() {
        search_dirs.push(grandparent.to_path_buf());
        if let Some(great) = grandparent.parent() {
          search_dirs.push(great.to_path_buf());
        }
      }
    }

    for base in search_dirs {
      let backend_dir = base.join("Wrecziser backend");
      let mut python_exe = backend_dir.join(".venv").join("Scripts").join("pythonw.exe");
      if !python_exe.exists() {
        python_exe = backend_dir.join(".venv").join("Scripts").join("python.exe");
      }
      let main_py = backend_dir.join("main.py");

      let python_cmd = if python_exe.exists() {
        python_exe.to_string_lossy().to_string()
      } else {
        "pythonw".to_string()
      };

      if main_py.exists() {
        eprintln!(">>> [Tauri] Found backend at: {:?}", backend_dir);
        let mut cmd = Command::new(&python_cmd);
        cmd.arg(&main_py).current_dir(&backend_dir);
        cmd.stdin(std::process::Stdio::null())
          .stdout(std::process::Stdio::null())
          .stderr(std::process::Stdio::null());
        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);
        match cmd.spawn() {
          Ok(_) => {
            eprintln!(">>> [Tauri] Backend spawned successfully");
            break;
          }
          Err(e) => eprintln!(">>> [Tauri] Failed to spawn backend: {:?}", e),
        }
      }
    }
  }

  // 2. Check if Ollama (port 11434) is running
  let ollama_up = TcpStream::connect_timeout(
    &"127.0.0.1:11434".parse().unwrap(),
    Duration::from_millis(400),
  ).is_ok();

  if !ollama_up {
    eprintln!(">>> [Tauri] Ollama not detected on port 11434, launching ollama serve...");
    let mut cmd = Command::new("ollama");
    cmd.arg("serve");
    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);
    let _ = cmd.spawn();
  }
}

