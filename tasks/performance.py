from invoke.tasks import task

from .system import OperatingSystem, get_current_system


@task(default=True)
def profile(c):
    """Create performance profile and show it in timeline."""
    system = get_current_system()
    if system == OperatingSystem.LINUX:
        cmd = (
            rf"pyinstrument {c.project_slug}/__init__.py"
            r" | grep 'pyinstrument --load-prev'"
            r" | sed 's/\[options\]/-r html/'"
            r" | source /dev/stdin -f"
        )
        c.run(cmd, pty=True)
    else:
        raise ValueError(f"System {system} is not supported")
