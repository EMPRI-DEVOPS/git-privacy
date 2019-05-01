import click


def assertCommits(ctx: click.Context) -> None:
    """Assert that the current ref has commits."""
    head = ctx.obj.repo.head
    if not head.is_valid():
        click.echo(
            f"fatal: your current branch '{head.ref.name}' "
            "does not have any commits yet",
            err=True
        )
        ctx.exit(128)  # Same exit-code as used by git
