#!/usr/bin/python3
"""
git privacy
"""
import click
import git  # type: ignore
import os
import stat
import sys

from datetime import datetime, timezone
from typing import Optional, TextIO, Tuple


from . import GIT_SUBDIR
from . import crypto as crypt
from .cli import email
from .cli import keys
from .cli.utils import assertCommits
from .dateredacter import DateRedacter, ResolutionDateRedacter
from .encoder import (
    Encoder, BasicEncoder, MessageEmbeddingEncoder,
    Decoder, BasicDecoder, MessageEmbeddingDecoder,
)
from .rewriter import AmendRewriter, FilterRepoRewriter
from .utils import fmtdate


class GitPrivacyConfig(object):
    SECTION = "privacy"

    def __init__(self, gitdir: str) -> None:
        self.gitdir = gitdir
        try:
            self.repo = git.Repo(gitdir, search_parent_directories=True)
        except git.InvalidGitRepositoryError as e:
            raise click.UsageError("not a git repository: '{}'".format(e))
        with self.repo.config_reader() as config:
            self.mode = config.get_value(self.SECTION, 'mode', 'reduce')
            self.pattern = config.get_value(self.SECTION, 'pattern', '')
            self.limit = config.get_value(self.SECTION, 'limit', '')
            self.password = config.get_value(self.SECTION, 'password', '')
            self.salt = config.get_value(self.SECTION, 'salt', '')
            self.ignoreTimezone = bool(config.get_value(
                self.SECTION, 'ignoreTimezone', True))
            self.replace = bool(config.get_value(
                self.SECTION, 'replacements', False))

    def get_crypto(self) -> Optional[crypt.EncryptionProvider]:
        if self.password:
            if not self.salt:
                self.salt = crypt.PasswordSecretBox.generate_salt()
                self.write_config(salt=self.salt)
            return crypt.PasswordSecretBox(self.salt, str(self.password))
        key = keys.get_active_key(self.repo.git_dir)
        archive = keys.get_archived_keys(self.repo.git_dir)
        if key:
            return crypt.MultiSecretBox(key=key, keyarchive=archive)
        return None

    def get_decrypto(self) -> Optional[crypt.DecryptionProvider]:
        # try to get a EncryptionProvider, then fallback to DecryptionProvider
        crypto = self.get_crypto()
        if crypto:
            return crypto
        archive = keys.get_archived_keys(self.repo.git_dir)
        return crypt.MultiSecretDecryptor(keyarchive=archive)

    def get_dateredacter(self) -> DateRedacter:
        if self.mode == "reduce" and self.pattern == '':
            raise click.ClickException(click.wrap_text(
                "Missing pattern configuration. Set a reduction pattern using\n"  # noqa: E501
                "\n"
                f"    git config {self.SECTION}.pattern <pattern>\n"
                "\n"
                "The pattern is a comma separated list that may contain the "
                "following time unit identifiers: "
                "M: month, d: day, h: hour, m: minute, s: second.",
                preserve_paragraphs=True))
        return ResolutionDateRedacter(self.pattern, self.limit, self.mode)

    def write_config(self, **kwargs):
        """Write config"""
        with self.repo.config_writer(config_level='repository') as writer:
            for key, value in kwargs.items():
                writer.set_value(self.SECTION, key, value)

    def comment_out_password_options(self):
        with self.repo.config_writer() as config:
            if self.password:
                config.remove_option(self.SECTION, 'password')
                config.set_value(self.SECTION, "#password", self.password)
                self.password = ""
            if self.salt:
                config.remove_option(self.SECTION, 'salt')
                config.set_value(self.SECTION, "#salt", self.salt)
                self.salt = ""


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('--gitdir', default=os.getcwd,
              type=click.Path(exists=True, file_okay=False, dir_okay=True,
                              readable=True),
              help="Path to your Git repsitory.")
@click.pass_context
def cli(ctx: click.Context, gitdir):
    ctx.obj = GitPrivacyConfig(gitdir)


@cli.command('init')
@click.option('-g', '--global', "globally", is_flag=True,
              help="Setup a global template instead.")
@click.option('--timezone-change', type=click.Choice(("warn", "abort")),
              #default="warn", show_default=True,
              help=("Reaction strategy to detected time zone changes pre commit."
                    " (default: warn)"))
