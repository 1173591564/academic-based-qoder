use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::env;
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use tauri::{AppHandle, Emitter, Manager, State};
use std::sync::Mutex;
use std::collections::HashMap;

struct ChildPid(Mutex<HashMap<String, u32>>);

/// Cache for build_system_prompt results (key = work_dir|scholar_home, value = prompt)
struct PromptCache(Mutex<Option<(String, String)>>);

/// Get the path to scholar.exe
fn get_scholar_path() -> Result<PathBuf, String> {
    // In development mode, CARGO_MANIFEST_DIR = desktop/src-tauri
    // Go up 2 levels to reach project root, then dist/scholar/scholar.exe
    if cfg!(debug_assertions) {
        // option_env! embeds the value at compile time (env::var reads runtime env, which is wrong)
        let manifest_dir = option_env!("CARGO_MANIFEST_DIR").unwrap_or("");
        if !manifest_dir.is_empty() {
            let exe_path = PathBuf::from(&manifest_dir)
                .parent()
                .and_then(|p| p.parent())
                .map(|p| p.join("dist").join("scholar").join("scholar.exe"));
            if let Some(exe_path) = exe_path {
                if exe_path.exists() {
                    return Ok(exe_path);
                }
            }
        }
        // Fallback: try relative to current exe
        if let Ok(exe) = env::current_exe() {
            let project_root = exe.parent().and_then(|p| p.parent()).and_then(|p| p.parent());
            if let Some(root) = project_root {
                let fallback = root.join("dist").join("scholar").join("scholar.exe");
                if fallback.exists() {
                    return Ok(fallback);
                }
            }
        }
        return Err("scholar.exe not found (checked dist/scholar/scholar.exe)".to_string());
    }

    // In production, scholar.exe is next to the app executable
    env::current_exe()
        .map_err(|e| e.to_string())
        .and_then(|p| {
            let exe_dir = p.parent().ok_or("Failed to get exe dir")?;
            Ok(exe_dir.join("scholar.exe"))
        })
}

/// Get SCHOLAR_HOME - in dev mode, point to the project root where data lives
fn get_scholar_home() -> String {
    if let Ok(home) = env::var("SCHOLAR_HOME") {
        return home;
    }
    // In dev mode, compute project root from CARGO_MANIFEST_DIR (compile-time macro)
    if cfg!(debug_assertions) {
        if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
            if let Some(project_root) = PathBuf::from(manifest_dir)
                .parent()
                .and_then(|p| p.parent())
            {
                return project_root.to_string_lossy().to_string();
            }
        }
        // Fallback: try relative to current exe
        if let Ok(exe) = env::current_exe() {
            if let Some(root) = exe.parent().and_then(|p| p.parent()).and_then(|p| p.parent()) {
                return root.to_string_lossy().to_string();
            }
        }
    }
    // Production default
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    home.join(".scholar-studio")
        .to_string_lossy()
        .to_string()
}

/// Run scholar.exe with given arguments and return stdout as string
fn run_scholar(args: &[&str]) -> Result<String, String> {
    let exe_path = get_scholar_path()?;
    let scholar_home = get_scholar_home();

    let output = Command::new(&exe_path)
        .args(args)
        .env("SCHOLAR_HOME", &scholar_home)
        .output()
        .map_err(|e| format!("Failed to run scholar.exe: {}", e))?;

    if !output.status.success() {
        // Try to parse structured JSON error from stdout first
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Ok(json_err) = serde_json::from_str::<Value>(&stdout) {
            if let Some(err_msg) = json_err.get("error").and_then(|v| v.as_str()) {
                return Err(err_msg.to_string());
            }
        }
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("scholar.exe failed: {}", stderr));
    }

    String::from_utf8(output.stdout).map_err(|e| format!("Invalid UTF-8: {}", e))
}

#[tauri::command]
fn get_stats() -> Result<Value, String> {
    let output = run_scholar(&["stats", "--json"])?;
    serde_json::from_str(&output).map_err(|e| format!("Failed to parse JSON: {}", e))
}

#[tauri::command]
fn search_papers(query: String) -> Result<Value, String> {
    if query.is_empty() || query.starts_with('-') {
        return Err("Invalid search query".to_string());
    }
    let output = run_scholar(&["search", "--json", "--", &query])?;
    serde_json::from_str(&output).map_err(|e| format!("Failed to parse JSON: {}", e))
}

#[tauri::command]
fn get_paper_info(paper_id: String) -> Result<Value, String> {
    if paper_id.is_empty() || paper_id.starts_with('-') {
        return Err("Invalid paper ID".to_string());
    }
    let output = run_scholar(&["info", "--json", "--", &paper_id])?;
    serde_json::from_str(&output).map_err(|e| format!("Failed to parse JSON: {}", e))
}

/* ============================================================ */
/*  Data structures for new commands                             */
/* ============================================================ */

#[derive(Serialize)]
struct FileNode {
    name: String,
    path: String,
    is_dir: bool,
    children: Option<Vec<FileNode>>,
}

#[derive(Serialize)]
struct Conversation {
    id: String,
    title: String,
    date: String,
    preview: String,
    message_count: u32,
}

#[derive(Serialize, Deserialize)]
struct ChatMessageRecord {
    id: String,
    role: String,
    content: String,
    timestamp: String,
}

#[derive(Serialize, Deserialize)]
struct ConversationRecord {
    id: String,
    title: String,
    created_at: String,
    updated_at: String,
    work_dir: String,
    cli_ide: String,
    session_id: String,
    messages: Vec<ChatMessageRecord>,
}

