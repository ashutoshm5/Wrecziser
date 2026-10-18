#![windows_subsystem = "windows"]

use std::io::{self, Read, Write};
use std::net::TcpStream;
use std::os::windows::process::CommandExt;
use std::process::{Command, Stdio};
use std::time::Duration;

const CREATE_NO_WINDOW: u32 = 0x08000000;
const DETACHED_PROCESS: u32 = 0x00000008;
const SW_RESTORE: i32 = 9;

#[link(name = "user32")]
extern "system" {
    fn SetForegroundWindow(hWnd: isize) -> i32;
    fn ShowWindow(hWnd: isize, nCmdShow: i32) -> i32;
    fn EnumWindows(lpEnumFunc: extern "system" fn(isize, isize) -> i32, lParam: isize) -> i32;
    fn GetWindowTextW(hWnd: isize, lpString: *mut u16, nMaxCount: i32) -> i32;
    fn GetClassNameW(hWnd: isize, lpClassName: *mut u16, nMaxCount: i32) -> i32;
    fn IsWindowVisible(hWnd: isize) -> i32;
}

static mut FOUND_HWND: isize = 0;

extern "system" fn enum_windows_callback(hwnd: isize, _lparam: isize) -> i32 {
    unsafe {
        if IsWindowVisible(hwnd) != 0 {
            let mut class_buf = [0u16; 256];
            let class_len = GetClassNameW(hwnd, class_buf.as_mut_ptr(), 256);
            if class_len > 0 {
                let class_name = String::from_utf16_lossy(&class_buf[..class_len as usize]);
                if class_name == "ConsoleWindowClass" || class_name == "CASCADIA_HOSTING_WINDOW_CLASS" || class_name == "PseudoConsoleWindow" {
                    return 1; // NEVER match console or terminal windows
                }
            }

            let mut buf = [0u16; 512];
            let len = GetWindowTextW(hwnd, buf.as_mut_ptr(), 512);
            if len > 0 {
                let title = String::from_utf16_lossy(&buf[..len as usize]);
                if title.trim() == "Wrecziser" {
                    FOUND_HWND = hwnd;
                    return 0; // stop enumeration
                }
            }
        }
        1 // continue enumeration
    }
}

fn bring_wrecziser_to_front() -> bool {
    unsafe {
        FOUND_HWND = 0;
        EnumWindows(enum_windows_callback, 0);
        if FOUND_HWND != 0 {
            ShowWindow(FOUND_HWND, SW_RESTORE);
            SetForegroundWindow(FOUND_HWND);
            return true;
        }
    }
    false
}

fn is_backend_online() -> bool {
    TcpStream::connect_timeout(
        &"127.0.0.1:8000".parse().unwrap(),
        Duration::from_millis(300),
    )
    .is_ok()
}

fn get_root_dir() -> std::path::PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| std::path::PathBuf::from("."))
}

fn ensure_backend_silent() {
    if is_backend_online() {
        return;
    }

    let root_dir = get_root_dir();
    let backend_dir = root_dir.join("Wrecziser backend");
    let mut python_exe = backend_dir.join(".venv").join("Scripts").join("pythonw.exe");
    if !python_exe.exists() {
        python_exe = backend_dir.join(".venv").join("Scripts").join("python.exe");
    }
    let python_cmd = if python_exe.exists() {
        python_exe.to_string_lossy().to_string()
    } else {
        "pythonw".to_string()
    };
    let main_py = backend_dir.join("main.py");

    let _ = Command::new(&python_cmd)
        .arg(&main_py)
        .current_dir(&backend_dir)
        .creation_flags(CREATE_NO_WINDOW | DETACHED_PROCESS)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn();

    // Poll until port 8000 is verified warmed up
    for _ in 0..25 {
        std::thread::sleep(Duration::from_millis(200));
        if is_backend_online() {
            break;
        }
    }
}

#[link(name = "shell32")]
extern "system" {
    fn ShellExecuteW(
        hwnd: isize,
        operation: *const u16,
        file: *const u16,
        parameters: *const u16,
        directory: *const u16,
        show_cmd: i32,
    ) -> isize;
}

fn to_wide_null(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn log(msg: &str) {
    use std::fs::OpenOptions;
    let log_path = get_root_dir().join("native_host.log");
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = writeln!(f, "[{}]", msg);
    }
}

fn open_wrecziser_window() {
    log("open_wrecziser_window started");
    ensure_backend_silent();

    // Check if Wrecziser is already running and bring it to front
    if bring_wrecziser_to_front() {
        log("wrecziser already running, brought to front");
        return;
    }

    log("spawning wrecziser.exe via ShellExecuteW");
    let root_dir = get_root_dir();
    let wrecziser_exe = root_dir.join("wrecziser.exe");
    let file = to_wide_null(&wrecziser_exe.to_string_lossy());
    let dir = to_wide_null(&root_dir.to_string_lossy());
    let op = to_wide_null("open");
    unsafe {
        ShellExecuteW(0, op.as_ptr(), file.as_ptr(), std::ptr::null(), dir.as_ptr(), 1);
    }
    log("wrecziser.exe spawned via ShellExecuteW");
}

fn main() {
    log("native_host main started");
    let mut stdin = io::stdin();
    let mut len_buf = [0u8; 4];

    if stdin.read_exact(&mut len_buf).is_ok() {
        let msg_len = u32::from_le_bytes(len_buf) as usize;
        log(&format!("read len: {}", msg_len));
        let mut msg_buf = vec![0u8; msg_len];

        if stdin.read_exact(&mut msg_buf).is_ok() {
            let msg = String::from_utf8_lossy(&msg_buf);
            log(&format!("read msg: {}", msg));

            if msg.contains("open_app") {
                open_wrecziser_window();
            } else if msg.contains("start") {
                ensure_backend_silent();
            } else {
                ensure_backend_silent();
            }
        }
    } else {
        log("stdin.read_exact len failed");
    }

    log("writing response to stdout");
    let response = b"{\"status\":\"ok\",\"started\":true}";
    let len = (response.len() as u32).to_le_bytes();
    let mut stdout = io::stdout().lock();
    let _ = stdout.write_all(&len);
    let _ = stdout.write_all(response);
    let _ = stdout.flush();
    log("response sent, exiting main with std::process::exit(0)");
    std::process::exit(0);
}
