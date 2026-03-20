"""Test tasks."""

from invoke import task


@task
def run(c, test=None, pytest_args="-v"):
    """Run the test suite."""
    test_command = f" {test}" if test else ""
    command = (
        "pytest "
        f"{pytest_args} "
        "--cov=src/owi/metadatabase/results "
        "--cov-report=term-missing:skip-covered "
        "--doctest-modules"
        f"{test_command}"
    )
    c.run(command, pty=True)


@task(default=True)
def all(c, test=None, pytest_args="-v"):
    """Run tests."""
    run(c, test, pytest_args)
