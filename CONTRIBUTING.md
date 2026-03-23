# Contributing to Caffeinator

Thanks for your interest in contributing! Caffeinator is a small utility and contributions of all sizes are welcome — bug fixes, new features, docs improvements, or just reporting issues.

## Getting Started

1. **Fork and clone** the repo:

   ```bash
   git clone https://github.com/<your-username>/Caffeinator.git
   cd Caffeinator
   ```

2. **Install in development mode**:

   ```bash
   pip install -e ".[dev]"
   ```

3. **Run the app** to make sure everything works:

   ```bash
   procawake
   ```

## Development Workflow

1. Create a feature branch from `main`:

   ```bash
   git checkout -b my-feature
   ```

2. Make your changes. Keep commits focused — one logical change per commit.

3. Run the checks before pushing:

   ```bash
   # Lint
   ruff check src/

   # Type check
   mypy src/procawake/ --ignore-missing-imports

   # Tests
   pytest tests/ -v
   ```

4. Push your branch and open a Pull Request against `main`.

## Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting. The CI pipeline enforces this.
- Type hints are encouraged. We run `mypy` in CI.
- Keep functions short and well-named. If a comment explains *what* the code does, the code probably needs renaming.

## Testing

- Tests live in `tests/` and use `pytest`.
- If you're adding a new feature, add tests for it.
- If you're fixing a bug, add a test that would have caught it.

## Pull Request Expectations

- **One thing per PR.** A bug fix and a new feature should be separate PRs.
- **Describe the "why."** The PR description should explain the motivation, not just list files changed.
- **Keep it small.** Smaller PRs get reviewed faster and merged sooner.
- **Tests must pass.** CI runs lint, type checking, and tests on Python 3.11 through 3.13.

## Reporting Bugs

Open an issue using the **Bug Report** template. Include your Windows version, how you installed Caffeinator (exe vs pip vs source), and any relevant logs from `%APPDATA%\procawake\`.

## Suggesting Features

Open an issue using the **Feature Request** template. Describe the problem you're trying to solve — sometimes there's already a way to do it with existing config options.

## Questions?

Open a discussion or issue. There are no dumb questions.