/// Recursively build a file tree from a directory.
/// Directories are listed first, then files, alphabetically.
/// Limits to 50 entries per directory and `max_depth` levels.
fn build_file_tree(base: &PathBuf, current: &PathBuf, max_depth: u32, depth: u32) -> Vec<FileNode> {
    if depth >= max_depth {
        return vec![];
    }

    let mut nodes = vec![];
    let entries = match fs::read_dir(current) {
        Ok(e) => e,
        Err(_) => return vec![],
    };

    let mut items: Vec<_> = entries.filter_map(|e| e.ok()).collect();
    items.sort_by(|a, b| {
        let a_dir = a.path().is_dir();
        let b_dir = b.path().is_dir();
        b_dir.cmp(&a_dir).then_with(|| a.file_name().cmp(&b.file_name()))
    });

    let mut count = 0u32;
    for entry in items {
        if count >= 50 {
            break;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with('.')
            || name == "node_modules"
            || name == "__pycache__"
            || name == "target"
        {
            continue;
        }
        count += 1;

        let entry_path = entry.path();
        let is_dir = entry_path.is_dir();
        let relative = entry_path
            .strip_prefix(base)
            .unwrap_or(&entry_path)
            .to_string_lossy()
            .to_string()
            .replace('\\', "/");

        let children = if is_dir {
            Some(build_file_tree(base, &entry_path, max_depth, depth + 1))
        } else {
            None
        };

        nodes.push(FileNode {
            name,
            path: relative,
            is_dir,
            children,
        });
    }
    nodes
}

#[tauri::command]
fn list_workspace_files(work_dir: String) -> Result<Vec<FileNode>, String> {
    let base = if work_dir.is_empty() { get_scholar_home() } else { work_dir };
    let output_dir = PathBuf::from(&base).join("output");

    if !output_dir.exists() {
        return Ok(vec![]);
    }

    Ok(build_file_tree(&output_dir, &output_dir, 3, 0))
}

#[tauri::command]
fn list_conversations(work_dir: String) -> Result<Vec<Conversation>, String> {
    let base = if work_dir.is_empty() { get_scholar_home() } else { work_dir };
    let conv_dir = PathBuf::from(&base).join(".scholar-studio").join("conversations");

    if !conv_dir.exists() {
        return Ok(vec![]);
    }

    let mut conversations = vec![];
    let entries = match fs::read_dir(&conv_dir) {
        Ok(e) => e,
        Err(_) => return Ok(vec![]),
    };

    let mut items: Vec<_> = entries.filter_map(|e| e.ok()).collect();
    items.sort_by(|a, b| b.file_name().cmp(&a.file_name()));

    for entry in items {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if !name.ends_with(".json") {
            continue;
        }

        let content = fs::read_to_string(&path).unwrap_or_default();
        if let Ok(record) = serde_json::from_str::<Value>(&content) {
            let id = record.get("id").and_then(|v| v.as_str()).unwrap_or(&name).to_string();
            let title = record.get("title").and_then(|v| v.as_str()).unwrap_or("（无标题）").to_string();
            let date = record.get("updated_at").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let msg_count = record.get("messages")
                .and_then(|m| m.as_array())
                .map(|a| a.len() as u32)
                .unwrap_or(0);

            let preview: String = record.get("messages")
                .and_then(|m| m.as_array())
                .and_then(|a| a.first())
                .and_then(|first| first.get("content"))
                .and_then(|c| c.as_str())
                .unwrap_or("（无预览）")
                .chars()
                .take(100)
                .collect();

            conversations.push(Conversation {
                id,
                title,
                date,
                preview,
                message_count: msg_count,
            });
        }
    }

    Ok(conversations)
}

/// Sanitize conversation ID to prevent path traversal attacks.
/// Only allows alphanumeric characters and hyphens.
fn sanitize_conversation_id(id: &str) -> Result<String, String> {
    if id.is_empty() {
        return Err("对话 ID 不能为空".to_string());
    }
    if !id.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
        return Err(format!("对话 ID 包含非法字符: {}", id));
    }
    Ok(id.to_string())
}

/// Validate that a work_dir path doesn't contain path traversal patterns.
fn validate_work_dir(work_dir: &str) -> Result<String, String> {
    if work_dir.is_empty() {
        return Err("工作目录不能为空".to_string());
    }
    // Reject obvious traversal patterns
    if work_dir.contains("..") {
        return Err("工作目录不能包含 .. 路径穿越".to_string());
    }
    let p = PathBuf::from(work_dir);
    if !p.is_absolute() {
        return Err("工作目录必须是绝对路径".to_string());
    }
    Ok(work_dir.to_string())
}

