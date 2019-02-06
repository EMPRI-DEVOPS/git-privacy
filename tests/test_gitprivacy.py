import click
from click.testing import CliRunner
import git
import os
import time
import unittest

from gitprivacy.gitprivacy import cli


class TestGitPrivacy(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def setUpRepo(self) -> None:
        self.git = git.Git()
        self.git.init()
        self.repo = git.Repo()

    def setConfig(self) -> None:
        self.git.config(["privacy.pattern", "m,s"])

    def addCommit(self, filename: str) -> git.Commit:
        with open(filename, "w") as f:
            f.write(filename)
        self.git.add(filename)
        self.git.commit(f"-m {filename}")
        return self.repo.head.commit

    def invoke(self, args):
        return self.runner.invoke(cli, args=args)

    def test_nogit(self):
        with self.runner.isolated_filesystem():
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 2)

    def test_logwithemptygit(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 128)

    def test_log(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.addCommit("a")
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.output.startswith("commit"))
            self.assertEqual(result.output.count("commit"), 1)
            self.addCommit("b")
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output.count("commit"), 2)

    def test_redateempty(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 128)

    def test_redatenoconfig(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.addCommit("a")
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 2)

    def test_redate(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.head.commit
            self.assertNotEqual(a, ar)
            self.assertNotEqual(a.authored_date, ar.authored_date)
            self.assertEqual(ar.authored_datetime,
                             a.authored_datetime.replace(minute=0, second=0))

    def test_redatemultiple(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            b = self.addCommit("b")
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.commit("HEAD^")
            br = self.repo.commit("HEAD")
            self.assertNotEqual(a, ar)
            self.assertNotEqual(b, br)
            self.assertNotEqual(a.authored_date, ar.authored_date)
            self.assertNotEqual(b.authored_date, br.authored_date)

    def test_redatehead(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            b = self.addCommit("b")
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.commit("HEAD^")
            br = self.repo.commit("HEAD")
            self.assertEqual(a, ar)
            self.assertNotEqual(b, br)
            self.assertEqual(a.authored_date, ar.authored_date)
            self.assertNotEqual(b.authored_date, br.authored_date)

    def test_redateheadsinglecommit(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.commit("HEAD")
            self.assertNotEqual(a, ar)
            self.assertNotEqual(a.authored_date, ar.authored_date)

    def test_init(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "Installed post-commit hook" + os.linesep)
            self.assertTrue(os.access(os.path.join(".git", "hooks", "post-commit"),
                                      os.R_OK | os.X_OK))
            self.assertFalse(os.access(os.path.join(".git", "hooks", "pre-commit"),
                                       os.F_OK))
            a = self.addCommit("a")  # gitpython already returns the rewritten commit
            self.assertEqual(a.authored_datetime,
                             a.authored_datetime.replace(minute=0, second=0))

    def test_initwithcheck(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init --enable-check')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, os.linesep.join(
                f"Installed {hook} hook"
                for hook in ["post-commit", "pre-commit"]
            ) + os.linesep)
            self.assertTrue(os.access(os.path.join(".git", "hooks", "post-commit"),
                                      os.R_OK | os.X_OK))
            self.assertTrue(os.access(os.path.join(".git", "hooks", "pre-commit"),
                                      os.R_OK | os.X_OK))

    def test_checkempty(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('check')
            self.assertEqual(result.exit_code, 0)

    def test_checkone(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            result = self.invoke('check')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "")

    def test_checkchange(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            a = self.addCommit("a")
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            result = self.invoke('check')
            self.assertEqual(result.exit_code, 2)
            self.assertEqual(result.output,
                             "Warning: Your timezone has changed." + os.linesep)

    def test_checkchangeignore(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.ignoreTimezone", "true"])
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            a = self.addCommit("a")
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            result = self.invoke('check')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output,
                             "Warning: Your timezone has changed." + os.linesep)

    def test_checkwithhook(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init -c')
            self.assertEqual(result.exit_code, 0)
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            a = self.addCommit("a")
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            with self.assertRaises(git.GitCommandError):
                self.addCommit("b")

    def test_encryptdates(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.password", "passw0ord"])
            a = self.addCommit("a")
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertFalse("RealDate" in result.output)
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 0)
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertTrue("RealDate" in result.output)

    def test_pwdmismatch(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.password", "passw0ord"])
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            a = self.addCommit("a")
            self.git.config(["privacy.password", "geheim"])
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertFalse("RealDate" in result.output)


if __name__ == '__main__':
    unittest.main()
