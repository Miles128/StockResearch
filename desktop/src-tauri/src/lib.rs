//! StockResearch desktop shell: spawn local API, open window, clean up on exit.

use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

const API_HOST: &str = "127.0.0.1";
const DEFAULT_API_PORT: u16 = 8000;
const HEALTH_PATH: &str = "/health";
const READY_TIMEOUT: Duration = Duration::from_secs(90);
const POLL_INTERVAL: Duration = Duration::from_millis(400);

fn api_port() -> u16 {
    std::env::var("STOCKRESEARCH_DESKTOP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(DEFAULT_API_PORT)
}

struct BackendChildren {
    api: Option<Child>,
    worker: Option<Child>,
    /// True when this shell started the API (so we should kill it on exit).
    owns_api: bool,
}

impl BackendChildren {
    fn kill_owned(&mut self) {
        if self.owns_api {
            if let Some(mut child) = self.api.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
        if let Some(mut child) = self.worker.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

impl Drop for BackendChildren {
    fn drop(&mut self) {
        self.kill_owned();
    }
}

struct BackendState(Mutex<Option<BackendChildren>>);

fn repo_root() -> PathBuf {
    if let Ok(root) = std::env::var("STOCKRESEARCH_ROOT") {
        let path = PathBuf::from(root);
        if path.is_dir() {
            return path;
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

fn api_base() -> String {
    format!("http://{API_HOST}:{}", api_port())
}

fn health_ok() -> bool {
    let port = api_port();
    let addr = format!("{API_HOST}:{port}");
    if TcpStream::connect_timeout(
        &addr.parse().expect("static addr"),
        Duration::from_millis(200),
    )
    .is_err()
    {
        return false;
    }
    let url = format!("{}{HEALTH_PATH}", api_base());
    Command::new(if cfg!(windows) { "curl.exe" } else { "curl" })
        .args(["-fsS", "--max-time", "2", &url])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn which(bin: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join(bin);
        if candidate.is_file() {
            return Some(candidate);
        }
        #[cfg(windows)]
        {
            let exe = dir.join(format!("{bin}.exe"));
            if exe.is_file() {
                return Some(exe);
            }
        }
    }
    None
}

fn find_uv() -> PathBuf {
    if let Ok(uv) = std::env::var("STOCKRESEARCH_UV") {
        return PathBuf::from(uv);
    }
    which("uv").unwrap_or_else(|| PathBuf::from("uv"))
}

fn spawn_api(root: &Path, uv: &Path) -> std::io::Result<Child> {
    let mut cmd = Command::new(uv);
    cmd.args([
        "run",
        "uvicorn",
        "stockresearch.api.app:app",
        "--host",
        API_HOST,
        "--port",
        &api_port().to_string(),
        "--app-dir",
        "src",
    ])
    .current_dir(root)
    .stdin(Stdio::null())
    .stdout(Stdio::null())
    .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.spawn()
}

fn spawn_worker(root: &Path, uv: &Path) -> std::io::Result<Child> {
    let mut cmd = Command::new(uv);
    cmd.args(["run", "python", "-m", "stockresearch", "worker"])
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.spawn()
}

fn wait_until_ready(timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if health_ok() {
            return true;
        }
        thread::sleep(POLL_INTERVAL);
    }
    false
}

fn ensure_web_dist(root: &Path) -> Result<(), String> {
    let dist = root.join("web/dist/index.html");
    if dist.is_file() {
        return Ok(());
    }
    Err(format!(
        "未找到前端构建产物：{}\n请先执行：cd web && npm run build",
        dist.display()
    ))
}

fn start_backend(root: &Path) -> Result<BackendChildren, String> {
    ensure_web_dist(root)?;
    let uv = find_uv();
    if which("uv").is_none() && !uv.is_file() {
        return Err(
            "未找到 uv。请安装 https://github.com/astral-sh/uv 或设置 STOCKRESEARCH_UV".into(),
        );
    }

    let mut children = BackendChildren {
        api: None,
        worker: None,
        owns_api: false,
    };

    if health_ok() {
        children.owns_api = false;
    } else {
        let child = spawn_api(root, &uv).map_err(|e| format!("启动 API 失败: {e}"))?;
        children.api = Some(child);
        children.owns_api = true;
        if !wait_until_ready(READY_TIMEOUT) {
            children.kill_owned();
            return Err(format!(
                "API 在 {}s 内未就绪（{}{}）。请确认已 uv sync，并查看终端日志。",
                READY_TIMEOUT.as_secs(),
                api_base(),
                HEALTH_PATH
            ));
        }
    }

    let worker_on = matches!(
        std::env::var("STOCKRESEARCH_DESKTOP_WORKER").as_deref(),
        Ok("1") | Ok("true") | Ok("TRUE") | Ok("yes")
    );
    if worker_on {
        match spawn_worker(root, &uv) {
            Ok(child) => children.worker = Some(child),
            Err(e) => {
                eprintln!("[stockresearch-desktop] worker 启动失败（可忽略）: {e}");
            }
        }
    }

    Ok(children)
}

fn build_main_window(app: &tauri::App, url: WebviewUrl) -> tauri::Result<tauri::WebviewWindow> {
    WebviewWindowBuilder::new(app, "main", url)
        .title("StockResearch")
        .inner_size(1440.0, 900.0)
        .min_inner_size(1100.0, 700.0)
        .resizable(true)
        .center()
        .build()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let root = repo_root();
            match start_backend(&root) {
                Ok(children) => {
                    app.manage(BackendState(Mutex::new(Some(children))));
                    let url = url::Url::parse(&api_base()).expect("static api url");
                    build_main_window(app, WebviewUrl::External(url))?;
                }
                Err(err) => {
                    eprintln!("[stockresearch-desktop] {err}");
                    app.manage(BackendState(Mutex::new(None)));
                    // Local splash with error details.
                    let window = build_main_window(app, WebviewUrl::App("index.html".into()))?;
                    let html = format!(
                        "<!doctype html><meta charset=utf-8><body style='font-family:system-ui;padding:2rem;background:#0b1220;color:#e8eefc'><h1>启动失败</h1><pre style='white-space:pre-wrap'>{err}</pre><p>仓库根：{}</p></body>",
                        root.display()
                    );
                    let _ = window.eval(&format!(
                        "document.open();document.write({});document.close();",
                        serde_json::to_string(&html).unwrap_or_else(|_| "\"error\"".into())
                    ));
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building StockResearch desktop")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<BackendState>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut children) = guard.take() {
                            children.kill_owned();
                        }
                    }
                }
            }
        });
}