#[tauri::command]
fn save_conversation(record: ConversationRecord) -> Result<(), String> {
    let _ = sanitize_conversation_id(&record.id)?;
    let _ = validate_work_dir(&record.work_dir)?;
    let dir = PathBuf::from(&record.work_dir)
        .join(".scholar-studio")
        .join("conversations");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join(format!("{}.json", record.id));
    let json = serde_json::to_string_pretty(&record).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn load_conversation(id: String, work_dir: String) -> Result<ConversationRecord, String> {
    let safe_id = sanitize_conversation_id(&id)?;
    let base = if work_dir.is_empty() { get_scholar_home() } else { validate_work_dir(&work_dir)? };
    let path = PathBuf::from(&base)
        .join(".scholar-studio")
        .join("conversations")
        .join(format!("{}.json", safe_id));
    let content = fs::read_to_string(&path)
        .map_err(|e| format!("对话不存在: {}", e))?;
    serde_json::from_str(&content)
        .map_err(|e| format!("解析失败: {}", e))
}

/// Qoder CLI specific search paths (common install locations)
fn qodercli_search_paths() -> Vec<PathBuf> {
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    let mut paths = vec![
        home.join(".qoder").join("bin").join("qodercli").join("qodercli.exe"),
        home.join(".qoder").join("bin").join("qodercli"),
        home.join("AppData").join("Local").join("Programs").join("Qoder").join("bin").join("qoder.cmd"),
    ];
    if cfg!(windows) {
        paths.push(PathBuf::from("C:/Program Files/Qoder/bin/qoder.cmd"));
        paths.push(PathBuf::from("C:/Program Files (x86)/Qoder/bin/qoder.cmd"));
    } else {
        paths.push(PathBuf::from("/usr/local/bin/qodercli"));
        paths.push(PathBuf::from("/usr/bin/qodercli"));
    }
    paths
}

/// Find CLI executable path (shared logic for detect_cli and invoke_agent_stream)
fn find_cli_path(cli_ide: &str) -> Option<String> {
    let (cmd_name, fallback_paths) = match cli_ide {
        "claude-code" => ("claude", {
            let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
            let mut paths: Vec<PathBuf> = if cfg!(windows) {
                vec![
                    home.join(".local").join("bin").join("claude.exe"),
                    home.join(".local").join("bin").join("claude.cmd"),
                    home.join("AppData").join("Roaming").join("npm").join("claude.cmd"),
                    home.join("AppData").join("Roaming").join("npm").join("claude.ps1"),
                    home.join("AppData").join("Local").join("Programs").join("claude.exe"),
                ]
            } else {
                vec![
                    home.join(".local").join("bin").join("claude"),
                    home.join(".cargo").join("bin").join("claude"),
                    PathBuf::from("/usr/local/bin/claude"),
                    PathBuf::from("/usr/bin/claude"),
                ]
            };
            paths.extend(qodercli_search_paths());
            paths
        }),
        "qoder-cli" => ("qodercli", qodercli_search_paths()),
        _ => return None,
    };

    // 1. Try where / which
    #[cfg(windows)]
    let probe = Command::new("where").arg(cmd_name).output();
    #[cfg(not(windows))]
    let probe = Command::new("which").arg(cmd_name).output();

    if let Ok(out) = probe {
        if out.status.success() {
            let path = String::from_utf8_lossy(&out.stdout);
            let first = path.lines().next().unwrap_or("").trim();
            if !first.is_empty() {
                return Some(first.to_string());
            }
        }
    }

    // 2. Fallback: check known install locations
    for c in &fallback_paths {
        if c.as_os_str().is_empty() { continue; }
        if c.exists() {
            return Some(c.to_string_lossy().to_string());
        }
    }

    None
}

/// Detect CLI executable path via `where`/`which`, then fallback to common install locations
#[tauri::command]
fn detect_cli(cli_ide: String) -> Result<String, String> {
    find_cli_path(&cli_ide).ok_or_else(|| {
        let cmd_name = match cli_ide.as_str() {
            "claude-code" => "claude",
            "qoder-cli" => "qodercli",
            _ => &cli_ide,
        };
        format!("未找到 {} CLI，请确认已安装或手动填写路径", cmd_name)
    })
}

/// Read a rule file, stripping YAML front-matter if present
fn read_rule_body(path: &PathBuf) -> Option<String> {
    let content = fs::read_to_string(path).ok()?;
    let body = if content.starts_with("---") {
        content.splitn(3, "---").nth(2).unwrap_or(&content).trim()
    } else {
        content.trim()
    };
    if body.is_empty() { None } else { Some(body.to_string()) }
}

/// Build a comprehensive system prompt from .qoder/rules/ and .claude/rules/ files
fn build_system_prompt(scholar_home: &str, work_dir: &str) -> String {
    let rule_files = [
        "identity.md", "onboarding.md", "pipelines.md", "tools.md",
        "memory-policy.md", "academic.md", "interest-capture.md",
    ];
    let mut parts = Vec::new();
    let mut seen = std::collections::HashSet::new();

    // Read from .qoder/rules/ first
    let qoder_rules = PathBuf::from(scholar_home).join(".qoder").join("rules");
    for name in &rule_files {
        let path = qoder_rules.join(name);
        if let Some(body) = read_rule_body(&path) {
            if seen.insert(name.to_string()) {
                parts.push(format!("## {}\n{}", name, body));
            }
        }
    }

    // Then .claude/rules/ (补差异，让 Claude Code 也能发现 Qoder-only 规则)
    let claude_rules = PathBuf::from(scholar_home).join(".claude").join("rules");
    for name in &rule_files {
        let path = claude_rules.join(name);
        if let Some(body) = read_rule_body(&path) {
            if seen.insert(name.to_string()) {
                parts.push(format!("## {}\n{}", name, body));
            }
        }
    }

    // List available skills (union of .qoder and .claude)
    let mut skills = std::collections::HashSet::new();
    for skills_dir_name in &[".qoder", ".claude"] {
        let skills_dir = PathBuf::from(scholar_home).join(skills_dir_name).join("skills");
        if let Ok(entries) = fs::read_dir(&skills_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                if entry.path().is_dir() {
                    skills.insert(entry.file_name().to_string_lossy().to_string());
                }
            }
        }
    }
    if !skills.is_empty() {
        let mut skill_list: Vec<String> = skills.into_iter().collect();
        skill_list.sort();
        parts.push(format!(
            "## Available Skills\n用户表达学术意图时，通过 read_skill MCP 工具读取对应 SKILL.md。\n可用 skills: {}",
            skill_list.join(", ")
        ));
    }

    // Environment info
    let ws = if work_dir.is_empty() { scholar_home } else { work_dir };
    parts.push(format!(
        "## Environment\n- SCHOLAR_HOME={} (知识库根目录)\n- WORKSPACE={} (当前工作目录)\n- 论文数据: output/parsed/<ULID>.json (560+ 篇)\n- 输出目录: output/ (notes/, drafts/, bib/, experiments/)\n- MCP 服务器已接入，提供 55 个学术工具 (35 直调 + 12 子进程 + 8 结构化)\n- 同时支持 Claude Code 与 Qoder CLI",
        scholar_home, ws
    ));

    parts.join("\n\n---\n\n")
}

/// Ensure CLAUDE.md exists in work_dir with Scholar Studio context.
/// Both Claude Code and Qoder CLI auto-discover CLAUDE.md, so this single
/// config file works for both IDE backends.
fn ensure_claude_config(work_dir: &str, scholar_home: &str) {
    if work_dir.is_empty() { return; }
    let claude_md = PathBuf::from(work_dir).join("CLAUDE.md");
    if claude_md.exists() { return; }

    let prompt = build_system_prompt(scholar_home, work_dir);
    let content = format!(
        "<!-- Auto-generated by Scholar Studio. Do not edit manually. -->\n\n# Scholar Studio — Project Instructions\n\n{}",
        prompt
    );
    let _ = fs::write(&claude_md, content);
}

/// RAII guard that removes a temp file on drop (even on panic).
struct TempFileGuard(PathBuf);
impl Drop for TempFileGuard {
    fn drop(&mut self) {
        if self.0.exists() {
            let _ = fs::remove_file(&self.0);
        }
    }
}