@click.pass_context
def do_init(ctx: click.Context, globally: bool, 
            timezone_change: Optional[str]) -> None:
    """Init git-privacy for this repository."""
    repo = ctx.obj.repo
    if globally:
        git_dir = get_template_dir(repo)
    else:
        git_dir = repo.git_dir
    copy_hook(git_dir, "post-commit")
    copy_hook(git_dir, "pre-commit")
    copy_hook(git_dir, "post-rewrite")
    # only (over-)write settings if option is explicitly specified
    if timezone_change is not None:
        assert timezone_change in ("warn", "abort")
        ctx.obj.write_config(ignoreTimezone=(timezone_change == "warn"))


def get_template_dir(repo: git.Repo) -> str:
    default_templatedir = os.path.join(os.path.expanduser("~"),
                                       ".git_template")
    with repo.config_reader(config_level="global") as config:
        templatedir = config.get_value("init", "templatedir", "")
    if templatedir:
        if os.path.isdir(templatedir):
            return templatedir  # use existing non-default template
        if templatedir != default_templatedir:
            click.confirm("Template directory is currently set to "
                          f"non-existing {templatedir}. "
                          "Overwrite?", abort=True)
        else:
            # template set to default but folders are missing
            # recreate them in the following
            pass
    templatedir = default_templatedir
    os.mkdir(templatedir)
    os.mkdir(os.path.join(templatedir, "hooks"))
    with repo.config_writer(config_level="global") as config:
        config.set_value("init", "templatedir", templatedir)
    return templatedir


def copy_hook(git_path: str, hook: str, ) -> None:
    from pkg_resources import resource_stream, resource_string
    import shutil
    hookdir = os.path.join(git_path, "hooks")
    if not os.path.exists(hookdir):
        os.mkdir(hookdir)
    hook_fn = os.path.join(hookdir, hook)
    try:
        dst = open(hook_fn, "xb")
    except FileExistsError:
        hook_txt = resource_string('gitprivacy.resources.hooks', hook).decode()
        with open(hook_fn, "r") as f:
            if f.read() == hook_txt:
                print(f"{hook} hook is already installed at {hook_fn}.")
                return
        print(f"A Git hook already exists at {hook_fn}", file=sys.stderr)
        print("\nRemove hook and rerun or add the following to the existing "
              f"hook:\n\n{hook_txt}")
        return
    else:
        with resource_stream('gitprivacy.resources.hooks', hook) as src, dst:
            shutil.copyfileobj(src, dst)
            os.chmod(dst.fileno(), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                     stat.S_IROTH | stat.S_IXOTH)  # mode 755
            print("Installed {} hook".format(hook))


@cli.command('log')
@click.option('-r', '--revision-range', required=False, default='HEAD',
              help="Show only commits in the specified revision range.")
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
@click.pass_context
def do_log(ctx: click.Context, revision_range: str, paths: click.Path):
    """Display a git-log-like history."""
    assertCommits(ctx)
    repo = ctx.obj.repo
    crypto: crypt.DecryptionProvider = ctx.obj.get_decrypto()
    #keys._check_abort_passwordbased(ctx, crypto)
    if crypto:
        decoder: Decoder = MessageEmbeddingDecoder(crypto)
    else:
        decoder = BasicDecoder()
    commit_list = list(repo.iter_commits(rev=revision_range, paths=paths))
    buf = list()
    for commit in commit_list:
        buf.append(click.style(f"commit {commit.hexsha}", fg='yellow'))
        a_date, c_date = decoder.decode(commit)
        if a_date:
            buf.append(f"Author:   {commit.author.name} <{commit.author.email}>")  # noqa: E501
            buf.append(click.style(f"Date: {fmtdate(commit.authored_datetime)}",  # noqa: E501)
                                   fg='red'))
            buf.append(click.style(f"RealDate: {fmtdate(a_date)}", fg='green'))
        else:
            buf.append(f"Author: {commit.author.name} <{commit.author.email}>")
            buf.append(f"Date:   {fmtdate(commit.authored_datetime)}")
        if c_date:
            buf.append(f"Commit:   {commit.committer.name} <{commit.committer.email}>")  # noqa: E501
            buf.append(click.style(f"Date: {fmtdate(commit.committed_datetime)}",  # noqa: E501)
                                   fg='red'))
            buf.append(click.style(f"RealDate: {fmtdate(c_date)}", fg='green'))
        else:
            buf.append(f"Commit: {commit.committer.name} <{commit.committer.email}>")
            buf.append(f"Date:   {fmtdate(commit.committed_datetime)}")
        buf.append(os.linesep + f"    {commit.message}")
    click.echo_via_pager(os.linesep.join(buf))


