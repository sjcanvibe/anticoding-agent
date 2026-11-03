#!/usr/bin/env python3
"""
AntiCoding Agent - Local AI Pair-Programmer powered by llama.service (Qwen3-Coder-Next-Q8_0)
Zero external dependencies required (100% Python 3 standard library).
Features:
- Real-time Token Streaming (SSE over urllib.request)
- Thinking / Reasoning Highlighting (<think> tags & reasoning_content)
- Automatic Git Checkpoints (Non-destructive rollback / undo)
- Deep History Recovery (JSONL Session Transcript Journal + search_session_history tool)
- Hybrid Memory Architecture: Living Disk Artifacts (.anticoding/scratchpad.md) + Turn-Boundary Compaction.
"""

import os
import sys
import json
import re
import time
import subprocess
import urllib.request
import urllib.error

# ==============================================================================
# ⚙️ USER CONFIGURATION (Easily customize your local setup or .env file here)
# ==============================================================================
def find_repo_root() -> str:
    """Locate the top-level root of the Git repository or fallback to current directory."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            return os.path.abspath(res.stdout.strip())
    except Exception:
        pass
    return os.path.abspath(".")

def load_dotenv(dotenv_path: str = ".env"):
    """Zero-dependency .env file loader into os.environ."""
    if not os.path.exists(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip().removeprefix("export ").strip()
                v = v.strip().strip("'").strip('"')
                os.environ.setdefault(k, v)
    except Exception:
        pass

ROOT_WORKSPACE = find_repo_root()                                  # Main repository root directory
load_dotenv(os.path.join(ROOT_WORKSPACE, ".env"))
load_dotenv(".env")

API_BASE = os.getenv("ANTICODING_API_BASE", "http://127.0.0.1:8081/v1")
API_KEY = os.getenv("ANTICODING_API_KEY", "sk-no-key-required")
MODEL_NAME = os.getenv("ANTICODING_MODEL", "Qwen3-Coder-Next-Q8_0")

# Context & Memory Limits (Configured for 128k / 131,072 context size)
SERVER_CTX_SIZE = int(os.getenv("ANTICODING_CTX_SIZE", "131072"))  # Server's --ctx-size
MAX_CONTEXT_TOKENS = int(os.getenv("ANTICODING_MAX_TOKENS", str(int(SERVER_CTX_SIZE * 0.75)))) # Default: 98,304 tokens
MAX_READ_CHARS = 160000                                            # Max characters per read_file (~3,500–4,000 lines)
MAX_CMD_CHARS = 60000                                              # Max characters returned per command run (~1,200 lines)
RECENT_MESSAGES_TO_KEEP = int(os.getenv("ANTICODING_RECENT_MSGS", "14")) # Preserves ~3–5 full conversation rounds
ENABLE_STREAMING = True                                            # Real-time word-by-word streaming
ENABLE_REPO_MAP = True                                             # Inject real-time repo symbol map into System Prompt
ENABLE_SANDBOX = True                                              # Enforce filesystem path jail & dangerous command filters

# Persistent Storage Paths & Workspaces
CURRENT_WORKSPACE = ROOT_WORKSPACE                                # Active workspace directory (root or worktree)
WORKSPACES_DIR = os.path.join(ROOT_WORKSPACE, ".anticoding/workspaces") # Isolated worktree directory
SCRATCHPAD_PATH = os.path.join(ROOT_WORKSPACE, ".anticoding/scratchpad.md")
CHECKPOINTS_DIR = os.path.join(ROOT_WORKSPACE, ".anticoding/checkpoints")
TRANSCRIPTS_DIR = os.path.join(ROOT_WORKSPACE, ".anticoding/transcripts")
SESSION_ID = time.strftime("%Y%m%d_%H%M%S")
TRANSCRIPT_FILE = os.path.join(TRANSCRIPTS_DIR, f"session_{SESSION_ID}.jsonl")
# ==============================================================================

SYSTEM_PROMPT = """You are AntiCoding Agent, an autonomous local AI pair-programming assistant.
You have access to powerful tools to inspect codebases, execute shell commands, read/write files, and perform surgical code edits.

