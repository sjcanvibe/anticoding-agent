# Security Policy & Sandbox Model

## Sandbox Architecture

AntiCoding Agent includes two built-in application-level safety layers enabled by default (`ENABLE_SANDBOX = True`):

1. **Filesystem Path Jail (`is_safe_path`)**:
   Restricts `read_file`, `write_file`, `replace_file_content`, `search_files`, and `list_dir` strictly to the active workspace directory via canonical path resolution (`os.path.abspath` + `os.path.realpath`).
2. **Command Pattern Filter (`is_safe_command`)**:
   Blocks known high-risk shell patterns (`sudo`, root/home `rm -rf`, `mkfs`, `fdisk`, `dd`, fork bombs, `/etc/` and `/usr/` redirection) in `run_command`.

## Threat Model Disclaimer

Application-level regex filtering is a guardrail against accidental destructive actions by the LLM, **not an OS kernel sandbox**. Because `run_command` executes arbitrary shell subcommands under your user privileges, always run autonomous coding agents inside an isolated container, VM, or unprivileged user account when working with untrusted prompts or repositories.
