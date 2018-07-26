#!/usr/bin/python3
"""
git privacy
"""
import argparse
import os
import sys
import base64
import configparser
from git import Repo
import timestamp
import crypto
import database

PARSER = argparse.ArgumentParser()
PARSER.add_argument("-i", metavar="Intensity", dest="intensity",
                    help="-i low | med | high",
                    required=False)
PARSER.add_argument("-log", help="-log", action="store_true", required=False)
PARSER.add_argument("-config", help="-config", action="store_true", required=False)
PARSER.add_argument("-hexsha", metavar="hexsha", dest="hexsha",
                    help="-hexsha 7dsfg...",
                    required=False)
PARSER.add_argument("-gitdir", metavar="gitdir", dest="gitdir",
                    help="-gitdir some dir",
                    required=True)
PARSER.add_argument("-a_date", metavar="a_date", dest="a_date",
                    help="-a_date some_Date",
                    required=False)
PARSER.add_argument("-c_date", metavar="c_date", dest="c_date",
                    help="-c_date some_Date",
                    required=False)
ARGS = PARSER.parse_args()

def read_config(gitdir):
    """ Reads git config and returns dict with:
        mode
        password
        and salt """
    repo = Repo(gitdir)
    config = {}
    config_reader = repo.config_reader(config_level='repository')
    options = ["password", "mode", "salt", "limit"]
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
            elif missing_option == "limit":
                print("no limit", file=sys.stderr)
    if config["mode"] == "reduce":
        try:
            config["pattern"] = config_reader.get_value("privacy", "pattern")
        except configparser.NoOptionError as missing_option:
            print("no pattern, setting default pattern s", file=sys.stderr)
            config["pattern"] = "s"

    return config

def write_salt(gitdir, salt):
    """ Writes salt to config """
    repo = Repo(gitdir)
    config_writer = repo.config_writer(config_level='repository')
    config_writer.set_value("privacy", "salt", salt)
    config_writer.release()

def do_log(privacy):
    """ creates a git log like output """
    time_manager = timestamp.TimeStamp()
    current_working_directory = os.getcwd()
    db_connection = database.Database(current_working_directory, privacy)

    repo = Repo(current_working_directory)
    text = repo.git.rev_list("master").splitlines()
    print("loaded {} commits".format(len(text)))

    magic_list = db_connection.get()

    for commit_id in text:
        commit = repo.commit(commit_id)
        if commit.hexsha in magic_list:
            real_date = magic_list[commit.hexsha]
        else:
            real_date = "The Date is real"
        print("commit {}\n Author: {}\n Date: {}\n RealDate: {} \n \t {} ".format(commit.hexsha, commit.author,
                                                                        time_manager.seconds_to_gitstamp(commit.authored_date, commit.author_tz_offset),
                                                                        real_date,
                                                                        commit.message))

def main():
    """start stuff"""
    path = os.path.expanduser(ARGS.gitdir)
    config = read_config(path)
    salt = config["salt"]
    password = str(config["password"])

    privacy = crypto.Crypto(salt, password)
    db_connection = database.Database(path, privacy)
    # TODO put time related option in dict
    time_manager = timestamp.TimeStamp(config["pattern"], config["limit"], config["mode"])
    repo = Repo(path)
    time_stamp = time_manager.now() # TODO
    print(time_manager.get_next_timestamp(repo, time_stamp))

    if ARGS.log:
        do_log(privacy)
    elif ARGS.hexsha is not None and ARGS.a_date is not None:
        db_connection.put(ARGS.hexsha, ARGS.a_date, ARGS.c_date)

    sys.exit()

if __name__ == '__main__':
    main()
