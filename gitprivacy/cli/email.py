import click
from collections import Counter
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
    ctx.obj.assert_repo()
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


@click.command('list-email')
@click.option('-a', '--all', 'check_all', is_flag=True,
              help="Include all local references.")
@click.option('-e', '--email-only', is_flag=True,
              help="Only consider actors' email address when counting contributions.")
@click.pass_context
def list_email(ctx: click.Context, check_all: bool, email_only: bool) -> None:
    """List all author and committer identities."""
    assertCommits(ctx)
    repo = ctx.obj.repo
    commits = repo.iter_commits("HEAD" if not check_all else "--all")
    authors: Counter[str] = Counter()
    committers: Counter[str] = Counter()
    if email_only:
        to_str = lambda a: a.email
    else:
        to_str = _actor_to_str
    for commit in commits:
        authors[to_str(commit.author)] += 1
        committers[to_str(commit.committer)] += 1
    total = authors + committers
    for actor in sorted(total):
        print(f"{actor} (total: {total[actor]}, author: {authors[actor]}, committer: {committers[actor]})")

def _actor_to_str(actor):
    return f"{actor.name} <{actor.email}>"
