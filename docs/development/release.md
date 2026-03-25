# Release Process

## High-Level Steps

1. Add at most one release label to the pull request targeting `main`:
   - `release:major`
   - `release:minor`
   - `release:patch`
2. Open or update the PR and let the **Release Preview** workflow compute the
   next version.
3. Merge the PR into `main`.
4. The **Release On Merge** workflow validates, bumps version files, creates the
   `vX.Y.Z` tag, and pushes it.
5. The tag-triggered workflow deploys docs and publishes to PyPI.

If no release label is present, the workflow defaults to a **patch** release.

## Workflow Details

- **Release Preview** — runs on PRs to `main`, resolves the release label, and
  previews the target version.
- **Release On Merge** — runs after merge, executes
  `uv sync --dev --locked`, `uv run invoke test.run`,
  `uv run invoke qa`, and `uv run invoke docs.build` before tagging.
- **Tag push** (`v*`) — deploys docs, publishes to PyPI, creates a GitHub
  release.

## Manual Publish Fallback

1. Open the **Publish Python package** workflow in GitHub Actions.
2. Run it against `main` with the confirmation input enabled.
3. The workflow builds and publishes from the current `main` state.

!!! warning
    The manual path does **not** bump the version, create a tag, deploy
    docs, or create a GitHub release. If the version already exists on
    PyPI, the publish step fails as expected.

## Label Rules

- Use exactly **one** release label per pull request.
- If more than one label is applied, the preview workflow fails.