/// Invoke CLI IDE (Claude Code or Qoder CLI) with streaming output via Tauri events.
/// Both CLIs share the same MCP/session/output-format flags, so a single
/// implementation handles both backends.
fn invoke_agent_stream(
    app: &AppHandle,
    cli_ide: &str,
    message: &str,
    work_dir: &str,
    cli_path: Option<&str>,
    session_id: Option<&str>,
    is_first: bool,
) -> Result<(), String> {
    // Resolve CLI path: use provided path, or auto-detect
    let exe = match cli_path.filter(|p| !p.is_empty()) {
        Some(p) => p.to_string(),
        None => find_cli_path(cli_ide).unwrap_or_else(|| {
            match cli_ide {
                "qoder-cli" => "qodercli".to_string(),
                _ => "claude".to_string(),
            }
        }),
    };
    let scholar_home = get_scholar_home();

    ensure_claude_config(work_dir, &scholar_home);

    let mcp_cwd = if work_dir.is_empty() { scholar_home.clone() } else { work_dir.to_string() };
    let mcp_config = serde_json::json!({
        "mcpServers": {
            "scholar": {
                "command": "python",
                "args": ["-m", "scholar_mcp"],
                "cwd": &mcp_cwd,
                "env": {
                    "SCHOLAR_HOME": &scholar_home,
                    "SCHOLAR_WORKSPACE": &mcp_cwd,
                    "PYTHONPATH": &scholar_home
                }
            }
        }
    });

    let temp_dir = std::env::temp_dir();
    let mcp_filename = format!("scholar_mcp_config_{}.json", session_id.unwrap_or("default"));
    let mcp_path = temp_dir.join(&mcp_filename);
    let mcp_written = fs::write(&mcp_path, mcp_config.to_string()).is_ok();
    // RAII guard: ensures temp file cleanup even on panic
    let _mcp_guard = if mcp_written { Some(TempFileGuard(mcp_path.clone())) } else { None };

    // Use cached system prompt if available, otherwise build and cache
    let cache_key = format!("{}|{}", work_dir, scholar_home);
    let system_prompt = if let Some(state) = app.try_state::<PromptCache>() {
        if let Ok(guard) = state.0.lock() {
            if let Some((ref key, ref prompt)) = *guard {
                if key == &cache_key {
                    prompt.clone()
                } else {
                    String::new() // will be built below
                }
            } else {
                String::new()
            }
        } else {
            String::new()
        }
    } else {
        String::new()
    };
    let system_prompt = if system_prompt.is_empty() {
        let prompt = build_system_prompt(&scholar_home, work_dir);
        if let Some(state) = app.try_state::<PromptCache>() {
            if let Ok(mut guard) = state.0.lock() {
                *guard = Some((cache_key, prompt.clone()));
            }
        }
        prompt
    } else {
        system_prompt
    };

    // Direct invocation — avoids cmd.exe mangling special chars in system prompt
    let mut cmd = Command::new(&exe);

    if mcp_written {
        cmd.arg("--mcp-config").arg(&mcp_path);
    }
    // Safety: Windows command-line limit is 32KB; truncate system prompt if needed
    let safe_prompt = if system_prompt.len() > 30000 {
        eprintln!("Warning: system prompt truncated ({} -> 30000 chars)", system_prompt.len());
        system_prompt.chars().take(30000).collect::<String>()
    } else {
        system_prompt
    };
    cmd.arg("--append-system-prompt").arg(&safe_prompt);
    cmd.arg("--output-format").arg("stream-json");

    if let Some(sid) = session_id {
        if !sid.is_empty() {
            if is_first {
                cmd.arg("--session-id").arg(sid);
            } else {
                cmd.arg("--resume").arg(sid);
            }
        }
    }

    cmd.arg("-p").arg(message);

    if !work_dir.is_empty() {
        cmd.current_dir(work_dir);
    }
    cmd.env("SCHOLAR_HOME", &scholar_home);
    cmd.env("SCHOLAR_WORKSPACE", &mcp_cwd);
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| {
        let _ = fs::remove_file(&mcp_path);
        format!("无法启动 Claude Code CLI: {}", e)
    })?;

    // Store PID for stop_generation — use HashMap to track multiple sessions
    let pid = child.id();
    let session_key = session_id.unwrap_or("default").to_string();
    if let Some(state) = app.try_state::<ChildPid>() {
        if let Ok(mut guard) = state.0.lock() {
            // If previous process for this session exists, kill it first
            if let Some(old_pid) = guard.insert(session_key, pid) {
                #[cfg(windows)]
                { let _ = Command::new("taskkill").args(["/PID", &old_pid.to_string(), "/F", "/T"]).output(); }
                #[cfg(not(windows))]
                { let _ = Command::new("kill").arg("-9").arg(old_pid.to_string()).output(); }
            }
        }
    }

    // If stdout.take() fails, kill the child to prevent orphan process
    let stdout = match child.stdout.take() {
        Some(s) => s,
        None => {
            let _ = child.kill();
            let _ = child.wait();
            return Err("无法获取 stdout".to_string());
        }
    };
    let reader = BufReader::new(stdout);

    for line in reader.lines() {
        match line {
            Ok(text) => {
                if text.is_empty() { continue; }
                if let Ok(json) = serde_json::from_str::<Value>(&text) {
                    let msg_type = json.get("type").and_then(|v| v.as_str()).unwrap_or("");
                    match msg_type {
                        "assistant" => {
                            if let Some(content) = json.get("message")
                                .and_then(|m| m.get("content"))
                                .and_then(|c| c.as_array())
                            {
                                for block in content {
                                    if block.get("type").and_then(|t| t.as_str()) == Some("text") {
                                        if let Some(t) = block.get("text").and_then(|v| v.as_str()) {
                                            let _ = app.emit("chat-chunk", t.to_string());
                                        }
                                    }
                                }
                            }
                        }
                        "result" => { let _ = app.emit("chat-done", ()); }
                        _ => {}
                    }
                } else {
                    let _ = app.emit("chat-chunk", text);
                }
            }
            Err(_) => break,
        }
    }

    let status = child.wait().map_err(|e| format!("等待进程失败: {}", e))?;

    // Clean up PID from tracking map
    let session_key = session_id.unwrap_or("default").to_string();
    if let Some(state) = app.try_state::<ChildPid>() {
        if let Ok(mut guard) = state.0.lock() {
            guard.remove(&session_key);
        }
    }

    if !status.success() {
        let _ = app.emit("chat-error", format!("CLI ({}) 异常退出 (code: {:?})", cli_ide, status.code()));
    }

    Ok(())
}

