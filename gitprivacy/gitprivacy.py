#!/usr/bin/python3
"""
git privacy
"""
import argparse
import os
import sys
import base64
import configparser
import sqlite3
import git
import progressbar
import colorama
from . import timestamp
from . import crypto
from . import database


def read_config(gitdir):
    """ Reads git config and returns a dictionary"""
    repo = git.Repo(gitdir)
    config = {}
    config_reader = repo.config_reader(config_level='repository')
    options = ["password", "mode", "salt", "limit", "databasepath"]
    for option in options:
        try:
            config[option] = config_reader.get_value("privacy", option)
        except configparser.NoOptionError as missing_option:
            if missing_option.option == "salt":
                print("No Salt found generating a new salt....", file=sys.stderr)
                config["salt"] = base64.urlsafe_b64encode(os.urandom(16))
                write_salt(gitdir, base64.urlsafe_b64encode(config["salt"]))
            elif missing_option.option == "mode":
                print("No mode defined using default", file=sys.stderr)
                config["mode"] = "simple"
            elif missing_option.option == "password":
                print("error no password", file=sys.stderr)
                raise missing_option
            elif missing_option.option == "limit":
                config["limit"] = False
            elif missing_option.option == "databasepath":
                print("databasepath not defined using path to repository", file=sys.stderr)
                config["databasepath"] = "notdefined"
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


def do_log(args):
    """ creates a git log like output """
    db_connection = connect_to_database(args.config, args.gitdir)
    colorama.init(autoreset=True)
    time_manager = timestamp.TimeStamp()
    repo = args.repo
    commit_list = repo.git.rev_list(repo.active_branch.name).splitlines()
    print("loaded {} commits, branch: {}".format(len(commit_list), repo.active_branch.name))

    try:
        magic_list = db_connection.get()
        for commit_id in commit_list:
            commit = repo.commit(commit_id)
            print(colorama.Fore.YELLOW +"commit {}".format(commit.hexsha))
            print("Author: {}".format(commit.author))
            if commit.hexsha in magic_list:
                real_date = magic_list[commit.hexsha]
                print(colorama.Fore.RED + "Date: {}".format(time_manager.seconds_to_gitstamp(commit.authored_date, commit.author_tz_offset)))
                print(colorama.Fore.GREEN + "RealDate: {}".format(real_date))
            else:
                print("Date: {}".format(time_manager.seconds_to_gitstamp(commit.authored_date, commit.author_tz_offset)))
            print("\t {} ".format(commit.message))
    except sqlite3.OperationalError as db_e:
        print(db_e)
        print("No data found in Database {}".format(db_connection.get_path()))
    finally:
        db_connection.close()


def do_anonymize(args):
    db_connection = connect_to_database(args.config, args.gitdir)
    repo = args.repo
    time_manager = args.time_manager
    commit_amount = len(repo.git.rev_list(repo.active_branch.name).splitlines())
    commit_list = repo.git.rev_list(repo.active_branch.name).splitlines()
    first_commit = repo.commit(commit_list[-1])
    first_stamp = time_manager.simple(time_manager.seconds_to_gitstamp(first_commit.authored_date, first_commit.author_tz_offset))
    last_commit = repo.commit(commit_list[0])
    last_stamp = time_manager.simple(time_manager.seconds_to_gitstamp(last_commit.authored_date, last_commit.author_tz_offset))

    # get all old dates
    datelist_original = []
    for commit in commit_list:
        commit_obj = repo.commit(commit)
        datelist_original.append((
            time_manager.seconds_to_gitstamp(commit_obj.authored_date, commit_obj.author_tz_offset),
            time_manager.seconds_to_gitstamp(commit_obj.committed_date, commit_obj.committer_tz_offset)
        ))

    try:
        start_date = input("Enter the start date [Default: {}]:".format(first_stamp))
        if start_date == "":
            start_date = first_stamp
        try:
            start_date = time_manager.simple(start_date)
        except ValueError:
            print("ERROR: Invalid Date")
        print("Your start date will be: {}".format(start_date))

        end_date = input("Enter the end date [Default: {}]:".format(last_stamp))
        if end_date == "":
            end_date = last_stamp
        try:
            end_date = time_manager.simple(end_date)
        except ValueError:
            print("ERROR: Invalid Date")
        print("Your end date will be: {}".format(end_date))

        input("Last time to make a backup (cancel via ctrl+c)")

        datelist = time_manager.datelist(start_date, end_date, commit_amount)

        git_repo = git.Git(args.gitdir)
        progress = progressbar.bar.ProgressBar(min_value=0, max_value=commit_amount).start()
        counter = 0
        for commit, date in zip(commit_list, datelist):
            sub_command = "if [ $GIT_COMMIT = {} ] \n then \n\t export GIT_AUTHOR_DATE=\"{}\"\n \t export GIT_COMMITTER_DATE=\"{}\"\n fi".format(commit, date, date)
            my_command = ["git", "filter-branch", "-f", "--env-filter", sub_command]
            git_repo.execute(command=my_command)
            counter += 1
            progress.update(counter)
        progress.finish()

        # update the DB
        print("Updating database ...")
        commit_list = repo.git.rev_list(repo.active_branch.name).splitlines()
        progress = progressbar.bar.ProgressBar(min_value=0, max_value=commit_amount).start()
        counter = 0
        for commit, (a_date, c_date) in zip(commit_list, datelist_original):
            db_connection.put(commit, a_date, c_date)
            counter += 1
            progress.update(counter)

    except KeyboardInterrupt:
        print("\n\nERROR: Cancelled by user")
    finally:
        db_connection.close()


