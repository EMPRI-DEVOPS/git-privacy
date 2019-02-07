#!/usr/bin/python3
"""
git privacy
"""
import click
from datetime import datetime, timezone
import os
import re
import stat
import sys
from typing import Optional, Tuple
import configparser
import git
from . import timestamp
from . import crypto


MSG_TAG = "GitPrivacy: "


class GitPrivacyConfig(object):
    SECTION = "privacy"
    def __init__(self, gitdir: str) -> None:
        self.gitdir = gitdir
        try:
            self.repo = git.Repo(gitdir)
        except git.InvalidGitRepositoryError as e:
            raise click.UsageError("not a git repository: '{}'".format(e))
        with self.repo.config_reader() as config:
            self.mode = config.get_value(self.SECTION, 'mode', 'reduce')
            self.pattern = config.get_value(self.SECTION, 'pattern', '')
            self.limit = config.get_value(self.SECTION, 'limit', '')
            self.password = config.get_value(self.SECTION, 'password', '')
            self.salt = config.get_value(self.SECTION, 'salt', '')
            self.ignoreTimezone = bool(config.get_value(self.SECTION,
                                                        'ignoreTimezone', False))

    def get_crypto(self) -> Optional[crypto.Crypto]:
        if not self.password:
            return None
        elif self.password and not self.salt:
            self.salt = crypto.generate_salt()
            self.write_config(salt=self.salt)
        return crypto.Crypto(self.salt, str(self.password))

    def get_timestamp(self) -> timestamp.TimeStamp:
        if self.mode == "reduce" and self.pattern == '':
            raise click.UsageError(click.wrap_text(
                "Missing pattern configuration. Set a reduction pattern using\n"
                "\n"
                f"    git config {self.SECTION}.pattern <pattern>\n"
                "\n"
                "The pattern is a comma separated list that may contain the "
                "following time unit identifiers: "
                "M: month, d: day, h: hour, m: minute, s: second.",
                preserve_paragraphs=True))
        return timestamp.TimeStamp(self.pattern, self.limit, self.mode)




    def write_config(self, **kwargs):
        """Write config"""
        with self.repo.config_writer(config_level='repository') as writer:
            for key, value in kwargs.items():
                writer.set_value("privacy", key, value)


@click.group()
@click.option('--gitdir', default=os.getcwd,
              type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
              help="Path to your Git repsitory.")
@click.pass_context
def cli(ctx, gitdir):
    ctx.obj = GitPrivacyConfig(gitdir)


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


@cli.command('init')
@click.option('-c', '--enable-check', is_flag=True,
              help="Enable execution of 'check' before committing.")
@click.pass_context
def do_init(ctx, enable_check):
    """Init git-privacy for this repository."""
    repo = ctx.obj.repo
    copy_hook(repo, "post-commit")
    if enable_check:
        copy_hook(repo, "pre-commit")

def copy_hook(repo: git.Repo, hook: str) -> None:
    from pkg_resources import resource_stream, resource_string
    import shutil
    hook_fn = os.path.join(repo.git_dir, "hooks", hook)
    try:
        dst = open(hook_fn, "xb")
    except FileExistsError as e:
        hook_txt = resource_string('gitprivacy.resources.hooks', hook).decode()
        with open(hook_fn, "r") as f:
            if f.read() == hook_txt:
                print(f"{hook} hook is already installed.")
                return
        print(f"A Git hook already exists at {hook_fn}", file=sys.stderr)
        print("\nRemove hook and rerun or add the following to the existing "
              f"hook:\n\n{hook_txt}")
        return
    else:
        with resource_stream('gitprivacy.resources.hooks', hook) as src, dst:
            shutil.copyfileobj(src, dst)
            os.chmod(dst.fileno(), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                     stat.S_IROTH | stat.S_IXOTH) # mode 755
            print("Installed {} hook".format(hook))


@cli.command('log')
@click.pass_context
def do_log(ctx):
    """Display a git-log-like history."""
    assertCommits(ctx)
    tm = timestamp.TimeStamp()
    repo = ctx.obj.repo
    crypto = ctx.obj.get_crypto()
    commit_list = list(repo.iter_commits())
    buf = list()
    for commit in commit_list:
        buf.append(click.style(f"commit {commit.hexsha}", fg='yellow'))
        buf.append(f"Author:\t\t{commit.author.name} <{commit.author.email}>")
        orig_dates = _decrypt_from_msg(crypto, commit.message)
        if orig_dates is not None:
            a_date, c_date = orig_dates
            buf.append(click.style(f"Date:\t\t{tm.to_string(commit.authored_datetime)}", fg='red'))
            buf.append(click.style(f"RealDate:\t{tm.to_string(a_date)}", fg='green'))
        else:
            buf.append(f"Date:\t\t{tm.to_string(commit.authored_datetime)}")
        buf.append(os.linesep + f"    {commit.message}")
    click.echo_via_pager(os.linesep.join(buf))