#[tauri::command]
async fn chat_send(
    app: AppHandle,
    message: String,
    cli_ide: String,
    work_dir: String,
    cli_path: Option<String>,
    session_id: Option<String>,
    is_first: bool,
) -> Result<(), String> {
    if message.is_empty() {
        return Err("消息不能为空".to_string());
    }

    // Use spawn_blocking to avoid blocking the tokio async runtime
    let app_clone = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        invoke_agent_stream(
            &app_clone, &cli_ide, &message, &work_dir,
            cli_path.as_deref(), session_id.as_deref(), is_first,
        )
    })
    .await
    .map_err(|e| format!("Task join error: {}", e))?
}

#[tauri::command]
fn read_file(path: String, work_dir: String) -> Result<String, String> {
    // Security: reject path traversal attempts
    if path.contains("..") {
        return Err("路径不能包含 .. 穿越模式".to_string());
    }
    let base = if work_dir.is_empty() { get_scholar_home() } else { work_dir };
    let base_path = PathBuf::from(&base);
    let full_path = base_path.join(&path);

    // Security: verify resolved path stays within base directory
    let canonical_base = base_path.canonicalize().map_err(|e| e.to_string())?;
    let canonical_full = full_path.canonicalize().map_err(|e| e.to_string())?;
    if !canonical_full.starts_with(&canonical_base) {
        return Err("路径超出允许范围".to_string());
    }

    let metadata = fs::metadata(&canonical_full).map_err(|e| e.to_string())?;
    if metadata.len() > 1_000_000 {
        return Err("文件过大（>1MB），不支持预览".to_string());
    }
    fs::read_to_string(&canonical_full).map_err(|e| e.to_string())
}

// ─── Health Check ───────────────────────────────────────────────

#[derive(Serialize)]
struct HealthStatus {
    scholar_exe: bool,
    scholar_exe_path: String,
    python: bool,
    python_path: String,
    claude_cli: bool,
    claude_cli_path: String,
    qoder_cli: bool,
    qoder_cli_path: String,
    mcp_importable: bool,
    rules_dir: bool,
    skills_count: u32,
    output_dir: bool,
    pg_running: bool,
    neo4j_running: bool,
    overall: bool,
}

#[tauri::command]
fn health_check(work_dir: String) -> HealthStatus {
    let scholar_home = get_scholar_home();

    let (scholar_exe, scholar_exe_path) = match get_scholar_path() {
        Ok(p) => (true, p.to_string_lossy().to_string()),
        Err(_) => (false, String::new()),
    };

    // Run subprocess checks in parallel using scoped threads
    std::thread::scope(|s| {
        // Python check
        let python_handle = s.spawn(|| {
            let result = Command::new("python").arg("--version").output();
            let ok = result.map(|o| o.status.success()).unwrap_or(false);
            let path = if ok {
                #[cfg(windows)]
                {
                    Command::new("where").arg("python").output().ok()
                        .and_then(|o| String::from_utf8(o.stdout).ok())
                        .and_then(|s| s.lines().next().map(|l| l.trim().to_string()))
                        .unwrap_or_default()
                }
                #[cfg(not(windows))]
                {
                    Command::new("which").arg("python").output().ok()
                        .and_then(|o| String::from_utf8(o.stdout).ok())
                        .and_then(|s| s.lines().next().map(|l| l.trim().to_string()))
                        .unwrap_or_default()
                }
            } else {
                String::new()
            };
            (ok, path)
        });

        // Claude CLI check
        let claude_handle = s.spawn(|| detect_cli("claude-code".to_string()));

        // Qoder CLI check
        let qoder_handle = s.spawn(|| detect_cli("qoder-cli".to_string()));

        // MCP import check
        let mcp_handle = s.spawn(|| {
            Command::new("python").arg("-c").arg("import scholar_mcp").output()
                .map(|o| o.status.success())
                .unwrap_or(false)
        });

        let (python, python_path) = python_handle.join().unwrap_or((false, String::new()));
        let claude_cli_path = claude_handle.join().unwrap_or_else(|_| Err(String::new())).unwrap_or_default();
        let qoder_cli_path = qoder_handle.join().unwrap_or_else(|_| Err(String::new())).unwrap_or_default();
        let mcp_importable = mcp_handle.join().unwrap_or(false);

        let claude_cli = !claude_cli_path.is_empty();
        let qoder_cli = !qoder_cli_path.is_empty();

        // rules_dir = either .qoder/rules/ OR .claude/rules/ exists
        let rules_path = PathBuf::from(&scholar_home).join(".qoder").join("rules");
        let claude_rules_path = PathBuf::from(&scholar_home).join(".claude").join("rules");
        let rules_dir = rules_path.exists() || claude_rules_path.exists();

        // skills_count = union of .qoder/skills and .claude/skills
        let mut skills_count: u32 = 0;
        let mut seen_skills = std::collections::HashSet::new();
        for skills_dir_name in &[".qoder", ".claude"] {
            let skills_dir = PathBuf::from(&scholar_home).join(skills_dir_name).join("skills");
            if let Ok(entries) = fs::read_dir(&skills_dir) {
                for entry in entries.filter_map(|e| e.ok()) {
                    if entry.path().is_dir() && seen_skills.insert(entry.file_name().to_string_lossy().to_string()) {
                        skills_count += 1;
                    }
                }
            }
        }

        let base = if work_dir.is_empty() { scholar_home.clone() } else { work_dir };
        let output_dir = PathBuf::from(&base).join("output").exists();

        // PostgreSQL check (port 5433)
        let pg_running = std::net::TcpStream::connect("127.0.0.1:5433").is_ok();

        // Neo4j check (port 7474 HTTP)
        let neo4j_running = std::net::TcpStream::connect("127.0.0.1:7474").is_ok();

        // overall = 至少一个 CLI 可用 + 其他核心组件 (PG/Neo4j 不影响 overall)
        let any_cli = claude_cli || qoder_cli;
        let overall = scholar_exe && python && any_cli && mcp_importable && rules_dir;

        HealthStatus {
            scholar_exe, scholar_exe_path, python, python_path,
            claude_cli, claude_cli_path, qoder_cli, qoder_cli_path,
            mcp_importable, rules_dir, skills_count, output_dir,
            pg_running, neo4j_running, overall,
        }
    })
}

