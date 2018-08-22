"""database adapter"""
import sqlite3
import os
import crypto

class Database(object):
    """docstring for Database"""
    def __init__(self, databasepath, crypto):
        super(Database, self).__init__()
        try:
            self.database = sqlite3.connect(databasepath)
        except Exception as e:
            raise e
        self.crypto = crypto
        self.database_cursor = self.database.cursor()

    def clean_database(self, commit_id_list):
        """Removes entrys that do no longer exist in the db"""
        commit_id_list = map(self.crypto.hmac, commit_id_list)
        counter = 0
        try:
            all_data = self.database_cursor.execute("SELECT * FROM history")
            for row in all_data.fetchall():
                if row[0] not in commit_id_list:
                    self.database_cursor.execute('DELETE FROM history WHERE identifyer=?', (row[0],))
                    counter += 1
            print("Deleted {} entrys".format(counter))
        except Exception as e:
            raise e
        finally:
            self.database.commit()
            self.database.close()


    def get(self):
        """ reads from the sqlitedb """
        try:
            result_list = {}
            all_data = self.database_cursor.execute("SELECT * FROM history")
            for row in all_data.fetchall():
                result_list[self.crypto.decrypt(row[1])] = self.crypto.decrypt(row[2])

            return result_list
        except Exception as e:
                raise e
        finally:
            self.database.close()

    def put(self, hexsha, authored_date, committer_date):
        """ stores to the sqlitedb """
        # TODO Check if data valid
        identifyer = self.crypto.hmac(hexsha)
        hexsha = self.crypto.encrypt(hexsha)
        committer_date = self.crypto.encrypt(committer_date)
        authored_date = self.crypto.encrypt(authored_date)

        try:
            self.database_cursor.execute("CREATE TABLE IF NOT EXISTS history (identifyer text, hexsha text, authored_date text, committer_date text)")
            self.database_cursor.execute("INSERT INTO history VALUES (?,?,?,?)", (identifyer, hexsha, authored_date, committer_date))
        except Exception as e:
            # TODO
            raise e
        finally:
            self.database.commit()
            self.database.close()