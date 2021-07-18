import click
from typing import List, Tuple

from .utils import assertCommits


class EmailRedactParamType(click.ParamType):
    name = 'emailredact'

    def convert(self, value, param, ctx) -> Tuple[str, str, str]:
        if ":" in value:
            try:
                old, new = value.split(":", maxsplit=1)
                name = ""
                if ":" in new:
                    new, name = new.split(":")
                return (old, new, name)
            except ValueError:
                self.fail(
                    f'{value} is not in the format '
                    'old-email[:new-email[:new-name]]',
                    param, ctx,
                )
        return (value, "", "")


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
def redact_email(ctx: click.Context,
                 addresses: List[Tuple[str, str, str]],
                 replacement: str,
                 use_ghnoreply: bool) -> None:
    """Redact email addresses from existing commits."""
    if not addresses:
        return  # nothing to do

    assertCommits(ctx)
    repo = ctx.obj.repo

    env_cmd = ""
    with click.progressbar(addresses,
                           label="Redacting emails") as bar:
        for old, new, name in bar:
            if new and use_ghnoreply:
                new = GHNOREPLY.format(username=new)
            if not new:
                new = replacement
            env_cmd += get_env_cmd("COMMITTER", old, new, name)
            env_cmd += get_env_cmd("AUTHOR", old, new, name)
    filter_cmd = ["git", "filter-branch", "-f",
                  "--env-filter", env_cmd,
                  "--",
                  "HEAD"]
    repo.git.execute(command=filter_cmd)


def get_env_cmd(role: str, old: str, new: str, name: str) -> str:
    name_env = f'GIT_{role}_NAME="{name}"'
    return (
        f'if test "$GIT_{role}_EMAIL" = "{old}"; then '
        f'export GIT_{role}_EMAIL="{new}" '
        f'{name_env if name else ""}; '
        'fi; '
    )