def connect_to_database(config, repo_path):
    try:
        if config["databasepath"] != "notdefined":
            privacy = crypto.Crypto(config["salt"], str(config["password"]))
            db_connection = database.Database(
                os.path.expanduser(config["databasepath"]), privacy)
        else:
            privacy = crypto.Crypto(config["salt"], str(config["password"]))
            db_connection = database.Database(repo_path+"/history.db", privacy)
    except sqlite3.Error as sq_error:
        print("A database error occurred: {}".format(sq_error.args[0]), file=sys.stderr)
        sys.exit(1)

    return db_connection


def do_getstamp(args):
    print(args.time_manager.get_next_timestamp(args.repo))


def do_store(args):
    try:
        db_connection = connect_to_database(args.config, args.gitdir)
        db_connection.put(args.hash, args.a_date, args.c_date)
        db_connection.close()
    except sqlite3.Error as db_error:
        print("Cant't write to your database: {}".format(db_error), file=sys.stderr)
        sys.exit(1)


def do_clean(args):
    db_connection = connect_to_database(args.config, args.gitdir)
    repo = args.repo
    commit_list = []
    for branch in repo.branches:
        commit_list.append(repo.git.rev_list(branch).splitlines())
    flat_list = [item for sublist in commit_list for item in sublist]
    db_connection.clean_database(set(flat_list))
    db_connection.close()


def do_check(args):
    repo = args.repo
    time_manager = args.time_manager
    commit_list = repo.git.rev_list(repo.active_branch.name).splitlines()
    commit = repo.commit(commit_list[0])
    last_stamp = time_manager.get_timezone(time_manager.seconds_to_gitstamp(commit.authored_date, commit.author_tz_offset))[1]
    next_stamp = time_manager.get_timezone(time_manager.now())[1]
    if last_stamp != next_stamp:
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

    # Command 'log'
    parser_log = subparsers.add_parser('log', help="Display a git log like history")
    parser_log.set_defaults(func=do_log)
    # Command 'anonymize'
    parser_anonymize = subparsers.add_parser('anonymize', help="Anonymize existing repository.")
    parser_anonymize.set_defaults(func=do_anonymize)
    # Command 'clean'
    parser_clean = subparsers.add_parser('clean', help="Remove commits from database that no longer exist")
    parser_clean.set_defaults(func=do_clean)
    # Command 'check'
    parser_check = subparsers.add_parser('check', help="Check for timezone leaks")
    parser_check.set_defaults(func=do_check)
    # Command 'getstamp'
    parser_stamp = subparsers.add_parser('getstamp', help="Get a new stamp depending on your chosen method")
    parser_stamp.set_defaults(func=do_getstamp)
    # Command 'store'
    parser_store = subparsers.add_parser('store', help="Store a commit timestamps in the database.")
    parser_store.add_argument('hash', help="Commit ID in hexadecimal form")
    parser_store.add_argument('a_date', help="Author date")
    parser_store.add_argument('c_date', help="Committer date")
    parser_store.set_defaults(func=do_store)

    # parse the args and call whatever function was selected
    args = parser.parse_args()
    init(args)
    args.func(args)


if __name__ == '__main__':
    main()
