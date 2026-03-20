"""Quality tasks."""

from invoke import task


@task
def format(c):
    """Run ruff formatter."""
    c.run("ruff format src tests", pty=True)


@task
def lint(c):
    """Run ruff linter."""
    c.run("ruff check src tests", pty=True)


@task
def ty_check(c):
    """Run ty."""
    c.run("ty check src/owi tests", warn=True, pty=True)


@task(post=[format, lint, ty_check], default=True)
def all(c):
    """Run all quality checks."""