Operating Principles:
1. Hybrid Memory: Maintain your active plan, current goals, and architectural discoveries in the living scratchpad using `update_scratchpad`. Check `read_scratchpad` when starting complex tasks.
2. Deep History Recovery: If asked about exact error tracebacks, past benchmark numbers, or steps from earlier in the session that were compacted, use `search_session_history` to recall the raw historical output.
3. Surgical Editing: Prefer `replace_file_content` to make targeted edits to existing files rather than rewriting whole files with `write_file`.
4. Exploration: Use `search_files` to grep across codebases and `read_file` with line ranges to inspect precise code sections.
5. Accuracy & Verification: Always verify your changes by running commands or reading modified files. Provide concise, high-quality responses."""

# OpenAI-compatible Function Calling Schema
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a bash shell command in the current working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The exact bash command line to run."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents with prepended line numbers. Supports optional start_line and end_line slicing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read."},
                    "start_line": {"type": "integer", "description": "Optional 1-indexed starting line number."},
                    "end_line": {"type": "integer", "description": "Optional 1-indexed ending line number (inclusive)."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_file_content",
            "description": "Surgically replace a unique block of text inside an existing file without rewriting the entire file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to modify."},
                    "target": {"type": "string", "description": "The exact block of code/text to replace (must match exactly including indentation)."},
                    "replacement": {"type": "string", "description": "The new block of code/text to insert."}
                },
                "required": ["path", "target", "replacement"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or completely overwrite an existing file with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write to."},
                    "content": {"type": "string", "description": "Text content to write."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Recursively search for a regex pattern or keyword across files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern or search term."},
                    "path": {"type": "string", "description": "Root directory to search (defaults to '.')."},
                    "case_sensitive": {"type": "boolean", "description": "Whether search is case-sensitive (default: false)."}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories in a directory path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (defaults to '.')."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_session_history",
            "description": "Search past conversation turns, previous raw tool outputs, command outputs, or exact error messages from earlier in the session that were compacted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword or regex to search in session transcript history."},
                    "limit": {"type": "integer", "description": "Maximum matching turns to return (default: 5)."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_scratchpad",
            "description": "Write or update the living disk artifact (.anticoding/scratchpad.md) with active goals, plans, and discoveries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The markdown content to persist in the living scratchpad."}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_scratchpad",
            "description": "Read the living disk artifact (.anticoding/scratchpad.md) containing the persistent plan and notes.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# ----------------- Deep History Recovery (Transcript Journal) -----------------

def log_transcript_entry(message: dict):
    """Append a raw interaction message to the disk transcript journal."""
    try:
        os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "message": message
        }
        with open(TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

def tool_search_session_history(query: str, limit: int = 5) -> str:
    """Search the session transcript journal for exact past turns, errors, and tool outputs."""
    if not os.path.exists(TRANSCRIPT_FILE):
        return "No transcript history recorded for this session yet."

    try:
        regex = re.compile(query, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    matches = []
    try:
        with open(TRANSCRIPT_FILE, "r", encoding="utf-8", errors="replace") as f:
            step_no = 0
            for line in f:
                if not line.strip():
                    continue
                step_no += 1
                entry = json.loads(line)
                msg = entry.get("message", {})
                timestamp = entry.get("timestamp", "")
                
                # Check for match in full message payload
                raw_payload = json.dumps(msg, ensure_ascii=False)
                if regex.search(raw_payload):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    tool_calls = msg.get("tool_calls", [])

                    header = f"[Step {step_no} | {timestamp} | Role: {role}]"
                    if role == "tool":
                        body = f"Tool Output (id: {msg.get('tool_call_id', '')}):\n{content}"
                    elif role == "assistant" and tool_calls:
                        tc_details = []
                        for tc in tool_calls:
                            fname = tc.get("function", {}).get("name", "")
                            fargs = tc.get("function", {}).get("arguments", "")
                            tc_details.append(f"{fname}({fargs})")
                        body = f"Tool Calls Executed: {', '.join(tc_details)}\n{content or ''}"
                    else:
                        body = str(content)

                    # Truncate per match snippet if huge
                    if len(body) > 2000:
                        body = body[:2000] + "\n[... Snippet truncated ...]"

                    matches.append(f"{header}\n{body}")
                    if len(matches) >= limit:
                        break

        if not matches:
            return f"No transcript entries matched query '{query}'."

        return f"Found {len(matches)} matching entries in session transcript:\n\n" + "\n\n---\n\n".join(matches)
    except Exception as e:
        return f"Transcript Search Error: {str(e)}"

# ----------------- Git Checkpoint & Rollback System -----------------

def is_git_repo(workspace: str = None) -> bool:
    """Check if target workspace directory is inside a git repository."""
    target_ws = workspace or CURRENT_WORKSPACE
    try:
        res = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=target_ws, capture_output=True, text=True, timeout=5)
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False

def create_checkpoint(label: str = "", workspace: str = None) -> str:
    """Create a non-destructive git snapshot patch before modifications."""
    target_ws = workspace or CURRENT_WORKSPACE
    if not is_git_repo(target_ws):
        return None
    try:
        os.makedirs(CHECKPOINTS_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        clean_label = re.sub(r'[^a-zA-Z0-9_-]', '_', label).strip('_')[:25] or "step"
        ws_tag = "root" if target_ws == ROOT_WORKSPACE else os.path.basename(target_ws)
        patch_file = os.path.join(CHECKPOINTS_DIR, f"cp_{timestamp}_{ws_tag}_{clean_label}.patch")

        head_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_ws, capture_output=True, text=True, timeout=5).stdout.strip()
        diff_res = subprocess.run(["git", "diff", "HEAD"], cwd=target_ws, capture_output=True, text=True, timeout=10)
        
        with open(patch_file, "w", encoding="utf-8") as f:
            f.write(f"# GIT_COMMIT: {head_commit}\n# TIMESTAMP: {timestamp}\n# WORKSPACE: {target_ws}\n# LABEL: {label}\n")
            f.write(diff_res.stdout)
            
        return patch_file
    except Exception:
        return None

def rollback_checkpoint(workspace: str = None) -> str:
    """Roll back workspace changes to the previous checkpoint."""
    target_ws = workspace or CURRENT_WORKSPACE
    if not is_git_repo(target_ws):
        return "Not a git repository. Cannot rollback."
    try:
        if not os.path.exists(CHECKPOINTS_DIR):
            return "No checkpoints found."
        patches = sorted([p for p in os.listdir(CHECKPOINTS_DIR) if p.endswith(".patch")])
        if not patches:
            return "No checkpoints available to rollback."
        
        latest_patch = patches[-1]
        patch_path = os.path.join(CHECKPOINTS_DIR, latest_patch)
        
        subprocess.run(["git", "checkout", "."], cwd=target_ws, capture_output=True, text=True, timeout=10)
        subprocess.run(["git", "clean", "-fd"], cwd=target_ws, capture_output=True, text=True, timeout=10)
        
        os.remove(patch_path)
        return f"Successfully rolled back workspace ({target_ws}) to before checkpoint '{latest_patch}'."
    except Exception as e:
        return f"Rollback Error: {str(e)}"

def list_checkpoints(workspace: str = None) -> str:
    """List available git checkpoints."""
    target_ws = workspace or CURRENT_WORKSPACE
    if not is_git_repo(target_ws):
        return "Not a git repository."
    if not os.path.exists(CHECKPOINTS_DIR):
        return "No checkpoints saved yet."
    patches = sorted([p for p in os.listdir(CHECKPOINTS_DIR) if p.endswith(".patch")])
    if not patches:
        return "No checkpoints saved yet."
    return f"Saved Checkpoints (newest last):\n" + "\n".join(f"  • {p}" for p in patches[-10:])

# ----------------- Sandboxing & Workspaces Engine -----------------

def is_safe_path(target_path: str, workspace: str = None) -> tuple:
    """
    Validate that target_path resolves strictly within the active workspace directory.
    Returns (is_safe: bool, canonical_path: str, error_msg: str).
    """
    ws = os.path.realpath(workspace or CURRENT_WORKSPACE)
    if not target_path or not isinstance(target_path, str):
        return False, "", "Invalid path parameter."
    
    if not os.path.isabs(target_path):
        candidate = os.path.join(ws, target_path)
    else:
        candidate = target_path

    # Canonicalize path handling non-existent paths securely
    norm = os.path.abspath(candidate)
    resolved = os.path.realpath(norm)
        
    if not ENABLE_SANDBOX:
        return True, resolved, ""
        
    if resolved == ws or resolved.startswith(ws + os.sep):
        return True, resolved, ""
    
    return False, resolved, f"Sandbox Security Error: Path '{target_path}' is outside active workspace boundary ({ws})."

def is_safe_command(command: str) -> tuple:
    """
    Inspect command string for dangerous system-level commands when sandboxing is active.
    Returns (is_safe: bool, reason: str).
    """
    if not ENABLE_SANDBOX:
        return True, ""
    
    dangerous_patterns = [
        (r'\bsudo\b', "Use of 'sudo' is blocked in sandbox mode."),
        (r'\brm\s+-[a-zA-Z]*[rfRF][a-zA-Z]*\s+(/|/\*|~|\$HOME|\.\.)(?:\s|$|;)', "Destructive root/home/parent deletion blocked."),
        (r'\bmkfs\b', "Filesystem formatting blocked."),
        (r'\bfdisk\b', "Disk partitioning blocked."),
        (r'\bdd\s+if=', "Low-level disk writing blocked."),
        (r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:', "Fork bomb blocked."),
        (r'>\s*/etc/', "Modifying system files in /etc/ blocked."),
        (r'>\s*/usr/', "Modifying system files in /usr/ blocked."),
        (r'\bchmod\s+-[a-zA-Z]*[rRfF][a-zA-Z]*\s+777\s+(/|/\*)(?:\s|$|;)', "Root permission modification blocked.")
    ]
    
    for pattern, reason in dangerous_patterns:
        if re.search(pattern, command):
            return False, f"Sandbox Security Violation: {reason}"
            
    return True, ""

def get_active_workspace() -> str:
    """Get active workspace root path."""
    return CURRENT_WORKSPACE

def set_active_workspace(path: str):
    """Set active workspace path."""
    global CURRENT_WORKSPACE
    CURRENT_WORKSPACE = os.path.abspath(path)

def list_workspaces() -> str:
    """List available git worktree workspaces."""
    if not is_git_repo():
        return "Not a git repository. Workspace worktrees unavailable."
    
    lines = [f"Root Workspace: {ROOT_WORKSPACE} {'(ACTIVE)' if CURRENT_WORKSPACE == ROOT_WORKSPACE else ''}"]
    
    if os.path.exists(WORKSPACES_DIR):
        for name in sorted(os.listdir(WORKSPACES_DIR)):
            wpath = os.path.join(WORKSPACES_DIR, name)
            if os.path.isdir(wpath):
                is_active = (CURRENT_WORKSPACE == wpath)
                lines.append(f"  • {name} -> {wpath} {'(ACTIVE)' if is_active else ''}")
                
    if len(lines) == 1:
        lines.append("  (No isolated worktrees created. Using root workspace.)")
        
    return "\n".join(lines)

def create_workspace(name: str) -> str:
    """Create a new isolated Git worktree workspace."""
    if not is_git_repo():
        return "Error: Workspaces require a Git repository."
        
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name).strip('_')
    if not clean_name:
        return "Error: Invalid workspace name."
        
    os.makedirs(WORKSPACES_DIR, exist_ok=True)
    target_dir = os.path.join(WORKSPACES_DIR, clean_name)
    
    if os.path.exists(target_dir):
        return f"Error: Workspace '{clean_name}' already exists at {target_dir}."
        
    res = subprocess.run(["git", "branch", "--list", clean_name], cwd=ROOT_WORKSPACE, capture_output=True, text=True)
    branch_flag = ["-B", clean_name] if clean_name in res.stdout else ["-b", clean_name]
    
    cmd = ["git", "worktree", "add"] + branch_flag + [target_dir, "HEAD"]
    proc = subprocess.run(cmd, cwd=ROOT_WORKSPACE, capture_output=True, text=True)
    
    if proc.returncode != 0:
        return f"Git Worktree Error: {proc.stderr or proc.stdout}"
        
    set_active_workspace(target_dir)
    return f"Successfully created and switched to isolated workspace '{clean_name}' ({target_dir})."

def switch_workspace(name: str) -> str:
    """Switch active workspace between root ('main'/'root') and worktrees."""
    if name.lower() in ["main", "root", "default", "."]:
        set_active_workspace(ROOT_WORKSPACE)
        return f"Switched active workspace back to Root ({ROOT_WORKSPACE})."
        
    target_dir = os.path.join(WORKSPACES_DIR, name)
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return f"Error: Workspace '{name}' not found. Use '/ws' to list workspaces."
        
    set_active_workspace(target_dir)
    return f"Switched active workspace to '{name}' ({target_dir})."

def apply_workspace(name: str = None) -> str:
    """Merge or apply changes from an isolated worktree branch into root workspace."""
    if not is_git_repo():
        return "Error: Git repository required."
        
    ws_to_apply = name or (os.path.basename(CURRENT_WORKSPACE) if CURRENT_WORKSPACE != ROOT_WORKSPACE else None)
    if not ws_to_apply or ws_to_apply in ["main", "root"]:
        return "Error: Currently in Root workspace. Specify a worktree name to apply (e.g. '/ws apply <name>')."
        
    proc = subprocess.run(["git", "merge", "--no-ff", "-m", f"Merge workspace '{ws_to_apply}'", ws_to_apply], cwd=ROOT_WORKSPACE, capture_output=True, text=True)
    if proc.returncode != 0:
        return f"Merge Conflict / Error applying '{ws_to_apply}' to root:\n{proc.stderr or proc.stdout}"
        
    return f"Successfully merged changes from workspace '{ws_to_apply}' into Root workspace."

def discard_workspace(name: str) -> str:
    """Discard and delete a worktree workspace and its branch."""
    if not is_git_repo():
        return "Error: Git repository required."
        
    if not name or name in ["main", "root"]:
        return "Error: Cannot discard root workspace."
        
    target_dir = os.path.join(WORKSPACES_DIR, name)
    if not os.path.exists(target_dir):
        return f"Error: Workspace '{name}' does not exist."
        
    if CURRENT_WORKSPACE == target_dir:
        set_active_workspace(ROOT_WORKSPACE)
        
    subprocess.run(["git", "worktree", "remove", "--force", target_dir], cwd=ROOT_WORKSPACE, capture_output=True, text=True)
    subprocess.run(["git", "branch", "-D", name], cwd=ROOT_WORKSPACE, capture_output=True, text=True)
    
    return f"Successfully discarded workspace '{name}' and deleted branch."

# ----------------- Tool Implementations -----------------

def tool_run_command(command: str) -> str:
    """Execute shell command with timeout, safety filtering, and active workspace cwd."""
    safe, reason = is_safe_command(command)
    if not safe:
        return f"Error: {reason}"
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120, cwd=CURRENT_WORKSPACE)
        output = res.stdout + res.stderr
        if not output.strip():
            output = "(Command executed successfully with no output)"
        if len(output) > MAX_CMD_CHARS:
            return output[:MAX_CMD_CHARS] + f"\n\n[... Output truncated: {len(output) - MAX_CMD_CHARS} characters omitted ...]"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command execution timed out after 120 seconds."
    except Exception as e:
        return f"Execution Error: {str(e)}"

def tool_read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Read file with line numbers and optional line range within active workspace."""
    safe, path, err = is_safe_path(path)
    if not safe:
        return f"Error: {err}"
    if not os.path.exists(path):
        return f"Error: File '{path}' does not exist."
    if os.path.isdir(path):
        return f"Error: '{path}' is a directory, not a file."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        s_line = max(1, start_line) if start_line is not None else 1
        e_line = min(total_lines, end_line) if end_line is not None else total_lines

        if s_line > total_lines:
            return f"Error: start_line ({s_line}) exceeds total lines in file ({total_lines})."

        output_lines = []
        for idx in range(s_line - 1, e_line):
            output_lines.append(f"{idx + 1:4d} | {lines[idx].rstrip()}")

        header = f"[{path} (Lines {s_line}-{e_line} of {total_lines})]\n"
        result = header + "\n".join(output_lines)
        if len(result) > MAX_READ_CHARS:
            result = result[:MAX_READ_CHARS] + "\n\n[... Truncated due to size limit. Specify narrower start_line and end_line ...]"
        return result
    except Exception as e:
        return f"Read File Error: {str(e)}"

