# Release Process

## Versioning

sdcgovernance follows the SDC ecosystem version scheme:

- **4.0.0a1-a7** - Alpha releases (one per phase)
- **4.0.0** - GA release (all phases complete)
- **4.x.y** - Patch releases for the sdc4 RM generation

The major version (4) tracks the SDC Reference Model generation.

## Version Location

Version is set in two places:
- `src/sdcgovernance/__init__.py` - `__version__ = "4.0.0"`
- `pyproject.toml` - `version = "4.0.0"`

Both must match.

## PyPI Publishing

Automated via GitHub Actions on tag push:

```bash
git tag v4.0.0
git push origin v4.0.0
```

The `.github/workflows/release.yml` workflow:
1. Runs full test suite
2. Builds sdist and wheel
3. Publishes to PyPI

## CI

`.github/workflows/test.yml` runs on every push and PR:
- Python 3.10, 3.11, 3.12
- Full test suite with pytest
- All tests must pass

## Pre-Release Checklist

1. All tests pass: `python -m pytest tests/ -v`
2. Version updated in `__init__.py` and `pyproject.toml`
3. README.md reflects current functionality
4. No placeholder tests remaining for released phases
5. Documentation complete for all released features
