# Git Workflow - Quick Reference

## ⚡ TL;DR - Never Fail Commits Again

```bash
# The only workflow you need:
git add -A                    # Stage EVERYTHING
git commit -m "your message"  # Commit (hooks auto-run)

# If hooks modify files, just commit again:
git add -A
git commit -m "your message"  # Will pass this time
```

That's it. **Always `git add -A` before `git commit`**. Problem solved forever.

---

## 🎯 The Golden Rule

**NEVER commit with unstaged changes.**

### ✅ Correct Workflow

```bash
# 1. Make changes
vim src/file.py

# 2. Format (optional, but recommended)
make format

# 3. Stage EVERYTHING
git add -A

# 4. Commit
git commit -m "add new feature"

# Done! ✅
```

### ❌ Wrong Workflow (WILL FAIL)

```bash
# 1. Make changes
vim src/file.py

# 2. Stage ONLY ONE FILE
git add src/file.py  # ❌ WRONG

# 3. Make more changes
vim src/other_file.py

# 4. Try to commit
git commit -m "add new feature"  # ❌ FAILS with:
# [WARNING] Stashed changes conflicted with hook auto-fixes...
```

**Why it fails:**
- Pre-commit runs Black/isort to format code
- But you have **unstaged changes** in `other_file.py`
- Formatting conflicts with unstaged changes
- Commit aborted

---

## 🚀 Quick Commands

### Before Every Commit

```bash
# Format everything first (recommended)
make format

# Then stage and commit
git add -A
git commit -m "your message"
```

### If Commit Fails

```bash
# Pre-commit modified files?
# Just add and commit again:
git add -A
git commit -m "your message"

# Will pass this time!
```

### Emergency: Skip Hooks (USE SPARINGLY)

```bash
# Critical hotfix, no time for formatting
git commit --no-verify -m "emergency: fix critical bug"

# Fix formatting immediately after:
make format
git add -A
git commit -m "chore: apply formatting"
```

---

## 🎨 Why We Have Pre-commit Hooks

Pre-commit hooks **automatically** enforce code quality:

1. ✅ **Black** - Formats code (100-char lines, consistent style)
2. ✅ **isort** - Sorts imports (STDLIB → THIRDPARTY → FIRSTPARTY)
3. ✅ **Ruff** - Lints and auto-fixes common issues
4. ✅ **Security** - Detects private keys, large files
5. ✅ **Validation** - Checks YAML/JSON/TOML syntax

**Result:** Every commit is production-ready. No manual work.

---

## 🔧 Makefile Shortcuts

We have shortcuts to make life easier:

```bash
make format         # Format all code (Black + isort + Ruff)
make format-check   # Check if code is formatted (CI mode)
make lint           # Run linters
make quality        # Run all checks
make pre-commit     # Run all hooks manually
```

**Recommended workflow:**

```bash
# Before committing:
make format    # Auto-format everything
git add -A     # Stage everything
git commit     # Commit (will pass!)
```

---

## 📊 What Happens on Each Commit

```bash
$ git commit -m "add new feature"

Running pre-commit hooks...
  ✅ Black formatting
  ✅ isort import sorting
  ✅ Ruff linting
  ✅ Trailing whitespace removal
  ✅ YAML validation
  ✅ JSON validation
  ✅ TOML validation
  ✅ Large file detection
  ✅ Private key detection
  ✅ Merge conflict detection
  ✅ Python syntax validation

All checks passed! ✅
[main abc1234] add new feature
 5 files changed, 100 insertions(+), 20 deletions(-)
```

---

## 🆘 Troubleshooting

### Problem: "Stashed changes conflicted with hook auto-fixes"

```bash
# You have unstaged changes
$ git status
Changes to be committed:
  modified:   file1.py

Changes not staged for commit:
  modified:   file2.py  # ← This is the problem

# Solution:
$ git add -A    # Stage everything
$ git commit    # Try again
```

### Problem: "Hook modified files"

```bash
# Pre-commit formatted your code
$ git commit -m "add feature"
black....................................Failed
- files were modified by this hook

# Solution:
$ git add -A    # Add formatted files
$ git commit -m "add feature"  # Commit again (will pass)
```

### Problem: Too many files modified

```bash
# First time running Black on large codebase
$ git commit
black....................................Failed
- 58 files reformatted

# Solution:
$ make format   # Format everything
$ git add -A    # Stage all formatted files
$ git commit -m "chore: apply Black formatting"

# From now on, commits will be smooth
```

---

## 💡 Pro Tips

### Tip 1: IDE Auto-format on Save

**VS Code:** Add to `.vscode/settings.json`:
```json
{
  "editor.formatOnSave": true,
  "python.formatting.provider": "black"
}
```

**Result:** Files auto-format on save. No commit conflicts!

### Tip 2: Always Use `make format`

```bash
# Before committing, always run:
make format    # Formats everything
git add -A     # Stage everything
git commit     # Commit (will pass)
```

### Tip 3: Check Before Committing

```bash
# Check if code is formatted:
make format-check

# If it passes, you're good to commit:
git add -A
git commit
```

### Tip 4: Use Git Aliases

Add to `~/.gitconfig`:

```ini
[alias]
  ac = "!f() { git add -A && git commit -m \"$1\"; }; f"
  fmt = "!make format && git add -A"
```

**Usage:**
```bash
git fmt                        # Format and stage everything
git ac "add new feature"       # Stage all and commit
```

---

## ✅ Summary

**The only thing you need to remember:**

```bash
git add -A          # Stage EVERYTHING
git commit          # Commit (hooks will pass)
```

**That's it. Problem solved forever.**

---

## 📚 Further Reading

- [CONTRIBUTING.md](.github/CONTRIBUTING.md) - Full contributing guide
- [FORMATTING.md](FORMATTING.md) - Complete formatting guide
- [Makefile](Makefile) - All available commands

---

**Remember:** Pre-commit hooks are here to help, not to annoy. They ensure every commit is production-ready! 🚀
