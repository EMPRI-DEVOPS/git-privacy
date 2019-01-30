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


@click.group()
@click.option('--gitdir', default=os.getcwd,
              type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
              help="Path to your Git repsitory.")
@click.pass_context
def cli(ctx, gitdir):
    ctx.ensure_object(dict)
    try:
        config = read_config(gitdir)
        ctx.obj["config"] = config
    except git.InvalidGitRepositoryError as git_error:
        print("Can't load repository: {}".format(git_error), file=sys.stderr)
        sys.exit(1)
    except configparser.NoSectionError:
        print("Not configured", file=sys.stderr)
        sys.exit(1)
    ctx.obj["crypto"] = (crypto.Crypto(config["salt"], str(config["password"]))
                     if config["password"] else None)
    ctx.obj["time"] = timestamp.TimeStamp(config["pattern"], config["limit"], config["mode"])
    ctx.obj["repo"] = git.Repo(gitdir)


def read_config(gitdir):
    """ Reads git config and returns a dictionary"""
    repo = git.Repo(gitdir)
    config = {}
    config_reader = repo.config_reader(config_level='repository')
    options = ["password", "mode", "salt", "limit"]
    for option in options:
        try:
            config[option] = config_reader.get_value("privacy", option)
        except configparser.NoOptionError as missing_option:
            if missing_option.option == "salt" and config["password"]:
                print("No Salt found generating a new salt....", file=sys.stderr)
                config["salt"] = crypto.generate_salt()
                write_salt(gitdir, config["salt"])
            elif missing_option.option == "mode":
                print("No mode defined using default", file=sys.stderr)
                config["mode"] = "reduce"
            elif missing_option.option == "password":
                config["password"] = None
            elif missing_option.option == "limit":
                config["limit"] = False
    if config["mode"] == "reduce":
        try:
            config["pattern"] = config_reader.get_value("privacy", "pattern")
        except configparser.NoOptionError as missing_option:
            print("no pattern, setting default pattern s", file=sys.stderr)
            config["pattern"] = "s"
    else:
        config["pattern"] = ""
    return config


def write_salt(gitdir, salt):
    """ Writes salt to config """
    repo = git.Repo(gitdir)
    config_writer = repo.config_writer(config_level='repository')
    config_writer.set_value("privacy", "salt", salt)
    config_writer.release()


@cli.command('init')
@click.option('-c', '--enable-check', is_flag=True,
              help="Enable execution of 'check' before committing.")
@click.pass_context
def do_init(ctx, enable_check):
    """Init git-privacy for this repository."""
    repo = ctx.obj["repo"]
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
        print("Git hook already exists at {}".format(hook_fn), file=sys.stderr)
        print("\nRemove hook and rerun or add the following to the existing "
              "hook:\n\n{}".format(resource_string('gitprivacy.resources.hooks',
                                                   hook).decode()))
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
    tm = timestamp.TimeStamp()
    repo = ctx.obj["repo"]
    commit_list = list(repo.iter_commits())
    buf = list()
    for commit in commit_list:
        buf.append(click.style(f"commit {commit.hexsha}", fg='yellow'))
        buf.append(f"Author:\t\t{commit.author.name} <{commit.author.email}>")
        orig_dates = _decrypt_from_msg(ctx.obj["crypto"], commit.message)
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
        match = re.search(f'^{MSG_TAG}(\S+)', line)
        if match:
            return match.group(1)
    return None


def _encrypt_for_msg(crypto, a_date: datetime, c_date: datetime) -> str:
    plain = f"{a_date.isoformat()};{c_date.isoformat()}"
    return crypto.encrypt(plain)


def _decrypt_from_msg(crypto, message: str) -> Optional[Tuple[datetime, datetime]]:
    enc_dates = _extract_enc_dates(message)
    if crypto is None or enc_dates is None:
        return None
    plain_dates = crypto.decrypt(enc_dates)
    a_date, c_date = [datetime.fromisoformat(d) for d in plain_dates.split(";")]
    return a_date, c_date


@cli.command('redate')
@click.option('--only-head', is_flag=True,
              help="Redate only the current head.")
@click.pass_context
def do_redate(ctx, only_head):
    """Redact timestamps of existing commits."""
    repo = ctx.obj["repo"]
    time_manager = ctx.obj["time"]

    commits = list(repo.iter_commits())
    if only_head:
        commits = commits[0:1]
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
            if keep_msg or ctx.obj["crypto"] is None:
                append_cmd = ""
            else:
                enc_dates = _encrypt_for_msg(ctx.obj["crypto"], commit.authored_datetime,
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
                  "HEAD" if not only_head else "HEAD~1..HEAD"]
    repo.git.execute(command=filter_cmd)


@cli.command('check')
@click.pass_context
def do_check(ctx):
    """Check for timezone change since last commit."""
    time_manager = ctx.obj["time"]
    last_commit = next(ctx.obj["repo"].iter_commits())
    current_tz = datetime.now(timezone.utc).astimezone().tzinfo
    last_tz = last_commit.authored_datetime.tzinfo
    dummy_date = datetime.now()
    if last_tz.utcoffset(dummy_date) != current_tz.utcoffset(dummy_date):
        print("Warning: Your timezone has changed.")


if __name__ == '__main__':
    cli(obj={})