def _is_cherrypick_finished(repo: git.Repo) -> bool:
    cherrypick_head = os.path.join(repo.git_dir, "CHERRY_PICK_HEAD")
    return os.path.exists(cherrypick_head) is False


@cli.command('redate')
@click.argument('startpoint', required=False, default='')
@click.option('--only-head', is_flag=True,
              help="Redate only the current head.")
@click.option('-f', '--force', is_flag=True,
              help="Force redate of commits.")
@click.pass_context
def do_redate(ctx: click.Context, startpoint: str,
              only_head: bool, force: bool):
    """Redact timestamps of existing commits."""
    assertCommits(ctx)
    repo = ctx.obj.repo
    # check for in progress rewrites (cherry-picks)
    # newer versions of Git trigger post-commit hook during
    # a cherry-pick, which conflicts with the amend rewriter
    # and also might lead to unexpected redates.
    # Hence do not redate during cherry-picks.
    # Briefly wait for the cherry-pick to finish
    # otherwise abort redating with a warning.
    if not _is_cherrypick_finished(repo):
        click.echo(
            '\n'
            'Warning: cherry-pick in progress. No redate possible.',
            err=True,
        )
        ctx.exit(5)
    redacter = ctx.obj.get_dateredacter()
    crypto = ctx.obj.get_crypto()
    keys._check_migrate_passwordbased(ctx, crypto)
    if crypto:
        encoder: Encoder = MessageEmbeddingEncoder(redacter, crypto)
    else:
        encoder = BasicEncoder(redacter)

    if only_head:  # use AmendRewriter to allow redates in dirty dirs
        amendrewriter = AmendRewriter(repo, encoder, ctx.obj.replace)
        if amendrewriter.is_already_active():
            return  # avoid cyclic invocation by post-commit hook
        amendrewriter.rewrite()
        return

    if repo.is_dirty():
        click.echo(f"Cannot redate: You have unstaged changes.", err=True)
        ctx.exit(1)
    rewriter = FilterRepoRewriter(repo, encoder, ctx.obj.replace)
    single_commit = next(repo.head.commit.iter_parents(), None) is None
    try:
        if startpoint and not single_commit:
            rev = f"{startpoint}..HEAD"
        else:
            rev = "HEAD"
            # Enforce validity of user-defined startpoint
            # to give proper feedback
            repo.commit(startpoint)
        commits = list(repo.iter_commits(rev))
    except (git.GitCommandError, git.BadName):
        click.echo(f"bad revision '{startpoint}'", err=True)
        ctx.exit(128)
    if len(commits) == 0:
        click.echo(f"Found nothing to redate for '{rev}'", err=True)
        ctx.exit(128)
    remotes = repo.git.branch(["-r", "--contains", commits[-1].hexsha])
    if remotes and not force:
        click.echo(
            "You are trying to redate commits contained in remote branches.\n"
            "Use '-f' to proceed if you are really sure.",
            err=True
        )
        ctx.exit(3)
    with click.progressbar(commits, label="Redating commits") as bar:
        for commit in bar:
            rewriter.update(commit)
    rewriter.finish()


@cli.command('redate-rewrites')
@click.pass_context
def redate_rewrites(ctx: click.Context):
    """Redact committer timestamps of rewritten commits."""
    assertCommits(ctx)
    repo = ctx.obj.repo
    rewrites_log_path = os.path.join(repo.git_dir, GIT_SUBDIR, "rewrites")
    if not os.path.exists(rewrites_log_path):
        click.echo("No pending rewrites to redact")
        ctx.exit(0)
    if repo.is_dirty():
        click.echo(f"Cannot redate: You have unstaged changes.", err=True)
        ctx.exit(1)

    # determine commits to redate
    with open(rewrites_log_path, "r") as rwlog_fp:
        rwlog = list(map(_parse_post_rewrite_format, rwlog_fp))
    olds = set(e[0] for e in rwlog)
    news = set(e[1] for e in rwlog)
    pending = news.difference(olds)  # ignore already rewritten news

    if len(pending) == 0:
        click.echo("No pending rewrites to redact")
        ctx.exit(0)

    redacter = ctx.obj.get_dateredacter()
    crypto = ctx.obj.get_crypto()
    keys._check_migrate_passwordbased(ctx, crypto)
    if crypto:
        encoder: Encoder = MessageEmbeddingEncoder(redacter, crypto)
    else:
        encoder = BasicEncoder(redacter)
    rewriter = FilterRepoRewriter(repo, encoder, ctx.obj.replace)

    commits = map(repo.commit, pending)  # get Commit objects from hashes
    with click.progressbar(commits, label="Redating commits") as bar:
        for commit in bar:
            rewriter.update(commit)
    rewriter.finish()
    os.remove(rewrites_log_path)