def _extract_enc_dates(msg: str) -> Optional[str]:
    """Extract encrypted dates from the commit message"""
    for line in msg.splitlines():
        match = re.search(fr'^{MSG_TAG}(\S+)', line)
        if match:
            return match.group(1)
    return None


def _encrypt_for_msg(crypto, a_date: datetime, c_date: datetime) -> str:
    plain = ";".join(d.strftime("%s %z") for d in (a_date, c_date))
    return crypto.encrypt(plain)


def _decrypt_from_msg(crypto, message: str) -> Optional[Tuple[datetime, datetime]]:
    enc_dates = _extract_enc_dates(message)
    if crypto is None or enc_dates is None:
        return None
    plain_dates = crypto.decrypt(enc_dates)
    if plain_dates is None:
        return None
    a_date, c_date = [_strptime(d) for d in plain_dates.split(";")]
    return a_date, c_date

def _strptime(string: str):
    seconds, tz = string.split()
    return datetime.fromtimestamp(
        int(seconds),
        datetime.strptime(tz, "%z").tzinfo,
    )


@cli.command('redate')
@click.argument('startpoint', required=False, default='')
@click.option('--only-head', is_flag=True,
              help="Redate only the current head.")
@click.pass_context
def do_redate(ctx, startpoint, only_head):
    """Redact timestamps of existing commits."""
    assertCommits(ctx)
    repo = ctx.obj.repo
    time_manager = ctx.obj.get_timestamp()
    crypto = ctx.obj.get_crypto()

    if only_head:
        startpoint = "HEAD~1"
    single_commit = next(repo.head.commit.iter_parents(), None) is None
    try:
        if startpoint and not single_commit:
            rev = f"{startpoint}..HEAD"
        else:
            rev = "HEAD"
            # Enforce validity of user-defined startpoint
            # to give proper feedback
            if not only_head:
                repo.commit(startpoint)
        commits = list(repo.iter_commits(rev))
    except (git.GitCommandError, git.BadName):
        click.echo(f"bad revision '{startpoint}'", err=True)
        ctx.exit(128)
    if len(commits) == 0:
        click.echo(f"Found nothing to redate for '{rev}'", err=True)
        ctx.exit(128)
    env_cmd = ""
    msg_cmd = ""
    with click.progressbar(commits,
                           label="Redating commits") as bar:
        for commit in bar:
            a_redacted = time_manager.reduce(commit.authored_datetime)
            c_redacted = time_manager.reduce(commit.committed_datetime)
            env_cmd += (
                f"if test \"$GIT_COMMIT\" = \"{commit.hexsha}\"; then "
                f"export GIT_AUTHOR_DATE=\"{a_redacted}\"; "
                f"export GIT_COMMITTER_DATE=\"{c_redacted}\"; fi; "
            )
            # Only add encrypted dates to commit message if none are present
            # already. Keep the original ones else.
            keep_msg = any([line.startswith(MSG_TAG)
                            for line in commit.message.splitlines()])
            if keep_msg or crypto is None:
                append_cmd = ""
            else:
                enc_dates = _encrypt_for_msg(crypto, commit.authored_datetime,
                                             commit.committed_datetime)
                append_cmd = f"&& echo && echo \"{MSG_TAG}{enc_dates}\""
            msg_cmd += (
                f"if test \"$GIT_COMMIT\" = \"{commit.hexsha}\"; then "
                f"cat {append_cmd}; fi; "
            )
    filter_cmd = ["git", "filter-branch", "-f",
                  "--env-filter", env_cmd,
                  "--msg-filter", msg_cmd,
                  "--",
                  rev]
    repo.git.execute(command=filter_cmd)


@cli.command('check')
@click.pass_context
def do_check(ctx):
    """Check for timezone change since last commit."""
    repo = ctx.obj.repo
    if not repo.head.is_valid():
        return  # no previous commits
    with repo.config_reader() as cr:
        user_email = cr.get_value("user", "email", "")
    if not user_email:
        click.echo("No user email set.", err=True)
        ctx.exit(128)
    user_commits = repo.iter_commits(
        author=f"<{user_email}>",
        committer=f"<{user_email}>",
    )
    last_commit = next(user_commits, None)
    if last_commit is None:
        return  # no previous commits by this user
    current_tz = datetime.now(timezone.utc).astimezone().tzinfo
    if last_commit.author.email == user_email:
        last_tz = last_commit.authored_datetime.tzinfo
    elif last_commit.committer.email == user_email:
        last_tz = last_commit.committed_datetime.tzinfo
    else:
        raise RuntimeError("Unexpected commit.")
    dummy_date = datetime.now()
    if last_tz.utcoffset(dummy_date) != current_tz.utcoffset(dummy_date):
        click.echo("Warning: Your timezone has changed.", err=True)
        if not ctx.obj.ignoreTimezone:
            ctx.exit(2)
