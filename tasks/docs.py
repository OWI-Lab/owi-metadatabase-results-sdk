"""Documentation tasks."""

from invoke import task


@task
def build(c):
    """Build MkDocs docs."""
    c.run("mkdocs build --strict", pty=True)


@task
def serve(c):
    """Serve MkDocs with hot reload."""
    c.run("mkdocs serve", pty=True)


@task
def deploy_version(c, version, alias="latest"):
    """Deploy versioned documentation with mike."""
    if alias == version:
        c.run(f"mike deploy --push {version}", pty=True)
    else:
        c.run(
            f"mike deploy --push --update-aliases {version} {alias}",
            pty=True,
        )


@task
def set_default_version(c, version):
    """Set the default documentation version with mike."""
    c.run(f"mike set-default --push {version}", pty=True)


@task(post=[build], default=True)
def all(c):
    """Build docs."""
