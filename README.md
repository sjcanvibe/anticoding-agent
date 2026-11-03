# 🚀 AntiCoding Agent

**AntiCoding Agent** is an autonomous, zero-dependency local AI pair-programmer powered by your local OpenAI-compatible inference server (`llama.cpp` / `llama.service` / `vLLM` / `Ollama`, optimized for `Qwen3-Coder-Next-Q8_0` 128k context).

---

## 🌟 Features

* **Zero External Dependencies**: Built with 100% pure Python 3 standard library (`urllib`, `json`, `subprocess`, `re`, `os`).
* **Deep History Recovery**: Full disk-backed JSONL session transcript journal with native `search_session_history` tool for 100% byte-for-byte recall of past errors and outputs.
* **Real-time SSE Token Streaming**: Word-by-word streaming for instant, snappy terminal feedback.
* **Thinking & Reasoning Highlighting**: Automatically detects `<think> ... </think>` blocks or `reasoning_content` deltas and renders them in dim gray.
* **Workspace Path Jail & Sandboxing**: Strict Path Jail (`is_safe_path`) prevents directory traversal outside the active workspace; blocks dangerous system commands (`sudo`, `rm -rf /`, `mkfs`).
* **Isolated Git Worktree Workspaces**: Spawns isolated Git worktree branches (`.anticoding/workspaces/<name>`) so the AI can experiment and test code without touching your active editor files.
* **Dynamic Repo Map Injection**: A zero-dependency AST heuristic extractor scans your workspace (with `mtime` caching and depth/symbol throttling) and injects the project's class/function skeletons directly into the System Prompt.
* **Automatic Git Checkpoints & Rollback**: Creates non-destructive worktree-aware snapshots before modifications; use `/rollback` to undo errors.
* **128k Context Optimized**: Pre-configured for local servers running with `--ctx-size 131072`.
* **Hybrid Memory Architecture**:
  * **Living Disk Artifacts** (`.anticoding/scratchpad.md`): Long-term memory, plans, and architectural discoveries persisted on disk.
  * **Turn-Boundary Compaction**: Smart summarization preserving the initial user goal and rich recent multi-turn context.
* **Surgical File Editing**: Block-level replacement tool (`replace_file_content`) avoids full-file rewrites.
* **Line-Numbered Slicing**: Targeted file viewing (`read_file`) with start/end line offsets.
* **Fast Code Search**: Built-in regex grep engine (`search_files`) with binary, lockfile, and minified bundle filtering.

---

## 🚀 Quickstart

### Option 1: Direct Execution (Zero Install)

```bash
python3 anticoding_agent.py
```

### Option 2: Global CLI Install via `pipx` or `uv`

```bash
pipx install .
# or: uv tool install .

# Run from any git repository on your machine:
anticoding
```

---

## 🛠️ Built-in Tools

| Tool | Function | Description |
| :--- | :--- | :--- |
| **`search_session_history`** | Deep History Recall | Searches past conversation turns, previous raw tool outputs, or exact error messages from earlier in the session |
| **`replace_file_content`** | Surgical Editor | Modifies a specific code block in an existing file without whole-file rewrites |
| **`read_file`** | Line-Sliced Reader | Reads file contents with line numbers and optional `start_line` / `end_line` |
| **`search_files`** | Regex Grep | Recursively searches for regex patterns or keywords across directory files |
| **`run_command`** | Bash Shell | Executes terminal commands and returns stdout/stderr with output truncation |
| **`write_file`** | File Creator | Creates new files or overwrites existing files |
| **`list_dir`** | Directory Listing | Lists files and subdirectories with type indicators |
| **`update_scratchpad`** | Living Memory | Writes/updates project goals and findings in `.anticoding/scratchpad.md` |
| **`read_scratchpad`** | Living Memory | Reads the persistent project plan from `.anticoding/scratchpad.md` |

---

## ⚡ Interactive Slash Commands

| Command | Action |
| :--- | :--- |
| `/ws` or `/workspaces` | Lists all active git worktree workspaces & active status |
| `/ws new <name>` | Creates & switches to a new isolated Git worktree workspace |
| `/ws switch <name\|main>` | Switches active workspace between worktrees or returns to root |
| `/ws apply [name]` | Merges tested changes from a worktree into your main workspace |
| `/ws discard <name>` | Deletes an isolated worktree and cleans up its branch |
| `/history [query]` | Searches raw session transcript journal for past steps, tracebacks, or outputs |
| `/transcript` | Shows path, turn count, and file size of the active session transcript journal |
| `/rollback` or `/undo` | Undoes workspace modifications and restores previous git checkpoint |
| `/checkpoints` | Lists available saved git snapshot patches |
| `/scratchpad` | Displays the current content of `.anticoding/scratchpad.md` |
| `/compact` | Manually triggers rolling compaction on conversation history |
| `/clear` or `/reset` | Resets conversation messages back to clean slate |
| `/help` | Shows interactive help menu |
| `exit` or `quit` | Exits the agent session |

---

## ⚙️ Configuration

Copy `.env.example` to `.env` in your repository root, or adjust environment variables directly at the top of [`anticoding_agent.py`](./anticoding_agent.py):

```bash
cp .env.example .env
```

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `ANTICODING_API_BASE` | `http://127.0.0.1:8081/v1` | OpenAI-compatible API endpoint URL |
| `ANTICODING_API_KEY` | `sk-no-key-required` | Bearer token for local/remote server |
| `ANTICODING_MODEL` | `Qwen3-Coder-Next-Q8_0` | Model identifier served by backend |
| `ANTICODING_CTX_SIZE` | `131072` | Total context window size of inference server |
| `ANTICODING_MAX_TOKENS` | `98304` | Token threshold before turn-boundary compaction |
| `ANTICODING_RECENT_MSGS` | `14` | Number of recent messages preserved during compaction |

---

## 📄 License

Licensed under the [MIT License](./LICENSE). See [SECURITY.md](./SECURITY.md) for sandbox architecture and threat-model details.
