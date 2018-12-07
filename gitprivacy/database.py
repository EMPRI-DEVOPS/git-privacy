"""database adapter"""
import sqlite3

class Database():
    """ handeling the database """
    def __init__(self, databasepath, my_crypto):
        super(Database, self).__init__()
        self.database = sqlite3.connect(databasepath)
        self.crypto = my_crypto
        self.database_cursor = self.database.cursor()
        self.databasepath = databasepath

    def get_path(self):
        """ returns path to database """
        return self.databasepath

    def clean_database(self, commit_id_list):
        """ Removes entrys that do no longer exist in the repository from the database """
        commit_id_list = map(self.crypto.hmac, commit_id_list)
        counter = 0
        try:
            all_data = self.database_cursor.execute("SELECT * FROM history")
            for row in all_data.fetchall():
                if row[0] not in commit_id_list:
                    self.database_cursor.execute('DELETE FROM history WHERE identifier=?', (row[0],))
                    counter += 1
            print("Deleted {} entrys".format(counter))
            self.database.commit()
        except Exception as db_error:
            raise db_error

    def close(self):
        if self.database:
            self.database.close()

    def get(self):
        """ reads from the sqlitedb """
        try:
            result_list = {}
            all_data = self.database_cursor.execute("SELECT * FROM history")
            for row in all_data.fetchall():
                result_list[self.crypto.decrypt(row[1])] = self.crypto.decrypt(row[2])

            return result_list
        except Exception as db_error:
            raise db_error

    def put(self, hexsha, author_date, commit_date):
        """ stores to the sqlitedb """
        identifier = self.crypto.hmac(hexsha)
        hexsha = self.crypto.encrypt(hexsha)
        commit_date = self.crypto.encrypt(commit_date)
        author_date = self.crypto.encrypt(author_date)

        try:
            self.database_cursor.execute("CREATE TABLE IF NOT EXISTS history (identifier text, hexsha text, author_date text, commit_date text)")
            self.database_cursor.execute("INSERT INTO history VALUES (?,?,?,?)", (identifier, hexsha, author_date, commit_date))
            self.database.commit()
        except Exception as db_error:
            raise db_error
