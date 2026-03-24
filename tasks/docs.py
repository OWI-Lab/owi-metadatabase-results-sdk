"""Documentation tasks."""

from invoke.tasks import task


@task
def build(c):
    """Build Zensical docs."""
    c.run("zensical build --clean", pty=True)


@task
def serve(c):
    """Serve Zensical with hot reload."""
    c.run("zensical serve", pty=True)


@task
def deploy_version(c, version, alias="latest"):
    """Build documentation for deployment.

    Version labels are retained for task compatibility but are not used by the
    GitHub Pages artifact deployment flow.
    """
    c.run("zensical build --clean", pty=True)


@task
def set_default_version(c, version):
    """Build documentation for deployment.

    Default-version selection is not used with the GitHub Pages artifact
    deployment flow.
    """
    c.run("zensical build --clean", pty=True)


@task(post=[build], default=True)
def all(c):
    """Build docs."""
