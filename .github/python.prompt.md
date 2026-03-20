---
agent: agent
description: This prompt provides guidelines for generating or editing Python code.
model: GPT-5.3-Codex (copilot)
tools: [vscode, execute, read, agent, edit, search, web, 'daisyui/*', 'pylance-mcp-server/*', ms-azuretools.vscode-containers/containerToolsConfig, ms-python.python/getPythonEnvironmentInfo, ms-python.python/getPythonExecutableCommand, ms-python.python/installPythonPackage, ms-python.python/configurePythonEnvironment, todo]
---

# Python Code Generation and Editing Guidelines

When generating or editing Python code, adhere to the following guidelines to ensure consistency and quality:

- Follow PEP 8 style guidelines.
- Use type hints for function signatures and variable declarations.
- Prefer f-strings for string formatting, besides when logging, where `%` formatting is preferred.
- Use `pathlib` for file and path operations instead of `os.path`.
- Use list comprehensions and generator expressions where appropriate.
- Handle exceptions using try-except blocks, and avoid bare except clauses.
- Write unit tests using `unittest` or `pytest` frameworks.
- If writing a package, test files naming must mirror the source files, e.g., `module.py` -> `test_module.py`.
- Use `uv` and the python environment installed at <current-working-folder>/.venv/bin/python for dependency management, testing, and execution.
- Run pytest via `uv` to ensure tests are executed in the correct environment.
- Before running tests, ensure that any necessary python package for testing (found in pyproject.toml) is installed, test databases or fixtures are set up, and that the test environment variables are configured.
- Use `logging` module for logging instead of print statements.
- When working with data, prefer using `pandas`, `numpy`, or `polars` for data manipulation
- Write detailed NumPy-style docstrings with doctest
- Keep 80 character maximum line length
- Edit only the code that is necessary to complete the request.
- Edit the code directly in the files, do not write snippets or partial code in the response.
- Run `uv` tests (if available) after making code changes to ensure correctness.
- If running in docker, rebuild the docker image and restart the container after code changes.
