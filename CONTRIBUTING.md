# Contributing to AntiCoding Agent

Thank you for your interest in improving AntiCoding Agent!

## 📜 Core Architectural Guidelines

To preserve the agent's unique design, all contributions must respect these three principles:

1. **Zero External Dependencies:**
   The agent must run on 100% pure Python 3 standard library (`urllib`, `json`, `subprocess`, `re`, `os`). Do not introduce external PyPI runtime dependencies (`requests`, `rich`, `langchain`, `pydantic`, etc.).
2. **Cross-Platform UNIX Compatibility:**
   Ensure file paths, subprocess invocations, and ANSI escape sequences work across Linux and macOS environments.
3. **Safety & Sandboxing Integrity:**
   Modifications to `is_safe_path()` or `is_safe_command()` must never weaken workspace path jail boundaries or destructive command filters.

## 🛠️ Submitting Changes

1. Fork the repository and create a feature branch (`git checkout -b feat/my-improvement`).
2. Verify code syntax and compilation:
   ```bash
   python3 -m py_compile anticoding_agent.py
   ```
3. Commit your changes with conventional commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
4. Push to your branch and open a Pull Request.