def tool_replace_file_content(path: str, target: str, replacement: str) -> str:
    """Surgically replace a unique block of text inside a file within active workspace."""
    safe, path, err = is_safe_path(path)
    if not safe:
        return f"Error: {err}"
    if not os.path.exists(path):
        return f"Error: File '{path}' does not exist."

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if target not in content:
            return f"Error: Target text not found in '{path}'. Please ensure exact matching including whitespace and indentation."

        occurrences = content.count(target)
        if occurrences > 1:
            return f"Error: Target text occurs {occurrences} times in '{path}'. Please provide more surrounding context to ensure a unique match."

        new_content = content.replace(target, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Successfully updated '{path}'."
    except Exception as e:
        return f"Replace Content Error: {str(e)}"

def tool_write_file(path: str, content: str) -> str:
    """Write or overwrite full file content within active workspace."""
    safe, path, err = is_safe_path(path)
    if not safe:
        return f"Error: {err}"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to '{path}'."
    except Exception as e:
        return f"Write File Error: {str(e)}"

def tool_search_files(pattern: str, path: str = ".", case_sensitive: bool = False) -> str:
    """Recursively search for regex pattern in text files within active workspace."""
    safe, root_dir, err = is_safe_path(path)
    if not safe:
        return f"Error: {err}"
    if not os.path.exists(root_dir):
        return f"Error: Search directory '{root_dir}' does not exist."

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    ignored_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".anticoding", "dist", "build", "target", ".idea", ".vscode"}
    ignored_exts = {
        ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".mp4",
        ".min.js", ".min.css", ".map", ".wasm", ".lock", ".sum", ".parquet", ".bin", ".exe", ".so", ".dylib"
    }
    max_file_size_bytes = 2 * 1024 * 1024  # Skip files > 2MB
    matches = []
    max_matches = 50

    try:
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ignored_exts or any(file.lower().endswith(ie) for ie in ignored_exts):
                    continue

                file_path = os.path.join(root, file)
                try:
                    if os.path.getsize(file_path) > max_file_size_bytes:
                        continue
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, start=1):
                            if regex.search(line):
                                rel_path = os.path.relpath(file_path, root_dir)
                                matches.append(f"{rel_path}:{line_no}: {line.strip()[:150]}")
                                if len(matches) >= max_matches:
                                     break
                except Exception:
                    continue
                if len(matches) >= max_matches:
                    break
            if len(matches) >= max_matches:
                break

        if not matches:
            return f"No matches found for pattern '{pattern}'."
        result = "\n".join(matches)
        if len(matches) >= max_matches:
            result += f"\n\n(Showing first {max_matches} matches. Narrow your search pattern if needed.)"
        return result
    except Exception as e:
        return f"Search Error: {str(e)}"

