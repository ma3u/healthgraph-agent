# Pre-commit hooks

Local git hooks that run linters + security checks before each commit/push.
The security checks are modeled on [ma3u/TwoBreath-app](https://github.com/ma3u/TwoBreath-app)
(gitleaks secret scanning, sensitive-file blocking, SwiftLint), extended with
Python lint/security for this repo's ETL and scripts.

## Setup (one time)

```bash
pip install pre-commit
brew install gitleaks swiftlint     # used by the local hooks
pre-commit install                   # wires up pre-commit + pre-push
```

Run against the whole repo any time:

```bash
pre-commit run --all-files
```

## What runs

| Hook | Stage | What it does |
|------|-------|--------------|
| **gitleaks** (`protect --staged`) | commit | Blocks commits containing secrets. Config: `.gitleaks.toml` (default rules + Neo4j/Aura/NAMS patterns). |
| **gitleaks** (`detect`) | push | Full scan before pushing — catches anything in history. |
| **block-sensitive-files** | commit | Refuses `.env`, `*.pem/key/p12/p8/cer`, `*.mobileprovision`, `*credentials*`. Script: `scripts/hooks/check_sensitive_files.sh`. |
| **detect-private-key** | commit | Standard private-key detector. |
| **swiftlint** | commit | Lints `ios/**/*.swift`. Config: `.swiftlint.yml`. |
| **ruff** + **ruff-format** | commit | Python lint (+autofix) and formatting. Config: `pyproject.toml [tool.ruff]`. |
| **bandit** | commit | Python security scan of `etl/` + `scripts/`. Config: `pyproject.toml [tool.bandit]`. |
| trailing-whitespace, end-of-file-fixer, check-yaml/json, check-added-large-files, check-merge-conflict, mixed-line-ending | commit | General hygiene. |

`data/`, `docs/snapshot/`, and the generated `*.xcodeproj` are excluded.

## Notes
- Hooks only run on **staged** files, so adopting them on existing code is incremental.
- `gitleaks` and `swiftlint` are invoked from your `PATH`; if not installed the hook prints a warning instead of failing (so CI/others aren't blocked). Install them for full coverage.
- Bypass in a genuine emergency with `git commit --no-verify` (avoid for the secret/sensitive-file hooks).
- `.env` is already gitignored; these hooks are the second line of defense.
