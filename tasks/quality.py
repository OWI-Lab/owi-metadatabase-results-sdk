"""Quality assessment tasks. Run all quality checks with `inv qa`.
The quality checks are:
- `pre-commit` hooks: Run the pre-commit hooks defined in the
  `.pre-commit-config.yaml` file. By default, all hooks will be run, but you
  can specify a subset of hooks to run by providing their names as arguments to
  the `hooks` parameter. For example, to run only the `black` and `isort` hooks,
  you can use the command `inv qa --hooks black,isort`.
"""

from invoke.tasks import task

from .colors import Color, colorize
from .system import PTY


@task(
    default=True,
    help={"hooks": "Specify a single hook or set of hooks to run."},
)
def pre_commit(c_r, hooks: str = "", files: str = "--all-files"):
    """Run pre-commit hooks."""
    tmp_str = colorize("\nRunning pre-commit hooks...", color=Color.HEADER, bold=True)
    print(f"{tmp_str}")
    _command = f"pre-commit run {hooks} {files}"
    print(f"\n{colorize('>>> ' + _command, color=Color.OKBLUE)}\n")
    result = c_r.run(
        _command,
        pty=PTY,
        warn=True,
    )
    if "failed" in result.stdout.lower():
        print(colorize("\nPre-commit hooks completed with errors.\n", color=Color.ERROR))
    else:
        print(colorize("\nPre-commit hooks completed.\n", color=Color.OKGREEN))
