# 🚀 AntiCoding Agent

**AntiCoding Agent** is an autonomous, **zero-dependency** AI pair-programmer built with 100% Python 3 standard library. It connects to **any OpenAI-compatible Chat Completions API** (`/v1/chat/completions`) — from local **llama.cpp**, **Ollama**, and **vLLM** servers to cloud **OpenAI**, **DeepSeek**, and **OpenRouter** endpoints.

---

## 🌟 Key Features

* **Zero External Dependencies**: 100% pure Python 3 standard library (`urllib`, `json`, `difflib`, `argparse`, `subprocess`, `re`, `os`). Drop a single file onto any Linux/macOS machine, container, or air-gapped server and run immediately.
* **Universal OpenAI-Compatible Client**: Works seamlessly with local inference servers (`llama-server`, `Ollama`, `vLLM`, `LM Studio`) and cloud APIs (`OpenAI`, `DeepSeek`, `OpenRouter`). Includes a built-in fallback `<tool_call>` parser for local GGUF models launched without `--jinja`.
* **Real-time SSE Token & Reasoning Streaming**: Word-by-word streaming with live `<think> ... </think>` and `reasoning_content` demuxing rendered in dim gray.
* **Live Colored Unified Diffs**: Displays instant ANSI-colored `+`/`-` unified diff previews (`difflib.unified_diff`) in the terminal whenever files are modified.
* **Isolated Git Worktree Workspaces**: Spawns isolated Git worktree branches (`.anticoding/workspaces/<name>`) via `/ws new <name>` so the agent can experiment and run tests without touching your active editor files.
* **Dynamic Repo Map Injection**: A zero-dependency AST heuristic extractor scans your workspace (with `mtime` caching and depth/symbol caps) and injects class/function skeletons into the System Prompt.
* **Non-Destructive Git Checkpoints & Rollback**: Captures worktree-aware `.patch` snapshots before every turn; run `/rollback` to restore the exact pre-turn state.
* **Hybrid Memory Architecture**:
  * **Living Disk Artifacts** (`.anticoding/scratchpad.md`): Persistent project goals, plans, and architectural notes.
  * **Turn-Boundary Compaction**: Smart rolling summarization preserving your root goal and recent multi-turn context.
  * **Deep History Recovery** (`search_session_history`): Full disk-backed JSONL session transcript journal for 100% byte-exact recall of earlier stack traces and outputs after compaction.
* **Workspace Sandbox & Human-in-the-Loop Mode**: Enforces a canonical Path Jail (`is_safe_path`), blocks destructive shell patterns (`is_safe_command`), and supports interactive confirmation mode (`--ask` or `/mode ask`).

---

## 🚀 Quickstart

### 1. Direct Execution (Zero Install)

```bash
# Interactive REPL session
python3 anticoding_agent.py

# Headless one-shot prompt
python3 anticoding_agent.py -p "Refactor utils.py and run unit tests"

# Pipe compiler/test output directly into AntiCoding Agent
pytest 2>&1 | python3 anticoding_agent.py -p "Fix this failing test"
```

### 2. Global CLI Install via `pipx` or `uv`

```bash
pipx install .
# or: uv tool install .

# Run from any Git repository on your machine:
anticoding
anticoding -p "Explain the architecture of this repo" --ask
```

---

## 🔌 Supported API Providers (`ANTICODING_API_BASE` / `OPENAI_BASE_URL`)

`ANTICODING_API_BASE` (or standard `OPENAI_BASE_URL`) accepts any **OpenAI-compatible `/v1` API Base URL**. The agent calls `{API_BASE}/chat/completions`.

| Provider | `ANTICODING_API_BASE` (`OPENAI_BASE_URL`) | `ANTICODING_API_KEY` (`OPENAI_API_KEY`) | Example `ANTICODING_MODEL` |
| :--- | :--- | :--- | :--- |
| **OpenAI Official API** | `https://api.openai.com/v1` | `sk-...` (Your OpenAI key) | `gpt-4.1` / `o4-mini` |
| **Ollama (Local)** | `http://127.0.0.1:11434/v1` | `ollama` (or leave default) | `qwen2.5-coder:32b` |
| **llama.cpp (`llama-server`)** | `http://127.0.0.1:8080/v1` *(or `:8081/v1`)* | `sk-no-key-required` | `Qwen3-Coder-Next-Q8_0` |
| **vLLM (Local / Self-Hosted)** | `http://127.0.0.1:8000/v1` | `sk-no-key-required` | `Qwen/Qwen2.5-Coder-32B-Instruct` |
| **DeepSeek API** | `https://api.deepseek.com/v1` | `sk-...` (Your DeepSeek key) | `deepseek-chat` / `deepseek-reasoner` |
| **OpenRouter** | `https://openrouter.ai/api/v1` | `sk-or-...` (Your OpenRouter key) | `qwen/qwen-2.5-coder-32b-instruct` |