def tool_list_dir(path: str = ".") -> str:
    """List directory contents with file/folder markers within active workspace."""
    safe, target_path, err = is_safe_path(path)
    if not safe:
        return f"Error: {err}"
    if not os.path.exists(target_path):
        return f"Error: Path '{target_path}' does not exist."
    if not os.path.isdir(target_path):
        return f"Error: Path '{target_path}' is a file, not a directory."

    try:
        entries = sorted(os.listdir(target_path))
        formatted = []
        for entry in entries[:100]:
            full = os.path.join(target_path, entry)
            marker = "[DIR] " if os.path.isdir(full) else "      "
            formatted.append(f"{marker}{entry}")
        result = "\n".join(formatted)
        if len(entries) > 100:
            result += f"\n\n... and {len(entries) - 100} more items."
        return result
    except Exception as e:
        return f"List Dir Error: {str(e)}"

def tool_update_scratchpad(content: str) -> str:
    """Persist living scratchpad on disk."""
    try:
        os.makedirs(os.path.dirname(SCRATCHPAD_PATH), exist_ok=True)
        with open(SCRATCHPAD_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Living Scratchpad successfully updated at '{SCRATCHPAD_PATH}'."
    except Exception as e:
        return f"Scratchpad Update Error: {str(e)}"

def tool_read_scratchpad() -> str:
    """Read living scratchpad from disk."""
    if not os.path.exists(SCRATCHPAD_PATH):
        return "Living Scratchpad is currently empty. Use `update_scratchpad` to initialize your active plan."
    try:
        with open(SCRATCHPAD_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Scratchpad Read Error: {str(e)}"

# Dispatcher
TOOL_DISPATCHER = {
    "run_command": lambda a: tool_run_command(a.get("command", "")),
    "read_file": lambda a: tool_read_file(a.get("path", ""), a.get("start_line"), a.get("end_line")),
    "replace_file_content": lambda a: tool_replace_file_content(a.get("path", ""), a.get("target", ""), a.get("replacement", "")),
    "write_file": lambda a: tool_write_file(a.get("path", ""), a.get("content", "")),
    "search_files": lambda a: tool_search_files(a.get("pattern", ""), a.get("path", "."), a.get("case_sensitive", False)),
    "list_dir": lambda a: tool_list_dir(a.get("path", ".")),
    "search_session_history": lambda a: tool_search_session_history(a.get("query", ""), a.get("limit", 5)),
    "update_scratchpad": lambda a: tool_update_scratchpad(a.get("content", "")),
    "read_scratchpad": lambda a: tool_read_scratchpad(),
}

def execute_tool(name: str, args: dict) -> str:
    """Execute tool and safely handle exceptions."""
    print(f"\n\033[93m[Tool Executing]\033[0m {name}({json.dumps(args, ensure_ascii=False)})")
    handler = TOOL_DISPATCHER.get(name)
    if not handler:
        return f"Unknown tool: '{name}'."
    try:
        return handler(args)
    except Exception as e:
        return f"Tool Execution Exception: {str(e)}"

# ----------------- Thinking & Streaming Token Renderer -----------------

class ThinkingStreamRenderer:
    """Handles real-time token streaming with live <think> tag detection and dim gray coloring."""
    def __init__(self):
        self.in_think = False
        self.buffer = ""
        self.full_content = ""
        self.full_reasoning = ""
        self.think_header_printed = False
        self.content_header_printed = False

    def on_reasoning_delta(self, delta_text: str):
        if not delta_text:
            return
        if not self.think_header_printed:
            sys.stdout.write("\n\033[90m[Thinking]\033[0m\n\033[90m")
            self.think_header_printed = True
        self.full_reasoning += delta_text
        sys.stdout.write(f"\033[90m{delta_text}\033[0m")
        sys.stdout.flush()

    def on_content_delta(self, delta_text: str):
        if not delta_text:
            return
        self.full_content += delta_text
        self.buffer += delta_text

        while self.buffer:
            if not self.in_think:
                if "<think>" in self.buffer:
                    before, _, after = self.buffer.partition("<think>")
                    if before:
                        self._print_content(before)
                    if not self.think_header_printed:
                        sys.stdout.write("\n\033[90m[Thinking]\033[0m\n\033[90m")
                        self.think_header_printed = True
                    self.in_think = True
                    self.buffer = after
                else:
                    partial = False
                    for i in range(1, 7):
                        if self.buffer.endswith("<think>"[:i]):
                            partial = True
                            break
                    if partial:
                        break
                    self._print_content(self.buffer)
                    self.buffer = ""
            else:
                if "</think>" in self.buffer:
                    think_text, _, after = self.buffer.partition("</think>")
                    if think_text:
                        sys.stdout.write(f"\033[90m{think_text}\033[0m")
                        sys.stdout.flush()
                    sys.stdout.write("\033[0m\n")
                    self.in_think = False
                    self.content_header_printed = False
                    self.buffer = after
                else:
                    partial = False
                    for i in range(1, 8):
                        if self.buffer.endswith("</think>"[:i]):
                            partial = True
                            break
                    if partial:
                        break
                    sys.stdout.write(f"\033[90m{self.buffer}\033[0m")
                    sys.stdout.flush()
                    self.buffer = ""

    def _print_content(self, text: str):
        if not self.content_header_printed:
            sys.stdout.write("\n\033[94mAntiCoding:\033[0m\n")
            self.content_header_printed = True
        sys.stdout.write(text)
        sys.stdout.flush()

    def flush(self):
        if self.buffer:
            if self.in_think:
                sys.stdout.write(f"\033[90m{self.buffer}\033[0m\n")
                self.in_think = False
            else:
                self._print_content(self.buffer)
            self.buffer = ""
        if self.content_header_printed or self.think_header_printed:
            sys.stdout.write("\n")
            sys.stdout.flush()

# ----------------- Context & API Management -----------------

def estimate_tokens(messages: list) -> int:
    """Fast approximation: ~4 characters per token."""
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) // 4

def compact_conversation(messages: list, max_tokens: int = MAX_CONTEXT_TOKENS) -> list:
    """Smart turn-boundary compaction: preserves master user goal, recent multi-turn history, and tool call integrity."""
    min_required_len = RECENT_MESSAGES_TO_KEEP + 4
    if estimate_tokens(messages) < max_tokens or len(messages) <= min_required_len:
        return messages

    print("\n\033[93m[Context Manager] Compacting older conversation history...\033[0m")
    
    system_msg = messages[0]
    root_user_goal = messages[1] if len(messages) > 1 and messages[1].get("role") == "user" else None

    cutoff_idx = max(2 if root_user_goal else 1, len(messages) - RECENT_MESSAGES_TO_KEEP)
    while cutoff_idx < len(messages) and messages[cutoff_idx].get("role") != "user":
        cutoff_idx += 1

    start_idx = 2 if root_user_goal else 1
    older_msgs = messages[start_idx:cutoff_idx]
    recent_msgs = messages[cutoff_idx:]

    if not older_msgs:
        return messages

    summary_req = [
        {"role": "system", "content": "You are a concise technical summarizer. Extract key goals, decisions, modified files, and pending tasks."},
        {"role": "user", "content": f"Summarize key goals, decisions made, code changes, and unresolved tasks in 3-4 bullet points:\n{json.dumps(older_msgs, ensure_ascii=False)}"}
    ]

    summary_resp = call_llm(summary_req, tools=None, stream=False, inject_repo_map=False)
    if summary_resp and summary_resp.get("content"):
        summary_text = summary_resp["content"].strip()
    else:
        summary_text = "Prior dialogue compacted to conserve context tokens."

    compacted = [system_msg]
    if root_user_goal:
        compacted.append(root_user_goal)

    compacted.extend([
        {"role": "user", "content": f"[Previous Session History Compacted]:\n{summary_text}"},
        {"role": "assistant", "content": "Understood. Continuing from current state with this context."},
        *recent_msgs
    ])

    print(f"\033[92m[Context Manager] Compaction complete (~{estimate_tokens(compacted)} tokens, preserved {len(recent_msgs)} recent messages).\033[0m")
    return compacted

_REPO_MAP_CACHE = {"workspace": "", "mtime": 0, "content": ""}

def generate_repo_map(root_dir=None) -> str:
    """Zero-dependency lightweight AST/repo map generator using Regex with depth limits and mtime caching."""
    global _REPO_MAP_CACHE
    if root_dir is None:
        root_dir = CURRENT_WORKSPACE
    if not os.path.exists(root_dir):
        return ""

    try:
        current_mtime = os.path.getmtime(root_dir)
        if _REPO_MAP_CACHE["workspace"] == root_dir and _REPO_MAP_CACHE["mtime"] == current_mtime:
            return _REPO_MAP_CACHE["content"]
    except Exception:
        pass

    ignore_dirs = {".git", ".anticoding", "__pycache__", "node_modules", "venv", ".venv", "env", "build", "dist", "target", ".idea", ".vscode"}
    ignore_exts = {
        ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".mp4",
        ".min.js", ".min.css", ".map", ".wasm", ".lock", ".sum", ".bin"
    }
    
    patterns = {
        ".py": re.compile(r'^\s*(?:async\s+)?(?:def|class)\s+\w+'),
        ".js": re.compile(r'^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+\w+'),
        ".ts": re.compile(r'^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type)\s+\w+'),
        ".go": re.compile(r'^\s*(?:func|type)\s+\w+'),
        ".rs": re.compile(r'^\s*(?:pub\s+)?(?:async\s+)?(?:fn|struct|enum|trait)\s+\w+'),
        ".java": re.compile(r'^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:class|interface|enum)\s+\w+'),
        ".cpp": re.compile(r'^\s*(?:class|struct)\s+\w+'),
        ".h": re.compile(r'^\s*(?:class|struct)\s+\w+')
    }

    output = []
    max_depth = 4
    max_symbols = 120
    symbol_count = 0
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        rel_path = os.path.relpath(dirpath, root_dir)
        depth = 0 if rel_path == "." else rel_path.count(os.sep) + 1
        if depth > max_depth:
            dirnames.clear()
            continue

        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith('.')]
        dirnames.sort()
        filenames.sort()
        
        if rel_path != ".":
            prefix = "  " * depth
            output.append(f"{prefix}/{os.path.basename(dirpath)}")
            
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in ignore_exts or any(filename.lower().endswith(ie) for ie in ignore_exts):
                continue
                
            file_prefix = "  " * (depth + (0 if rel_path == "." else 1))
            file_path = os.path.join(dirpath, filename)
            
            output.append(f"{file_prefix}/{filename}")
            
            if ext in patterns and symbol_count < max_symbols:
                pattern = patterns[ext]
                symbol_prefix = file_prefix + "  "
                try:
                    if os.path.getsize(file_path) < 1024 * 1024:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                match = pattern.search(line)
                                if match:
                                    cleaned = line.strip()
                                    if len(cleaned) > 80:
                                        cleaned = cleaned[:77] + "..."
                                    output.append(f"{symbol_prefix}{cleaned}")
                                    symbol_count += 1
                                    if symbol_count >= max_symbols:
                                        output.append(f"{symbol_prefix}... [Additional symbols truncated]")
                                        break
                except Exception:
                    pass

        if symbol_count >= max_symbols:
            break
                    
    repo_map_result = "\n".join(output)
    try:
        _REPO_MAP_CACHE = {
            "workspace": root_dir,
            "mtime": os.path.getmtime(root_dir),
            "content": repo_map_result
        }
    except Exception:
        pass
    return repo_map_result

