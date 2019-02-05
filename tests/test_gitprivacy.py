import click
from click.testing import CliRunner
import git
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


if __name__ == '__main__':
    unittest.main()
