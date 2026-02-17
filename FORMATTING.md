# Code Formatting & Quality Standards

This project uses **production-grade automated code formatting** to ensure consistent, high-quality code across the entire codebase.

---

## 🚀 Quick Start

### First Time Setup

```bash
# Install development dependencies with uv
uv pip install -r requirements-dev.txt

# Install pre-commit hooks (runs formatters automatically on git commit)
pre-commit install
```

### Format Your Code

```bash
# Format all Python files with Black
black .

# Sort imports with isort
isort .

# Lint and auto-fix with Ruff
ruff check --fix .

# Or run all pre-commit hooks manually
pre-commit run --all-files
```

---

## 🛠️ Tools Used

### 1. **Black** - Code Formatter
- **Purpose**: Enforces consistent code style (PEP 8 compliant)
- **Line length**: 100 characters
- **Target**: Python 3.11+
- **Config**: `[tool.black]` in `pyproject.toml`

**Example:**
```python
# Before
def my_function(x,y,z):
    return x+y+z

# After Black
def my_function(x, y, z):
    return x + y + z
```

### 2. **isort** - Import Sorter
- **Purpose**: Organizes imports alphabetically and by section
- **Profile**: Black-compatible
- **Sections**: FUTURE → STDLIB → THIRDPARTY → FIRSTPARTY → LOCALFOLDER
- **Config**: `[tool.isort]` in `pyproject.toml`

**Example:**
```python
# Before
import os
from src.utils import helper
import sys
from typing import List

# After isort
import os
import sys
from typing import List

from src.utils import helper
```

### 3. **Ruff** - Fast Linter
- **Purpose**: Catches bugs, code smells, and style issues
- **Speed**: 10-100x faster than Flake8
- **Rules**: pycodestyle, pyflakes, isort, bugbear, comprehensions
- **Config**: `[tool.ruff]` in `pyproject.toml`

---

## ⚙️ Configuration

All formatting tools are configured in [`pyproject.toml`](pyproject.toml):

```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

[tool.ruff]
line-length = 100
target-version = "py311"
```

---

## 🪝 Pre-commit Hooks (Automatic Formatting)

Pre-commit hooks **automatically format your code** before each commit.

### What Runs on Every Commit?
1. ✅ Black (code formatting)
2. ✅ isort (import sorting)
3. ✅ Ruff (linting + auto-fixes)
4. ✅ Trailing whitespace removal
5. ✅ End-of-file fixer
6. ✅ YAML/JSON/TOML validation
7. ✅ Large file detection
8. ✅ Merge conflict detection
9. ✅ Private key detection

### Enable Pre-commit Hooks

```bash
pre-commit install
```

### Run Manually (Without Committing)

```bash
# Run on all files
pre-commit run --all-files

# Run on specific files
pre-commit run --files src/main_agent.py

# Run only Black
pre-commit run black --all-files
```

### Skip Hooks (Emergency Only!)

```bash
# ⚠️ Use sparingly - only in emergencies
git commit --no-verify -m "Emergency commit"
```

---

## 🔄 CI/CD Enforcement (GitHub Actions)

Code quality is **automatically enforced** in CI/CD pipelines.

### What Happens on Every PR?

Our [`.github/workflows/code-quality.yml`](.github/workflows/code-quality.yml) workflow:

1. ✅ Checks if code is formatted with Black
2. ✅ Checks if imports are sorted with isort
3. ✅ Lints code with Ruff
4. ✅ Runs all pre-commit hooks

**If checks fail, the PR cannot be merged.**

### How to Fix Failing CI Checks?

```bash
# Run formatters locally
black .
isort .
ruff check --fix .

# Verify everything passes
pre-commit run --all-files

# Commit and push
git add .
git commit -m "Fix formatting"
git push
```

---

## 📝 Development Workflow

### Recommended Workflow

```bash
# 1. Make your changes
vim src/agent_service/api/endpoints/agent_stream.py

# 2. Format code (pre-commit does this automatically on commit)
black src/agent_service/api/endpoints/agent_stream.py
isort src/agent_service/api/endpoints/agent_stream.py

# 3. Check for issues
ruff check src/agent_service/api/endpoints/agent_stream.py

# 4. Commit (pre-commit hooks run automatically)
git add src/agent_service/api/endpoints/agent_stream.py
git commit -m "Update agent streaming logic"

# 5. Push (CI checks run automatically)
git push
```

### IDE Integration (Optional but Recommended)

#### VS Code
```json
// .vscode/settings.json
{
  "python.formatting.provider": "black",
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

#### PyCharm
1. Install Black plugin
2. Settings → Tools → Black → Enable Black formatter
3. Settings → Tools → Actions on Save → Reformat code

---

## 🎯 Standards & Best Practices

### Line Length
- **Maximum**: 100 characters
- **Why**: Better readability, fits on most screens

### Import Order
```python
# 1. Future imports
from __future__ import annotations

# 2. Standard library
import os
import sys
from typing import List

# 3. Third-party packages
from fastapi import APIRouter
from langchain import LLM

# 4. First-party (our code)
from src.agent_service.core.config import settings

# 5. Local folder
from .utils import helper
```

### Code Style
- ✅ Use double quotes for strings (`"hello"`)
- ✅ Trailing commas in multi-line structures
- ✅ Consistent spacing around operators
- ✅ No unnecessary parentheses
- ✅ Meaningful variable names

---

## 🚨 Troubleshooting

### Black and isort Conflict?
No! We use `profile = "black"` in isort config to ensure compatibility.

### Pre-commit Hook Fails?
```bash
# Update hooks to latest versions
pre-commit autoupdate

# Clear cache and retry
pre-commit clean
pre-commit run --all-files
```

### CI Fails Locally Passes?
```bash
# Ensure you're using the same Python version
python --version  # Should be 3.11+

# Reinstall dev dependencies
uv pip install -r requirements-dev.txt

# Run exact CI commands
black --check .
isort --check .
ruff check .
```

### Large Formatting Changes?
When Black/isort reformats many files:
```bash
# Create a dedicated "formatting" commit
black .
isort .
git add .
git commit -m "chore: apply Black and isort formatting"
```

---

## 📦 Files & Configuration

| File | Purpose |
|------|---------|
| [`pyproject.toml`](pyproject.toml) | Black, isort, Ruff configuration |
| [`.pre-commit-config.yaml`](.pre-commit-config.yaml) | Pre-commit hooks configuration |
| [`requirements-dev.txt`](requirements-dev.txt) | Development dependencies |
| [`.github/workflows/code-quality.yml`](.github/workflows/code-quality.yml) | CI/CD checks |

---

## 🎓 Learning Resources

- [Black Documentation](https://black.readthedocs.io/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pre-commit Documentation](https://pre-commit.com/)
- [PEP 8 Style Guide](https://pep8.org/)

---

## ✅ Summary

This project uses **production-grade automated formatting** with:

1. ✅ **Black** for consistent code style
2. ✅ **isort** for organized imports
3. ✅ **Ruff** for fast linting
4. ✅ **Pre-commit hooks** for automatic formatting
5. ✅ **GitHub Actions** for CI/CD enforcement

**No more style debates. Code is automatically formatted. Focus on logic, not formatting.**

---

## 🤝 Contributing

When contributing:
1. Install pre-commit hooks: `pre-commit install`
2. Format code before committing: `black . && isort .`
3. Fix linting issues: `ruff check --fix .`
4. Ensure CI passes before requesting review

**Questions?** Open an issue or ask the team.