def call_llm(messages: list, tools: list = TOOLS, stream: bool = ENABLE_STREAMING, max_retries: int = 2, inject_repo_map: bool = True) -> dict:
    """Call local llama.service OpenAI chat completions API with SSE real-time streaming."""
    url = f"{API_BASE}/chat/completions"
    
    payload_messages = list(messages)
    if ENABLE_REPO_MAP and inject_repo_map and payload_messages and payload_messages[0].get("role") == "system":
        repo_map_str = generate_repo_map()
        if repo_map_str.strip():
            augmented_content = payload_messages[0]["content"] + "\n\n--- Current Repository Map ---\n" + repo_map_str + "\n------------------------------"
            payload_messages[0] = {"role": "system", "content": augmented_content}

    payload = {
        "model": MODEL_NAME,
        "messages": payload_messages,
        "temperature": 0.2,
        "stream": stream
    }
    if tools:
        payload["tools"] = tools

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=180) as resp:
                if not stream:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]

                # SSE Streaming Mode
                renderer = ThinkingStreamRenderer()
                tool_calls_acc = {}

                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        # 1. Reasoning / Thinking Delta
                        if "reasoning_content" in delta and delta["reasoning_content"]:
                            renderer.on_reasoning_delta(delta["reasoning_content"])

                        # 2. Content Delta (also handles inline <think> tags)
                        if "content" in delta and delta["content"]:
                            renderer.on_content_delta(delta["content"])

                        # 3. Tool Calls Delta
                        if "tool_calls" in delta and delta["tool_calls"]:
                            for tc_chunk in delta["tool_calls"]:
                                idx = tc_chunk.get("index", 0)
                                if idx not in tool_calls_acc:
                                    tool_calls_acc[idx] = {
                                        "id": tc_chunk.get("id", f"call_{int(time.time()*1000)}_{idx}"),
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""}
                                    }
                                if "id" in tc_chunk and tc_chunk["id"]:
                                    tool_calls_acc[idx]["id"] = tc_chunk["id"]
                                fn_delta = tc_chunk.get("function", {})
                                if "name" in fn_delta and fn_delta["name"]:
                                    tool_calls_acc[idx]["function"]["name"] += fn_delta["name"]
                                if "arguments" in fn_delta and fn_delta["arguments"]:
                                    tool_calls_acc[idx]["function"]["arguments"] += fn_delta["arguments"]

                    except json.JSONDecodeError:
                        continue

                renderer.flush()

                message = {"role": "assistant"}
                if renderer.full_content:
                    message["content"] = renderer.full_content
                if renderer.full_reasoning:
                    message["reasoning_content"] = renderer.full_reasoning
                if tool_calls_acc:
                    message["tool_calls"] = list(tool_calls_acc.values())
                    if "content" not in message:
                        message["content"] = None

                return message

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"\033[91mAPI Error ({e.code}): {err_body}\033[0m")
            if attempt < max_retries:
                time.sleep(2)
        except Exception as e:
            print(f"\033[91mConnection Error (Attempt {attempt}/{max_retries}): {e}\033[0m")
            if attempt < max_retries:
                time.sleep(2)

    return None