// ─── Workspace Validation ───────────────────────────────────────

#[derive(Serialize)]
struct WorkspaceInfo {
    valid: bool,
    has_output: bool,
    conversation_count: u32,
    message: String,
}

#[tauri::command]
fn validate_workspace(path: String) -> Result<WorkspaceInfo, String> {
    let p = PathBuf::from(&path);
    if !p.exists() {
        return Ok(WorkspaceInfo {
            valid: false, has_output: false, conversation_count: 0,
            message: "路径不存在".to_string(),
        });
    }
    if !p.is_dir() {
        return Ok(WorkspaceInfo {
            valid: false, has_output: false, conversation_count: 0,
            message: "路径不是目录".to_string(),
        });
    }
    let has_output = p.join("output").exists();
    let conv_dir = p.join(".scholar-studio").join("conversations");
    let conversation_count = if conv_dir.exists() {
        fs::read_dir(&conv_dir).map(|entries| {
            entries.filter_map(|e| e.ok())
                .filter(|e| e.file_name().to_string_lossy().ends_with(".json"))
                .count() as u32
        }).unwrap_or(0)
    } else {
        0
    };

    let message = if has_output {
        format!("有效工作区（{} 篇对话）", conversation_count)
    } else {
        "有效目录，无 output/ 子目录".to_string()
    };

    Ok(WorkspaceInfo { valid: true, has_output, conversation_count, message })
}

// ─── Skills Listing ─────────────────────────────────────────────

#[derive(Serialize)]
struct SkillInfo {
    name: String,
    display_name: String,
    description: String,
    is_workflow: bool,
}

#[tauri::command]
fn list_skills() -> Result<Vec<SkillInfo>, String> {
    let scholar_home = get_scholar_home();
    let skills_dir = PathBuf::from(&scholar_home).join(".qoder").join("skills");

    if !skills_dir.exists() {
        return Ok(vec![]);
    }

    let workflow_skills = [
        "research-survey", "paper-deep-dive", "writing-pipeline",
        "reproduce-paper", "idea-to-paper", "kb-management", "adaptive-research",
    ];

    let mut skills = Vec::new();
    let entries = fs::read_dir(&skills_dir).map_err(|e| e.to_string())?;

    for entry in entries.filter_map(|e| e.ok()) {
        if !entry.path().is_dir() { continue; }
        let name = entry.file_name().to_string_lossy().to_string();
        let is_workflow = workflow_skills.contains(&name.as_str());

        let skill_md = entry.path().join("SKILL.md");
        let (display_name, description) = if let Ok(content) = fs::read_to_string(&skill_md) {
            let mut dn = name.replace('-', " ");
            let mut desc = String::new();
            for line in content.lines().take(10) {
                let trimmed = line.trim();
                if trimmed.starts_with("# ") {
                    dn = trimmed[2..].to_string();
                } else if !trimmed.is_empty()
                    && !trimmed.starts_with('#')
                    && !trimmed.starts_with("---")
                    && !trimmed.starts_with("*")
                    && desc.is_empty()
                {
                    desc = trimmed.chars().take(80).collect();
                }
            }
            (dn, desc)
        } else {
            (name.replace('-', " "), String::new())
        };

        skills.push(SkillInfo { name, display_name, description, is_workflow });
    }

    skills.sort_by(|a, b| b.is_workflow.cmp(&a.is_workflow).then(a.name.cmp(&b.name)));
    Ok(skills)
}

// ─── Dotfiles Distribution ─────────────────────────────────────────

#[derive(Serialize)]
struct DotfilesStatus {
    has_claude: bool,
    has_qoder: bool,
    claude_md_exists: bool,
    mcp_json_exists: bool,
    rules_count: u32,
    skills_count: u32,
    commands_count: u32,
    hooks_count: u32,
    total_files: u32,
    qoder_total: u32,
    last_distributed: String,
}

#[derive(Serialize)]
struct DistributionResult {
    success: bool,
    claude_files_copied: u32,
    qoder_files_copied: u32,
    mcp_json_customized: bool,
    claude_md_generated: bool,
    message: String,
}

/// Recursively count files in a directory
fn count_files_in_dir(dir: &PathBuf) -> u32 {
    if !dir.exists() { return 0; }
    let mut count = 0u32;
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.filter_map(|e| e.ok()) {
            let p = entry.path();
            if p.is_file() {
                count += 1;
            } else if p.is_dir() {
                count += count_files_in_dir(&p);
            }
        }
    }
    count
}

/// Recursively copy a directory tree
fn copy_dir_recursive(src: &PathBuf, dst: &PathBuf) -> Result<u32, String> {
    if !src.exists() {
        return Err(format!("源目录不存在: {:?}", src));
    }
    fs::create_dir_all(dst).map_err(|e| format!("创建目录失败 {:?}: {}", dst, e))?;
    let mut count = 0u32;
    let entries = fs::read_dir(src).map_err(|e| e.to_string())?;
    for entry in entries.filter_map(|e| e.ok()) {
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if src_path.is_dir() {
            count += copy_dir_recursive(&src_path, &dst_path)?;
        } else {
            fs::copy(&src_path, &dst_path).map_err(|e| format!("复制失败 {:?}: {}", src_path, e))?;
            count += 1;
        }
    }
    Ok(count)
}

#[tauri::command]
fn check_dotfiles_status(work_dir: String) -> DotfilesStatus {
    let work = PathBuf::from(&work_dir);
    let claude_dir = work.join(".claude");
    let qoder_dir = work.join(".qoder");

    let rules_count = count_files_in_dir(&claude_dir.join("rules"));
    let skills_count = count_files_in_dir(&claude_dir.join("skills"));
    let commands_count = count_files_in_dir(&claude_dir.join("commands"));
    let hooks_count = count_files_in_dir(&claude_dir.join("hooks"));
    let total = rules_count + skills_count + commands_count + hooks_count
        + (if claude_dir.join("CLAUDE.md").exists() { 1 } else { 0 })
        + (if claude_dir.join("mcp.json").exists() { 1 } else { 0 })
        + (if claude_dir.join("settings.json").exists() { 1 } else { 0 });

    // Also count .qoder/ files for symmetry
    let qoder_total = count_files_in_dir(&qoder_dir);

    let marker_path = work.join(".scholar-studio").join(".dotfiles-distributed");
    let last_distributed = fs::read_to_string(&marker_path)
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "never".to_string());

    DotfilesStatus {
        has_claude: claude_dir.exists(),
        has_qoder: qoder_dir.exists(),
        claude_md_exists: claude_dir.join("CLAUDE.md").exists(),
        mcp_json_exists: claude_dir.join("mcp.json").exists(),
        rules_count, skills_count, commands_count, hooks_count,
        total_files: total, qoder_total,
        last_distributed,
    }
}

