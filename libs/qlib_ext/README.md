# qlib_ext

## Fork Instructions

This directory is reserved for the qlib ext fork.

### To initialize:
```bash
git clone <upstream_url> qlib_ext
cd qlib_ext
git remote rename origin upstream
git checkout -b upstream/main upstream/main
```

### To sync upstream changes:
```bash
cd qlib_ext
git fetch upstream
git rebase upstream/main
```

### Rules:
- **NEVER** modify upstream core logic directly
- All extensions go in `adapters/`, `risk/`, `replay/` directories
- Keep `upstream/main` as tracking branch
- Monthly sync recommended