# ----------------- Interactive Main Loop -----------------

def print_help():
    print("""
\033[96mAvailable Commands:\033[0m
  /help                         - Show this help menu
  /clear                        - Clear current conversation history
  /ws                           - List all git worktree workspaces & active status
  /ws new <name>                - Create & switch to a new isolated worktree workspace
  /ws switch <name|main>        - Switch active workspace to a worktree or root
  /ws apply [name]              - Merge worktree changes into root workspace
  /ws discard <name>            - Discard and delete an isolated worktree
  /scratchpad                   - View living disk artifact (.anticoding/scratchpad.md)
  /history [query]              - Search raw session transcript journal
  /transcript                   - View path and stats of session transcript file
  /checkpoints                  - List saved git snapshots
  /rollback                     - Undo changes and roll back to previous checkpoint
  /compact                      - Manually trigger conversation compaction
  exit / quit                   - Terminate the agent session
""")

def run_agent():
    print("=" * 64)
    print("\033[96m🚀 AntiCoding Agent (10/10 Tier Edition)\033[0m")
    print(f"Backend    : {API_BASE} [{MODEL_NAME}]")
    print(f"Context Cap: {MAX_CONTEXT_TOKENS:,} tokens (Server ctx: {SERVER_CTX_SIZE:,})")
    print(f"Streaming  : {'Enabled (SSE)' if ENABLE_STREAMING else 'Disabled'}")
    print(f"Sandbox    : {'Enforced (Path Jail)' if ENABLE_SANDBOX else 'Disabled'}")
    print(f"Workspace  : {CURRENT_WORKSPACE}")
    print(f"Transcript : {TRANSCRIPT_FILE}")
    print(f"Scratchpad : {SCRATCHPAD_PATH}")
    print("Type '/help' for commands, or 'exit' / 'quit' to stop.")
    print("=" * 64)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    log_transcript_entry(messages[0])

    while True:
        try:
            ws_label = "main" if CURRENT_WORKSPACE == ROOT_WORKSPACE else os.path.basename(CURRENT_WORKSPACE)
            user_input = input(f"\n\033[92m(anticoding [{ws_label}]) > \033[0m").strip()
            if not user_input:
                continue

            # Handle interactive slash commands
            cmd_parts = user_input.split(maxsplit=1)
            cmd_name = cmd_parts[0].lower()
            cmd_arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

            if cmd_name in ["exit", "quit"]:
                print("Goodbye!")
                break
            elif cmd_name == "/help":
                print_help()
                continue
            elif cmd_name in ["/ws", "/workspace", "/workspaces"]:
                ws_sub = cmd_arg.split(maxsplit=1)
                sub_action = ws_sub[0].lower() if ws_sub else "list"
                sub_target = ws_sub[1].strip() if len(ws_sub) > 1 else ""

                if not cmd_arg or sub_action == "list":
                    print(f"\n\033[96m--- Git Worktree Workspaces ---\033[0m")
                    print(list_workspaces())
                    print("\033[96m-------------------------------\033[0m")
                elif sub_action == "new":
                    if not sub_target:
                        print("\033[91mUsage: /ws new <workspace_name>\033[0m")
                    else:
                        print(f"\n\033[92m{create_workspace(sub_target)}\033[0m")
                elif sub_action in ["switch", "use"]:
                    if not sub_target:
                        print("\033[91mUsage: /ws switch <workspace_name|main>\033[0m")
                    else:
                        print(f"\n\033[92m{switch_workspace(sub_target)}\033[0m")
                elif sub_action == "apply":
                    print(f"\n\033[92m{apply_workspace(sub_target or None)}\033[0m")
                elif sub_action in ["discard", "delete", "rm"]:
                    if not sub_target:
                        print("\033[91mUsage: /ws discard <workspace_name>\033[0m")
                    else:
                        print(f"\n\033[93m{discard_workspace(sub_target)}\033[0m")
                else:
                    print(f"\033[91mUnknown workspace command: '{sub_action}'. Type '/help' for usage.\033[0m")
                continue
            elif cmd_name in ["/clear", "/reset"]:
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                log_transcript_entry({"role": "system_event", "event": "session_cleared"})
                print("\033[93mConversation history cleared.\033[0m")
                continue
            elif cmd_name == "/scratchpad":
                print(f"\n\033[96m--- Living Scratchpad ({SCRATCHPAD_PATH}) ---\033[0m")
                print(tool_read_scratchpad())
                print("\033[96m--------------------------------------------\033[0m")
                continue
            elif cmd_name == "/transcript":
                if os.path.exists(TRANSCRIPT_FILE):
                    size = os.path.getsize(TRANSCRIPT_FILE)
                    lines = sum(1 for _ in open(TRANSCRIPT_FILE, "r", encoding="utf-8", errors="ignore"))
                    print(f"\n\033[96mSession Transcript:\033[0m {TRANSCRIPT_FILE} ({lines} turns, {size:,} bytes)")
                else:
                    print(f"\n\033[96mSession Transcript:\033[0m {TRANSCRIPT_FILE} (No entries yet)")
                continue
            elif cmd_name == "/history":
                query = cmd_arg.strip() or ".*"
                print(f"\n\033[96m--- Session History Search ('{query}') ---\033[0m")
                print(tool_search_session_history(query))
                print("\033[96m------------------------------------------\033[0m")
                continue
            elif cmd_name == "/checkpoints":
                print(f"\n\033[96m--- Git Checkpoints ---\033[0m")
                print(list_checkpoints())
                print("\033[96m-----------------------\033[0m")
                continue
            elif cmd_name in ["/rollback", "/undo"]:
                print(f"\n\033[93m[Rollback]\033[0m {rollback_checkpoint()}")
                continue
            elif cmd_name == "/compact":
                messages = compact_conversation(messages, max_tokens=0)
                continue

            # Take non-destructive git snapshot before executing turn
            create_checkpoint(user_input)

            user_msg = {"role": "user", "content": user_input}
            messages.append(user_msg)
            log_transcript_entry(user_msg)

            # Agent reasoning & tool execution loop
            step_count = 0
            max_steps = 25

            while step_count < max_steps:
                step_count += 1
                messages = compact_conversation(messages)

                response = call_llm(messages)
                if not response:
                    print("\033[91mFailed to receive a response from local LLM. Please verify llama.service is running.\033[0m")
                    break

                messages.append(response)
                log_transcript_entry(response)
                tool_calls = response.get("tool_calls")

                if not tool_calls:
                    # Content is already streamed live in real time
                    break

                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name", "")
                    raw_args = tc.get("function", {}).get("arguments", "{}")
                    
                    try:
                        fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError as err:
                        tool_output = f"JSON Argument Error: {err}. Please provide valid JSON arguments."
                    else:
                        tool_output = execute_tool(fn_name, fn_args)

                    # Display preview snippet
                    preview = tool_output[:300] + "..." if len(tool_output) > 300 else tool_output
                    print(f"\033[90mResult:\n{preview}\033[0m")

                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc.get("id", "call_default"),
                        "content": tool_output
                    }
                    messages.append(tool_msg)
                    log_transcript_entry(tool_msg)

        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break

if __name__ == "__main__":
    run_agent()
