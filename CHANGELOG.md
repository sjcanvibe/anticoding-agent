# Changelog

All notable changes to **AntiCoding Agent** are documented in this file.

## [2.1.0] - 2026-11-03

### Added
- **Zero-Dependency `.env` Loader (`load_dotenv`)**: Automatically loads `.env` from the repository root or working directory on startup (`export KEY=VAL`, single/double-quoted values) alongside standard `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` aliases.
- **Headless CLI & Pipe Mode (`-p` / `--prompt`)**: Execute one-shot prompts non-interactively and pipe compiler/test logs directly via `stdin` (e.g., `pytest 2>&1 | anticoding -p "Fix this failure"`).
- **Human-in-the-Loop Confirmation (`--ask` / `/mode ask`)**: Interactive `[Y/n/a(lways)]` approval prompt before shell execution or file modifications.
- **Fallback `<tool_call>` Parser**: Extracts `<tool_call>{...}</tool_call>` JSON blocks emitted by local GGUF models (`llama-server`, `Ollama`) when native OpenAI `tool_calls` array is omitted.
- **Stdlib Colored Unified Diffs**: Renders instant ANSI `+`/`-` diff previews via `difflib.unified_diff` before applying `write_file` or `replace_file_content`.

### Changed
- **Relicensed under GNU AGPL v3.0 (`AGPL-3.0-only`)**: Protects open-source modifications across network/SaaS deployments.
- **Hardened Git Checkpoints & Rollback**: Preserves pre-existing untracked files and `.anticoding/` runtime state during `/rollback` and scopes checkpoints per workspace (`root` vs. isolated Git worktrees).
- **Strict Role Alternation on Compaction**: Ensures `system -> user -> assistant` message role alternation after rolling context compaction for strict Jinja chat templates (`llama.cpp`, `vLLM`, `Mistral`, `DeepSeek`).
- **Cached & Bounded Repo Map (`generate_repo_map`)**: Added `mtime` caching, automatic cache invalidation on file mutations, depth limits (`max_depth=4`), and symbol caps (`max_symbols=120`).