/// Back up a file to <path>.bak if it exists, before overwriting.
/// Non-existence is silently OK (first distribution).
fn backup_if_exists(path: &std::path::Path) -> Result<(), String> {
    if path.exists() {
        let bak = path.with_extension("bak");
        fs::copy(path, &bak).map_err(|e| format!("备份失败 {:?}: {}", path, e))?;
    }
    Ok(())
}

#[tauri::command]
fn distribute_dotfiles(work_dir: String) -> Result<DistributionResult, String> {
    if work_dir.is_empty() {
        return Err("工作目录不能为空".to_string());
    }
    let work = PathBuf::from(&work_dir);
    if !work.exists() || !work.is_dir() {
        return Err(format!("工作目录无效: {}", work_dir));
    }

    let scholar_home = get_scholar_home();
    let qoder_src = PathBuf::from(&scholar_home).join(".qoder");
    let claude_src = PathBuf::from(&scholar_home).join(".claude");

    if !qoder_src.exists() || !claude_src.exists() {
        return Err(format!("项目根目录缺少 .qoder/ 或 .claude/: {}", scholar_home));
    }

    let mut claude_files = 0u32;
    let mut qoder_files = 0u32;

    // 1. Copy .qoder/ structure
    let qoder_dst = work.join(".qoder");
    for subdir in &["rules", "skills", "commands", "hooks"] {
        let src = qoder_src.join(subdir);
        let dst = qoder_dst.join(subdir);
        if src.exists() {
            qoder_files += copy_dir_recursive(&src, &dst)?;
        }
    }
    for f in &["mcp.json", "settings.json"] {
        let src = qoder_src.join(f);
        let dst = qoder_dst.join(f);
        if src.exists() {
            fs::copy(&src, &dst).map_err(|e| e.to_string())?;
            qoder_files += 1;
        }
    }

    // 2. Copy .claude/ structure
    let claude_dst = work.join(".claude");
    for subdir in &["rules", "skills", "commands", "hooks"] {
        let src = claude_src.join(subdir);
        let dst = claude_dst.join(subdir);
        if src.exists() {
            claude_files += copy_dir_recursive(&src, &dst)?;
        }
    }
    let settings_src = claude_src.join("settings.json");
    if settings_src.exists() {
        fs::copy(&settings_src, claude_dst.join("settings.json")).map_err(|e| e.to_string())?;
        claude_files += 1;
    }

    // 3. Generate work-dir-specific CLAUDE.md
    let work_basename = work_dir.split(|c: char| c == '/' || c == '\\').last().unwrap_or(&work_dir);
    let prompt = build_system_prompt(&scholar_home, &work_dir);
    let claude_md_content = format!(
        "<!-- Auto-generated by Scholar Studio for workspace: {} -->\n\n# Scholar Studio — Workspace: {}\n\n> 本文件由 Scholar Studio 自动分发，指向项目根 `{}` 的完整学术资源。\n\n---\n\n{}\n\n---\n\n## Workspace 特定信息\n\n- **当前工作目录**: `{}`\n- **项目根**: `{}`\n- **Scholar MCP**: 已配置（55 个工具，35 直调 + 12 子进程 + 8 结构化）\n- **可用 IDE**: Claude Code / Qoder CLI（双平台均识别 .claude/ 和 .qoder/）\n\n可用 skills（15）位于 `.claude/skills/`，rules（7）位于 `.claude/rules/`。\n",
        work_dir, work_basename, scholar_home, prompt, work_dir, scholar_home
    );
    // Backup existing CLAUDE.md before overwriting
    let claude_md_path = claude_dst.join("CLAUDE.md");
    backup_if_exists(&claude_md_path)?;
    fs::write(&claude_md_path, &claude_md_content).map_err(|e| e.to_string())?;
    claude_files += 1;

    // 4. Generate work-dir-specific mcp.json (cwd = work_dir, SCHOLAR_WORKSPACE = work_dir)
    // NOTE: serde_json::json! already handles backslash escaping — do NOT manually escape
    let mcp_json = serde_json::json!({
        "mcpServers": {
            "scholar": {
                "command": "python",
                "args": ["-m", "scholar_mcp"],
                "cwd": work_dir,
                "env": {
                    "SCHOLAR_HOME": scholar_home,
                    "SCHOLAR_WORKSPACE": work_dir,
                    "PYTHONPATH": scholar_home
                }
            }
        }
    });
    let mcp_json_path = claude_dst.join("mcp.json");
    backup_if_exists(&mcp_json_path)?;
    fs::write(&mcp_json_path, mcp_json.to_string()).map_err(|e| e.to_string())?;
    claude_files += 1;

    // 5. Also write CLAUDE.md to work_dir root (Claude Code auto-discovers)
    let root_claude_md = work.join("CLAUDE.md");
    backup_if_exists(&root_claude_md)?;
    fs::write(&root_claude_md, &claude_md_content).map_err(|e| e.to_string())?;

    // 6. Write timestamp marker
    let marker_dir = work.join(".scholar-studio");
    fs::create_dir_all(&marker_dir).map_err(|e| e.to_string())?;
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs().to_string())
        .unwrap_or_else(|_| "unknown".to_string());
    fs::write(marker_dir.join(".dotfiles-distributed"), &ts).map_err(|e| e.to_string())?;

    Ok(DistributionResult {
        success: true,
        claude_files_copied: claude_files,
        qoder_files_copied: qoder_files,
        mcp_json_customized: true,
        claude_md_generated: true,
        message: format!(
            "成功分发 .claude/ ({} 文件) + .qoder/ ({} 文件) 到 {}",
            claude_files, qoder_files, work_dir
        ),
    })
}

