#![windows_subsystem = "windows"]

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

#[cfg(windows)]
use std::os::windows::process::CommandExt;
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[link(name = "user32")]
extern "system" {
    fn MessageBoxW(hWnd: isize, lpText: *const u16, lpCaption: *const u16, uType: u32) -> i32;
}

const MB_OK: u32 = 0x00000000;
const MB_YESNO: u32 = 0x00000004;
const MB_ICONQUESTION: u32 = 0x00000020;
const MB_ICONINFORMATION: u32 = 0x00000040;
const IDYES: i32 = 6;

fn to_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn get_real_desktop() -> PathBuf {
    // 1. Try PowerShell to query real Windows special folder (handles OneDrive Desktop redirection)
    let mut cmd = Command::new("powershell");
    cmd.args(["-NoProfile", "-NonInteractive", "-Command", "[Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)"]);
    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);
    if let Ok(output) = cmd.output() {
        if output.status.success() {
            let s = String::from_utf8_lossy(&output.stdout).trim().to_string();
            let p = PathBuf::from(&s);
            if p.exists() {
                return p;
            }
        }
    }

    // 2. Fallbacks
    if let Ok(user_profile) = env::var("USERPROFILE") {
        let onedrive_desktop = PathBuf::from(&user_profile).join("OneDrive").join("Desktop");
        if onedrive_desktop.exists() {
            return onedrive_desktop;
        }
        let std_desktop = PathBuf::from(&user_profile).join("Desktop");
        if std_desktop.exists() {
            return std_desktop;
        }
    }

    PathBuf::from(".")
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let is_silent = args.iter().any(|a| a == "--silent" || a == "/S" || a == "-s");

    if !is_silent {
        let text = to_wide("Are you sure you want to completely uninstall Wrecziser and remove all its components?");
        let caption = to_wide("Wrecziser Uninstall");
        let result = unsafe { MessageBoxW(0, text.as_ptr(), caption.as_ptr(), MB_YESNO | MB_ICONQUESTION) };
        if result != IDYES {
            return;
        }
    }

    // 1. Terminate running Wrecziser instances
    let _ = Command::new("taskkill")
        .args(["/F", "/IM", "wrecziser.exe", "/T"])
        .creation_flags(CREATE_NO_WINDOW)
        .status();

    // 2. Remove Desktop Shortcuts
    let desktop = get_real_desktop();
    let _ = fs::remove_file(desktop.join("Wrecziser.lnk"));
    let _ = fs::remove_file(desktop.join("Wrecziser Extension Setup Guide.txt"));

    if let Ok(user_profile) = env::var("USERPROFILE") {
        let _ = fs::remove_file(PathBuf::from(&user_profile).join("Desktop").join("Wrecziser.lnk"));
        let _ = fs::remove_file(PathBuf::from(&user_profile).join("Desktop").join("Wrecziser Extension Setup Guide.txt"));
        let _ = fs::remove_file(PathBuf::from(&user_profile).join("OneDrive").join("Desktop").join("Wrecziser.lnk"));
        let _ = fs::remove_file(PathBuf::from(&user_profile).join("OneDrive").join("Desktop").join("Wrecziser Extension Setup Guide.txt"));
    }

    // 3. Remove Start Menu Shortcut
    if let Ok(app_data) = env::var("APPDATA") {
        let start_menu_lnk = PathBuf::from(&app_data)
            .join("Microsoft")
            .join("Windows")
            .join("Start Menu")
            .join("Programs")
            .join("Wrecziser.lnk");
        let _ = fs::remove_file(start_menu_lnk);
    }

    // 4. Remove Windows Registry Keys
    let _ = Command::new("reg")
        .args(["delete", "HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\com.wrecz.wrecziser", "/f"])
        .creation_flags(CREATE_NO_WINDOW)
        .status();

    let _ = Command::new("reg")
        .args(["delete", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Wrecziser", "/f"])
        .creation_flags(CREATE_NO_WINDOW)
        .status();

    // 5. Locate Install Directory and Self-Delete
    let current_exe = env::current_exe().unwrap_or_default();
    let install_dir = current_exe.parent().unwrap_or(Path::new(""));

    if install_dir.exists() {
        let install_dir_str = install_dir.to_string_lossy().to_string();
        let cmd_str = format!("ping 127.0.0.1 -n 2 > nul & rmdir /s /q \"{}\"", install_dir_str);

        let _ = Command::new("cmd")
            .args(["/c", &cmd_str])
            .creation_flags(CREATE_NO_WINDOW)
            .spawn();
    }

    // 6. Show Success Dialog
    if !is_silent {
        let text = to_wide("Wrecziser was successfully removed from your computer.");
        let caption = to_wide("Uninstall Complete");
        unsafe { MessageBoxW(0, text.as_ptr(), caption.as_ptr(), MB_OK | MB_ICONINFORMATION) };
    }
}
