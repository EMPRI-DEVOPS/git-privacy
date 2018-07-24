import sqlite3
import os

class Database(object):
    """docstring for Database"""
    def __init__(self, gitdir):
        super(Database, self).__init__()
        self.gitdir = gitdir
        self.database = sqlite3.connect("{}{}{}".format(self.gitdir, os.sep, "history.db"))

    def clean_database(self, commit_id_list, privacy):
        """Removes entrys that do no longer exist in the db"""
        # TODO: Implement
        pass

    # TODO: Move db related stuff