// ─── Stop Generation ───────────────────────────────────────────

#[tauri::command]
fn stop_generation(
    state: State<ChildPid>,
    app: AppHandle,
    session_id: Option<String>,
) -> Result<(), String> {
    let mut pid_guard = state.0.lock().map_err(|e| e.to_string())?;

    // If session_id provided, kill only that session; otherwise kill all
    let pids_to_kill: Vec<u32> = if let Some(sid) = session_id {
        pid_guard.remove(&sid).into_iter().collect()
    } else {
        pid_guard.drain().map(|(_, v)| v).collect()
    };
    drop(pid_guard); // Release lock before spawning taskkill

    for pid_val in pids_to_kill {
        #[cfg(windows)]
        {
            let output = Command::new("taskkill")
                .args(["/PID", &pid_val.to_string(), "/F", "/T"])
                .output()
                .map_err(|e| format!("taskkill failed: {}", e))?;
            if !output.status.success() {
                eprintln!("taskkill for PID {} failed: {}", pid_val,
                    String::from_utf8_lossy(&output.stderr));
            }
        }
        #[cfg(not(windows))]
        {
            let output = Command::new("kill")
                .arg("-9")
                .arg(pid_val.to_string())
                .output()
                .map_err(|e| format!("kill failed: {}", e))?;
            if !output.status.success() {
                eprintln!("kill for PID {} failed: {}", pid_val,
                    String::from_utf8_lossy(&output.stderr));
            }
        }
    }
    let _ = app.emit("chat-done", ());
    Ok(())
}

// ─── Docker Services ────────────────────────────────────────────

#[derive(Serialize)]
struct DockerService {
    name: String,
    running: bool,
    status: String,
}

#[tauri::command]
fn docker_status(_work_dir: String) -> Vec<DockerService> {
    // Check if Docker daemon is running
    let docker_ok = Command::new("docker").arg("info").output()
        .map(|o| o.status.success()).unwrap_or(false);

    if !docker_ok {
        return vec![
            DockerService { name: "Neo4j".into(), running: false, status: "Docker 不可用".into() },
            DockerService { name: "PostgreSQL".into(), running: false, status: "Docker 不可用".into() },
        ];
    }

    // Always check running containers by name pattern, even without compose file
    let services = [("scholar-neo4j", "Neo4j"), ("scholar-postgres", "PostgreSQL")];
    services.iter().map(|(container_name, display_name)| {
        let output = Command::new("docker")
            .args(["ps", "-q", "-f", &format!("name={}", container_name)])
            .output();
        let running = output.map(|o| !o.stdout.is_empty()).unwrap_or(false);
        DockerService {
            name: display_name.to_string(),
            running,
            status: if running { "running".into() } else { "stopped".into() },
        }
    }).collect()
}

#[tauri::command]
fn docker_toggle(service: String, work_dir: String, start: bool) -> Result<String, String> {
    let base = if work_dir.is_empty() { get_scholar_home() } else { work_dir };
    let compose_file = PathBuf::from(&base).join("infra").join("docker-compose.yml");

    let action = if start { "up" } else { "stop" };
    let output = Command::new("docker")
        .args(["compose", "-f", compose_file.to_str().unwrap(), action, "-d", &service])
        .output()
        .map_err(|e| e.to_string())?;

    if output.status.success() {
        Ok(format!("{} {}", service, if start { "started" } else { "stopped" }))
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

// ─── Scholar MCP Bridge ─────────────────────────────────────────

#[tauri::command]
fn call_scholar_mcp(tool_name: String, args: String) -> Result<String, String> {
    // Security: validate tool_name to prevent Python code injection
    if tool_name.is_empty() || !tool_name.chars().all(|c| c.is_alphanumeric() || c == '_') {
        return Err(format!("Invalid tool name: '{}'", tool_name));
    }

    let scholar_home = get_scholar_home();

    // Use unique nonce to prevent temp file race condition between concurrent calls
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let tmp = std::env::temp_dir().join(format!("scholar_mcp_{}_{nonce}.json", std::process::id()));
    fs::write(&tmp, &args).map_err(|e| e.to_string())?;

    // Security: pass temp file path via sys.argv instead of string interpolation
    let script = format!(
        "import json,sys; from scholar_mcp.server import {tool}; args=json.load(open(sys.argv[1],encoding='utf-8')); print({tool}(**args))",
        tool = tool_name,
    );

    let output = Command::new("python")
        .arg("-c")
        .arg(&script)
        .arg(&tmp)
        .current_dir(&scholar_home)
        .env("PYTHONPATH", &scholar_home)
        .env("SCHOLAR_HOME", &scholar_home)
        .output()
        .map_err(|e| format!("Failed to spawn python: {}", e))?;

    let _ = fs::remove_file(&tmp);

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(format!("MCP tool '{}' failed: {}", tool_name, stderr.lines().last().unwrap_or("unknown error")))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(ChildPid(Mutex::new(HashMap::new())))
                .manage(PromptCache(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            get_stats,
            search_papers,
            get_paper_info,
            list_workspace_files,
            list_conversations,
            chat_send,
            detect_cli,
            save_conversation,
            load_conversation,
            read_file,
            health_check,
            validate_workspace,
            list_skills,
            stop_generation,
            docker_status,
            docker_toggle,
            check_dotfiles_status,
            distribute_dotfiles,
            call_scholar_mcp,
        ])
        .setup(|app| {
            // Auto-start Docker infra (PostgreSQL + Neo4j) in background
            let scholar_home_setup = get_scholar_home();
            std::thread::spawn(move || {
                let compose_file = PathBuf::from(&scholar_home_setup).join("infra").join("docker-compose.yml");
                if !compose_file.exists() {
                    return;
                }
                // Check if services are already running
                let pg_up = std::net::TcpStream::connect("127.0.0.1:5433").is_ok();
                let neo4j_up = std::net::TcpStream::connect("127.0.0.1:7474").is_ok();
                if pg_up && neo4j_up {
                    return;
                }
                // Try to start via docker compose
                let _ = Command::new("docker")
                    .args(["compose", "-f", compose_file.to_str().unwrap_or(""), "up", "-d"])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .output();
            });

            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
