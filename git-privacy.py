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
from git import Repo
import colorama
import timestamp
import crypto
import database

PARSER = argparse.ArgumentParser()

ARGUMENTS = {
    "hexsha": {
        "argument": "-hexsha",
        "metavar": "hexsha",
        "dest": "hexsha",
        "help": "-hexsha 7dsfg...",
        "required": False
    },
    "gitdir": {
        "argument": "-gitdir",
        "metavar": "gitdir",
        "dest": "gitdir",
        "help": "-gitdir /home/user/git/somerepo",
        "required": True
    },
    "a_date": {
        "argument": "-a_date",
        "metavar": "a_date",
        "dest": "a_date",
        "help": "-a_date ",
        "required": False
    },
    "c_date": {
        "argument": "-c_date",
        "metavar": "c_date",
        "dest": "c_date",
        "help": "-c_date ",
        "required": False
    }
}

for arg in ARGUMENTS:
    PARSER.add_argument(ARGUMENTS[arg]["argument"], metavar=ARGUMENTS[arg]["metavar"],
                        dest=ARGUMENTS[arg]["dest"], help=ARGUMENTS[arg]["help"],
                        required=ARGUMENTS[arg]["required"])

# Flags

PARSER.add_argument("-log", help="-log", action="store_true", required=False)
PARSER.add_argument("-clean", help="-clean", action="store_true", required=False)

ARGS = PARSER.parse_args()

def read_config(gitdir):
    """ Reads git config and returns dict with:
        mode
        password
        and salt """
    repo = Repo(gitdir)
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
                print("no limit", file=sys.stderr)
            elif missing_option.option == "databasepath":
                print("databasepath not defined using path to repository", file=sys.stderr)
                config["databasepath"] = "notdefined"
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

def do_log(privacy, db_connection):
    """ creates a git log like output """
    colorama.init(autoreset=True)

    time_manager = timestamp.TimeStamp()
    current_working_directory = os.getcwd()

    repo = Repo(current_working_directory)
    text = repo.git.rev_list("master").splitlines()
    print("loaded {} commits".format(len(text)))

    try:
        magic_list = db_connection.get()
        for commit_id in text:
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
        print("No data found in Database")




def main():
    """start stuff"""
    # Open Config file
    repo_path = os.path.expanduser(ARGS.gitdir)
    config = read_config(repo_path)

    # init modules
    privacy = crypto.Crypto(config["salt"], str(config["password"]))
    if config["databasepath"] is "notdefined":
        db_connection = database.Database(repo_path+"/history.db", privacy)
    else:
        db_connection = database.Database(config["databasepath"], privacy)

    time_manager = timestamp.TimeStamp(config["pattern"], config["limit"], config["mode"])
    repo = Repo(repo_path)

    time_stamp = time_manager.now() # TODO
    print(time_manager.get_next_timestamp(repo, time_stamp))

    #print(time_manager.custom(2042, 10, 10, 10, 10, 10, 2))

    if ARGS.log:
        do_log(privacy, db_connection)
    elif ARGS.clean:
        db_connection.clean_database(repo.git.rev_list("master").splitlines())
    elif ARGS.hexsha is not None and ARGS.a_date is not None:
        db_connection.put(ARGS.hexsha, ARGS.a_date, ARGS.c_date)

    sys.exit()

if __name__ == '__main__':
    main()
