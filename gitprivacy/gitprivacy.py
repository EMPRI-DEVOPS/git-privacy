#!/usr/bin/python3
"""
git privacy
"""
import argparse
from datetime import datetime, timezone
import os
import re
import stat
import sys
from typing import Optional, Tuple
import configparser
import git
import progressbar
import colorama
from . import timestamp
from . import crypto


MSG_TAG = "GitPrivacy: "


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
            if missing_option.option == "salt":
                print("No Salt found generating a new salt....", file=sys.stderr)
                config["salt"] = crypto.generate_salt()
                write_salt(gitdir, config["salt"])
            elif missing_option.option == "mode":
                print("No mode defined using default", file=sys.stderr)
                config["mode"] = "reduce"
            elif missing_option.option == "password":
                print("error no password", file=sys.stderr)
                raise missing_option
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


def do_init(args):
    copy_hook(args, "post-commit")
    if args.enable_check:
        copy_hook(args, "pre-commit")

def copy_hook(args, hook):
    from pkg_resources import resource_stream, resource_string
    import shutil
    hook_fn = os.path.join(args.repo.git_dir, "hooks", hook)
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


def do_log(args):
    """ creates a git log like output """
    colorama.init(autoreset=True)
    time_manager = timestamp.TimeStamp()
    repo = args.repo
    commit_list = list(repo.iter_commits())

    for commit in commit_list:
        print(colorama.Fore.YELLOW +"commit {}".format(commit.hexsha))
        print(f"Author:\t\t{commit.author.name} <{commit.author.email}>")
        orig_dates = _decrypt_from_msg(args.crypto, commit.message)
        if orig_dates is not None:
            a_date, c_date = orig_dates
            print(colorama.Fore.RED +
                  f"Date:\t\t{time_manager.to_string(commit.authored_datetime)}")
            print(colorama.Fore.GREEN +
                  f"RealDate:\t{time_manager.to_string(a_date)}")
        else:
            print(f"Date:\t\t{time_manager.to_string(commit.authored_datetime)}")
        print(os.linesep + f"    {commit.message}")


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
    if enc_dates is None:
        return None
    plain_dates = crypto.decrypt(enc_dates)
    a_date, c_date = [datetime.fromisoformat(d) for d in plain_dates.split(";")]
    return a_date, c_date


def do_redate(args):
    repo = args.repo
    time_manager = args.time_manager

    if time_manager.mode != "reduce":
        print("Redate only supported in 'reduce' mode.")
        sys.exit(0)

    commits = list(repo.iter_commits())
    if args.only_head:
        commits = commits[0:1]
    verbose = not args.only_head
    if verbose:
        print("Redating commits...")
        progress = progressbar.bar.ProgressBar(min_value=0, max_value=len(commits)).start()
        counter = 0
    env_cmd = ""
    msg_cmd = ""
    try:
        for commit in commits:
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
            enc_dates = _encrypt_for_msg(args.crypto, commit.authored_datetime,
                                         commit.committed_datetime)
            append_cmd = "" if keep_msg else f"&& echo && echo \"{MSG_TAG}{enc_dates}\""
            msg_cmd += (
                f"if test \"$GIT_COMMIT\" = \"{commit.hexsha}\"; then "
                f"cat {append_cmd}; fi; "
            )
            if verbose:
                counter += 1
                progress.update(counter)
        if verbose:
            progress.finish()
        filter_cmd = ["git", "filter-branch", "-f",
                      "--env-filter", env_cmd,
                      "--msg-filter", msg_cmd,
                      "--",
                      "HEAD" if not args.only_head else "HEAD~1..HEAD"]
        repo.git.execute(command=filter_cmd)
    except KeyboardInterrupt:
        print("\n\nWarning: Aborted by user")


def do_check(args):
    """Check whether the timezone has changed since the last commit."""
    time_manager = args.time_manager
    last_commit = next(args.repo.iter_commits())
    current_tz = datetime.now(timezone.utc).astimezone().tzinfo
    last_tz = last_commit.authored_datetime.tzinfo
    dummy_date = datetime.now()
    if last_tz.utcoffset(dummy_date) != current_tz.utcoffset(dummy_date):
        print("Warning: Your timezone has changed.")


def is_readable_directory(string):
    gitdir = string
    if not os.path.isdir(gitdir):
        raise argparse.ArgumentTypeError("{} is not a directory".format(gitdir))
    if not os.access(gitdir, os.R_OK):
        raise argparse.ArgumentTypeError("{} is not readable".format(gitdir))
    return gitdir


def init(args):
    try:
        config = read_config(args.gitdir)
        args.config = config
    except git.InvalidGitRepositoryError as git_error:
        print("Can't load repository: {}".format(git_error), file=sys.stderr)
        sys.exit(1)
    except configparser.NoSectionError:
        print("Not configured", file=sys.stderr)
        sys.exit(1)
    args.crypto = crypto.Crypto(config["salt"], str(config["password"]))
    args.time_manager = timestamp.TimeStamp(config["pattern"], config["limit"], config["mode"])
    args.repo = git.Repo(args.gitdir)


def main(): # pylint: disable=too-many-branches, too-many-statements
    # create the top-level parser
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=do_log)
    parser.add_argument('--gitdir',
                        help="Path to your Git repsitory",
                        required=False,
                        type=is_readable_directory,
                        default=os.getcwd())
    subparsers = parser.add_subparsers(title='subcommands')

    # Command 'init'
    parser_init = subparsers.add_parser('init', help="Init git-privacy for this repository")
    parser_init.add_argument('-c', '--enable-check',
                             help="enable execution of 'check' before committing",
                             action='store_true')
    parser_init.set_defaults(func=do_init)
    # Command 'log'
    parser_log = subparsers.add_parser('log', help="Display a git log like history")
    parser_log.set_defaults(func=do_log)
    # Command 'redate'
    parser_redate = subparsers.add_parser('redate', help="Redact timestamps of existing commits")
    parser_redate.add_argument('--only-head',
                               help="redate only the current head",
                               action='store_true')
    parser_redate.set_defaults(func=do_redate)
    # Command 'check'
    parser_check = subparsers.add_parser('check', help="Check for timezone leaks")
    parser_check.set_defaults(func=do_check)

    # parse the args and call whatever function was selected
    args = parser.parse_args()
    init(args)
    args.func(args)


if __name__ == '__main__':
    main()
