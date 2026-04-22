# Contributing to SDC Governance

Thank you for your interest in contributing to SDC Governance.

## Development Setup

```bash
git clone https://github.com/SemanticDataCharter/SDC_Governance.git
cd SDC_Governance
pip install -e ".[dev,django]"
pytest tests/ -v
```

## Running Tests

```bash
pytest tests/ -v --tb=short
```

## Code Style

- Follow PEP 8
- Use type hints for all public functions
- Docstrings for all modules, classes, and public functions
- Reference W3C standard URIs in docstrings where applicable

## Pull Requests

1. Fork the repository
2. Create a feature branch from `main`
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request with a clear description

## Architecture

See [PLANNING.md](PLANNING.md) for the architecture overview and implementation roadmap.

The core modules in `src/sdc_governance/` must remain framework-agnostic (no Django imports). Django-specific code belongs in `src/sdc_governance/django/`.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