@cli.command('check', hidden=True)
@click.pass_context
def do_check(ctx: click.Context):
    """Pre-commit checks."""
    # check for setup up redaction patterns
    ctx.obj.get_dateredacter()  # raises errors if pattern is missing
    # check for timezone changes
    tzchanged = ctx.invoke(check_timezone_changes)
    if tzchanged and not ctx.obj.ignoreTimezone:
        click.echo(
            '\n'
            'abort commit (set "git config privacy.ignoreTimezone true"'
            ' to commit anyway)',
            err=True,
        )
        ctx.exit(2)


@cli.command('tzcheck')
@click.pass_context
def check_timezone_changes(ctx: click.Context) -> bool:
    """Check for timezone change since last commit."""
    repo = ctx.obj.repo
    if not repo.head.is_valid():
        return False  # no previous commits
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
        return False  # no previous commits by this user
    current_tz = datetime.now(timezone.utc).astimezone().tzinfo
    if last_commit.author.email == user_email:
        last_tz = last_commit.authored_datetime.tzinfo
    elif last_commit.committer.email == user_email:
        last_tz = last_commit.committed_datetime.tzinfo
    else:
        raise RuntimeError("Unexpected commit.")
    dummy_date = datetime.now()
    if (last_tz and current_tz and
            last_tz.utcoffset(dummy_date) != current_tz.utcoffset(dummy_date)):
        click.echo("Warning: Your timezone has changed since your last commit.", err=True)
        return True
    return False


@cli.command('log-rewrites', hidden=True)
@click.argument('rewrites', type=click.File("r"), default="-")
@click.option('--type', type=click.Choice(("amend", "rebase")))
@click.pass_context
def log_rewrites(ctx: click.Context, rewrites: TextIO, type: str):
    """Log rewrites for later redating of necessary."""
    # check if post-rewrites is triggered as result of AmendRewriter
    if AmendRewriter.is_already_active():
        # no need to log own amends
        assert type == "amend"
        ctx.exit(0)
    # log rewrites
    repo: git.Repo = ctx.obj.repo
    redacter = ctx.obj.get_dateredacter()
    subdir = _create_git_subdir(repo)
    rewrites_log_path = os.path.join(subdir, "rewrites")
    found_dirty_dates = False
    with open(rewrites_log_path, "a") as log:
        for rewrite in rewrites:
            _oldhex, newhex, _ = _parse_post_rewrite_format(rewrite)
            if _has_dirtydate(repo, redacter, newhex):
                log.write(rewrite)
                found_dirty_dates = True
    # warn about dirty dates
    if found_dirty_dates:
        click.echo("""A rewrite may have inserted unredacted committer dates.
To apply date redaction on these dates run

    git-privacy redate-rewrites

Warning: This alters your Git history.""", err=True)


def _create_git_subdir(repo: git.Repo) -> str:
    path = os.path.join(repo.git_dir, GIT_SUBDIR)
    if not os.path.exists(path):
        os.mkdir(path)
    return path


def _parse_post_rewrite_format(line: str) -> Tuple[str, str, str]:
    # format given to post-rewrite hook (cf. githooks(5)):
    # <old-sha1> SP <new-sha1> [ SP <extra-info> ] LF
    vals = line.split(" ", maxsplit=2)
    n_vals = len(vals)
    assert n_vals == 2 or n_vals == 3, "Unexpected post-rewrite format"
    if n_vals == 2:
        # pad to length 3
        vals.append("")
    return (vals[0].strip(), vals[1].strip(), vals[2])


def _has_dirtydate(repo: git.Repo, redacter: DateRedacter,
                   hexsha: str) -> bool:
    try:
        commit = repo.commit(hexsha)
    except ValueError:
        # commit no longer locatable
        # nothing to be dirty
        return False
    # check if commit is already loose, i.e. not part of any branch
    # (e.g., due to post-commit hook rewrites in the meantime)
    if not repo.git.branch("--contains", commit.hexsha):
        # do not warn about loose rewritten commits
        return False
    # check if commit date is already redacted
    new_cd = redacter.redact(commit.committed_datetime)
    if new_cd != commit.committed_datetime:
        return True  # commit date is dirty
    return False


cli.add_command(email.redact_email)
cli.add_command(keys.manage_keys)
