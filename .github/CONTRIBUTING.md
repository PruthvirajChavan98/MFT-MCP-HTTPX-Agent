# Contributing Guidelines - Production Workflow

## Git Workflow (IMPORTANT)

### The Problem You Just Hit

If you try to commit with **unstaged changes**, pre-commit hooks will fail with:
```
[WARNING] Stashed changes conflicted with hook auto-fixes... Rolling back fixes...
```

This happens because:
1. Pre-commit runs Black/isort to format your code
2. But you have unstaged changes that conflict with the formatting
3. Git can't apply both changes at once

### ✅ Permanent Solution: Proper Workflow

**ALWAYS follow this order:**

```bash
# 1. Make your changes
vim src/agent_service/api/endpoints/agent_stream.py

# 2. Format code BEFORE staging (optional but recommended)
make format

# 3. Stage ALL changes (including formatting)
git add -A

# 4. Commit (pre-commit hooks will run automatically)
git commit -m "your message"

# If hooks modify files, they're already staged, so commit will succeed
```

### ❌ What NOT to Do

```bash
# DON'T do this:
git add src/file1.py          # Stage one file
# ... make more changes ...
git commit -m "message"       # Commit with unstaged changes - WILL FAIL
```

### 🎯 Best Practices

#### Option 1: Pre-format Everything (Recommended)

```bash
# Before committing, always run:
make format          # Formats all code
git add -A          # Stage everything
git commit -m "..."  # Commit (hooks will pass)
```

#### Option 2: Let Pre-commit Handle It

```bash
# Make changes
vim src/file.py

# Stage everything (even if not formatted)
git add -A

# Commit (pre-commit will format and you'll commit again)
git commit -m "..."

# If hooks modified files, add and commit again:
git add -A
git commit -m "..." --no-verify  # OR just commit again normally
```

#### Option 3: Use Makefile Shortcuts

```bash
# We've added helpful shortcuts to Makefile:

make quality        # Check formatting without changing files
make format         # Format all files
make pre-commit     # Run all hooks manually
```

### 🚨 Emergency: Skip Hooks (USE SPARINGLY)

**Only in emergencies** (e.g., critical hotfix):

```bash
git commit --no-verify -m "emergency: critical hotfix"
```

**But then fix formatting immediately after:**

```bash
make format
git add -A
git commit -m "chore: apply formatting to previous commit"
```

---

## Pre-commit Hooks

Our pre-commit hooks run automatically on every commit:

1. ✅ **Black** - Code formatting
2. ✅ **isort** - Import sorting
3. ✅ **Ruff** - Linting + auto-fixes
4. ✅ **Trailing whitespace** - Cleanup
5. ✅ **YAML/JSON/TOML** - Validation
6. ✅ **Large files** - Detection
7. ✅ **Private keys** - Detection
8. ✅ **Merge conflicts** - Detection
9. ✅ **Python AST** - Syntax validation

### What Happens on Each Commit

```bash
$ git commit -m "add new feature"

# Pre-commit runs automatically:
Running black................................ ✅ Passed
Running isort................................ ✅ Passed
Running ruff................................. ✅ Passed
# ... (9 total checks)

# If any check modifies files:
Running black................................ ❌ Failed (files modified)

# Just stage and commit again:
$ git add -A
$ git commit -m "add new feature"  # Now it will pass
```

---

## Makefile Commands

We have production-grade shortcuts in `Makefile`:

### Development

```bash
make help           # Show all commands
make install        # Install production dependencies
make install-dev    # Install dev dependencies + pre-commit hooks
make dev            # Run development server
```

### Code Quality

```bash
make format         # Format code with Black, isort, Ruff
make format-check   # Check formatting (CI mode)
make lint           # Run Ruff linter
make quality        # Run all checks (format-check + lint)
make pre-commit     # Run all pre-commit hooks manually
```

### Docker

```bash
make docker-build   # Build Docker images
make docker-up      # Start services
make docker-down    # Stop services
make docker-logs    # View logs
```

### Cleanup

```bash
make clean          # Remove caches and build artifacts
```

---

## IDE Integration (Recommended)

### VS Code

Add to `.vscode/settings.json`:

```json
{
  "python.formatting.provider": "black",
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

**Result:** Files auto-format on save, no commit issues!

### PyCharm

1. Install Black plugin
2. Settings → Tools → Black → Enable
3. Settings → Actions on Save → Reformat code

---

## Common Issues

### Issue: "Stashed changes conflicted with hook auto-fixes"

**Cause:** You have unstaged changes when committing

**Fix:**
```bash
git add -A          # Stage everything
git commit -m "..."  # Commit again
```

### Issue: "Hook modified files"

**Cause:** Black/isort formatted your code during pre-commit

**Fix:**
```bash
git add -A          # Add the formatted files
git commit -m "..."  # Commit again (will pass now)
```

### Issue: "Too many files modified by hooks"

**Cause:** First time running Black on unformatted codebase

**Fix:**
```bash
# Format everything once:
make format
git add -A
git commit -m "chore: apply Black formatting to entire codebase"

# From now on, commits will be smooth
```

---

## Summary: The Golden Rule

**🎯 Always stage ALL changes before committing:**

```bash
# ✅ CORRECT WORKFLOW
make format    # Optional: format first
git add -A     # Stage everything
git commit     # Commit (hooks will pass)

# ❌ WRONG WORKFLOW
git add file1.py    # Stage one file
# ... make more changes ...
git commit          # FAILS: unstaged changes conflict with hooks
```

**Remember:** Pre-commit hooks are your friends, not enemies. They ensure code quality automatically!

---

## Questions?

- Read [`FORMATTING.md`](../FORMATTING.md) for detailed formatting guide
- Run `make help` to see all available commands
- Check pre-commit config: [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)