---

## ⚙️ Configuration & CLI Flags

Copy `.env.example` to `.env` in your project root (automatically loaded on startup by the built-in zero-dependency `.env` parser), export environment variables, or pass CLI flags:

```bash
cp .env.example .env
```

### Environment Variables

| Environment Variable | Fallback Alias | Default | Description |
| :--- | :--- | :--- | :--- |
| `ANTICODING_API_BASE` | `OPENAI_BASE_URL`, `OPENAI_API_BASE` | `http://127.0.0.1:8081/v1` | OpenAI-compatible `/v1` API base URL |
| `ANTICODING_API_KEY` | `OPENAI_API_KEY` | `sk-no-key-required` | API Bearer token (optional for local servers) |
| `ANTICODING_MODEL` | `OPENAI_MODEL` | `Qwen3-Coder-Next-Q8_0` | Model identifier sent in chat completion requests |
| `ANTICODING_CTX_SIZE` | — | `131072` | Total context window size of the target model |
| `ANTICODING_MAX_TOKENS` | — | `98304` | Context token threshold before rolling compaction triggers |
| `ANTICODING_RECENT_MSGS` | — | `14` | Number of recent messages preserved during compaction |
| `ANTICODING_CONFIRM` | — | `auto` | Execution approval mode: `auto` or `ask` |

### Command-Line Flags

| Flag | Description |
| :--- | :--- |
| `-p`, `--prompt <text>` | Run a single prompt non-interactively and exit (automatically reads piped `stdin` if present) |
| `-m`, `--model <name>` | Override the target model name for this session |
| `--api-base <url>` | Override the OpenAI-compatible `/v1` base URL |
| `--api-key <key>` | Override the API Bearer token |
| `--ask` | Enable human-in-the-loop confirmation before running shell commands or modifying files |
| `--no-sandbox` | Disable workspace path jail and shell command pattern filters |
| `--no-stream` | Disable SSE token streaming |
| `-v`, `--version` | Display version information |

---

## 🛠️ Built-in Agent Tools

| Tool | Function | Description |
| :--- | :--- | :--- |
| **`search_session_history`** | Deep History Recall | Searches past conversation turns, raw tool outputs, or exact error tracebacks from earlier in the session |
| **`replace_file_content`** | Surgical Editor | Modifies a unique code block in an existing file and renders a colored unified diff preview |
| **`read_file`** | Line-Sliced Reader | Reads file contents with 1-indexed line numbers and optional `start_line` / `end_line` |
| **`search_files`** | Regex Grep | Recursively searches for regex patterns across files (automatically skips binaries, lockfiles, and minified bundles) |
| **`run_command`** | Bash Shell | Executes terminal commands in the active workspace with timeout and safety filtering |
| **`write_file`** | File Creator | Creates new files or overwrites existing files with colored diff preview |
| **`list_dir`** | Directory Listing | Lists files and subdirectories with `[DIR]` markers |
| **`update_scratchpad`** | Living Memory | Writes/updates project goals and findings in `.anticoding/scratchpad.md` |
| **`read_scratchpad`** | Living Memory | Reads the persistent project plan from `.anticoding/scratchpad.md` |

---

## ⚡ Interactive Slash Commands

| Command | Action |
| :--- | :--- |
| `/mode [auto\|ask]` | Toggles between autonomous execution (`auto`) and interactive user confirmation (`ask`) |
| `/ws` or `/workspaces` | Lists all active Git worktree workspaces & active status |
| `/ws new <name>` | Creates & switches to a new isolated Git worktree workspace |
| `/ws switch <name\|main>` | Switches active workspace between worktrees or returns to root |
| `/ws apply [name]` | Merges tested changes from a worktree branch into your root workspace |
| `/ws discard <name>` | Deletes an isolated worktree and cleans up its branch |
| `/history [query]` | Searches raw session transcript journal for past steps, tracebacks, or outputs |
| `/transcript` | Shows path, turn count, and file size of the active session transcript journal |
| `/rollback` or `/undo` | Restores workspace files to the exact state captured in the previous `.patch` checkpoint |
| `/checkpoints` | Lists saved Git snapshot patches |
| `/scratchpad` | Displays the current content of `.anticoding/scratchpad.md` |
| `/compact` | Manually triggers rolling compaction on conversation history |
| `/clear` or `/reset` | Resets conversation messages back to a clean slate |
| `/help` | Shows interactive help menu |
| `exit` or `quit` | Exits the agent session |

---

## 📄 License & Security

Licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](./LICENSE). See [SECURITY.md](./SECURITY.md) for sandbox architecture and threat-model details.
