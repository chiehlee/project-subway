# Project Subway

Python requirement: 3.13.x (pyproject pins to >=3.13,<3.14).

## Setup
1. Install Python 3.13 (e.g., with pyenv: `pyenv install 3.13.6`).
2. Point Poetry at that interpreter: `poetry env use $(pyenv which python)`.
3. Install deps: `poetry install`.

## Usage
Add dependencies with `poetry add <package>` and start coding inside `project_subway/`.

## Poetry environments
- List envs: `poetry env list` (names look like `project-subway-<hash>-py3.13`).
- Current 3.13 env: `/Users/chieh/Library/Caches/pypoetry/virtualenvs/project-subway-1s6GqF-t-py3.13` (auto-used by `poetry run ...`).
- Test env created with Python 3.12: `poetry env use python3.12`. It exists but doesn’t satisfy the >=3.13,<3.14 constraint; switch back with `poetry env use python3.13`.
- Inspect the active env: `poetry env info`.