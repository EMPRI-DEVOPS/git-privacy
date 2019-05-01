import click
from typing import List

from .utils import assertCommits


class EmailRedactParamType(click.ParamType):
    name = 'emailredact'

    def convert(self, value, param, ctx):
        if ":" in value:
            try:
                old, new = value.split(":")
                return (old, new)
            except ValueError:
                self.fail('%s is not in the format old-email[:new-email]' % value, param, ctx)
        else:
            return (value, "")


EMAIL_REDACT = EmailRedactParamType()
GHNOREPLY = "{username}@users.noreply.github.com"


@click.command('redact-email')
@click.argument('addresses', nargs=-1, type=EMAIL_REDACT)
@click.option('-r', '--replacement', type=str,
              default="noreply@gitprivacy.invalid",
              help="Email address used as replacement.")
@click.option('-g', '--use-github-noreply', 'use_ghnoreply', is_flag=True,
              help="Interpret custom replacements as GitHub usernames"
                   " and construct noreply addresses.")
@click.pass_context
def redact_email(ctx: click.Context, addresses: List[str], replacement: str,
                 use_ghnoreply: bool) -> None:
    """Redact email addresses from existing commits."""
    if not addresses:
        return  # nothing to do

    assertCommits(ctx)
    repo = ctx.obj.repo

    env_cmd = ""
    with click.progressbar(addresses,
                           label="Redacting emails") as bar:
        for old, new in bar:
            if new and use_ghnoreply:
                new = GHNOREPLY.format(username=new)
            if not new:
                new = replacement
            env_cmd += (
                f"if test \"$GIT_COMMITTER_EMAIL\" = \"{old}\"; then "
                f"export GIT_COMMITTER_EMAIL=\"{new}\"; "
                "fi; "
                f"if test \"$GIT_AUTHOR_EMAIL\" = \"{old}\"; then "
                f"export GIT_AUTHOR_EMAIL=\"{new}\"; "
                "fi; "
            )
    filter_cmd = ["git", "filter-branch", "-f",
                  "--env-filter", env_cmd,
                  "--",
                  "HEAD"]
    repo.git.execute(command=filter_cmd)

