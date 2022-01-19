# pylint: disable=invalid-name,too-many-public-methods,line-too-long
import copy
import git  # type: ignore
import locale
import os
import pathlib
import time
import unittest

from click.testing import CliRunner
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from gitprivacy.gitprivacy import cli, GitPrivacyConfig
import gitprivacy.utils as utils


# make sure no non-local configs are used
HOME = ".home"
NO_GLOBAL_CONF_ENV = dict(
    HOME=HOME,  # ignore global config
    XDG_CONFIG_HOME="",
    GIT_CONFIG_NOSYSTEM="yes",  # ignore system config
)


class TestGitPrivacy(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.update(NO_GLOBAL_CONF_ENV)
        self.home = HOME  # only used for templates
        self.runner = CliRunner()
        # Prevent gitpython from forcing locales to ascii
        os.environ.update(self.getLang())

    @staticmethod
    def getLang() -> Dict:
        lc, code = locale.getlocale()
        if lc and code:
            lc_str = f"{lc}.{code}"
        else:
            lc_str = "C.UTF-8"
        return dict(LANG=lc_str, LC_ALL=lc_str)

    def setUpRepo(self) -> None:
        self.repo = git.Repo.init()
        self.git = self.repo.git
        self.configGit(self.git)

    @staticmethod
    def configGit(gitwrap: git.Git) -> None:
        # set user info
        gitwrap.config(["user.name", "John Doe"])
        gitwrap.config(["user.email", "jdoe@example.com"])
        # Prevent locale issue when git-privacy is called from hooks
        gitwrap.update_environment(**TestGitPrivacy.getLang())

    def setUpRemote(self, name="origin") -> git.Remote:
        r = git.Repo.init(f"remote_{name}", mkdir=True, bare=True)
        return self.repo.create_remote(name, r.working_dir)

    def setConfig(self) -> None:
        self.git.config(["privacy.pattern", "m,s"])

    def addCommit(self, filename: str, repo: Optional[git.Repo] = None) -> git.Commit:
        if not repo:
            repo = self.repo
        oldcwd = os.getcwd()
        os.chdir(repo.working_dir)
        with open(filename, "w") as f:
            f.write(filename)
        repo.git.add(filename)
        res, _stdout, stderr = repo.git.commit(
            f"-m {filename}",
            with_extended_output=True,
        )
        if res != 0:
            raise RuntimeError("Commit failed %s" % stderr)
        os.chdir(oldcwd)
        # make sure there are no rewrites logged during normal commits
        self.assertNotIn("redate-rewrites", stderr)
        # return a copy to avoid errors caused by the fazy loading of the
        # Commit object which in combination with git-filter-repo's eager
        # pruning results in failed lookups of no longer existing hashes
        return copy.copy(self.repo.head.commit)

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
            result = self.invoke('log a')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output.count("commit"), 1)
            result = self.invoke('log -r HEAD~1..HEAD')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output.count("commit"), 1)
            result = self.invoke('log -r HEAD~1..HEAD -- a')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output.count("commit"), 0)
            result = self.invoke('log x')
            self.assertEqual(result.exit_code, 2)

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
            self.assertIn("Error: Missing pattern configuration.", result.output)
            self.assertEqual(result.exit_code, 1)

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

    def test_redateheadwithunstagedchanges(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            with open("a", "w") as f:
                f.write("unstagedchange")
            # redate should fail on dirty WD
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 1)
            # head-only redating should work
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exception, None)
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.commit("HEAD")
            self.assertNotEqual(a, ar)
            self.assertNotEqual(a.authored_date, ar.authored_date)

    def test_redateheadempty(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.commit(["--allow-empty", "-m foo"])
            a = self.repo.head.commit
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.commit("HEAD")
            self.assertNotEqual(a, ar)
            self.assertNotEqual(a.authored_date, ar.authored_date)

    def test_redatefromstartpoint(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            self.git.checkout(["-b", "abranch"])
            b = self.addCommit("b")
            c = self.addCommit("c")
            result = self.invoke('redate master')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.commit("HEAD~2")
            br = self.repo.commit("HEAD~1")
            cr = self.repo.commit("HEAD")
            self.assertEqual(a, ar)
            self.assertNotEqual(b, br)
            self.assertNotEqual(c, cr)

    def test_redatewrongstartpoint(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            result = self.invoke('redate abc')
            self.assertEqual(result.exit_code, 128)

    def test_redatestartpointhead(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            b = self.addCommit("b")
            result = self.invoke('redate HEAD')
            self.assertEqual(result.exit_code, 128)

    def test_redatewithremote(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            remote = self.setUpRemote()
            self.setConfig()
            a = self.addCommit("a")
            remote.push(self.repo.active_branch, set_upstream=True)
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 3)
            result = self.invoke('redate -f')
            self.assertEqual(result.exit_code, 0)
            remote.push(force=True)
            b = self.addCommit("b")
            c = self.addCommit("c")
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 3)
            result = self.invoke('redate HEAD~2')
            self.assertEqual(result.exit_code, 0)

    def test_init(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, os.linesep.join(
                f"Installed {hook} hook"
                for hook in ["post-commit", "pre-commit", "post-rewrite",
                             "pre-push"]
            ) + os.linesep)
            self.assertTrue(os.access(os.path.join(".git", "hooks", "post-commit"),
                                      os.R_OK | os.X_OK))
            self.assertTrue(os.access(os.path.join(".git", "hooks", "pre-commit"),
                                      os.F_OK))
            a = self.addCommit("a")  # gitpython already returns the rewritten commit
            self.assertEqual(a.authored_datetime,
                             a.authored_datetime.replace(minute=0, second=0))

    def test_initwithcheck(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init --timezone-change=abort')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, os.linesep.join(
                f"Installed {hook} hook"
                for hook in ["post-commit", "pre-commit", "post-rewrite",
                             "pre-push"]
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
            self.git.config(["privacy.ignoreTimezone", "false"])  # default is ignore
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            a = self.addCommit("a")
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            result = self.invoke('check')
            self.assertTrue(result.output.startswith(
                "Warning: Your timezone has changed"))
            self.assertEqual(result.exit_code, 2)

    def test_checkchange_quotedmail(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            email = "johndoe@example.com"
            email_quoted = f'"{email}"'
            with self.repo.config_writer() as config:
                config.set_value("user", "email", email_quoted)
            self.git.config(["privacy.ignoreTimezone", "false"])  # default is ignore
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            a = self.addCommit("a")
            self.assertEqual(a.author.email, email)
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            result = self.invoke('check')
            self.assertTrue(result.output.startswith(
                "Warning: Your timezone has changed"))
            self.assertEqual(result.exit_code, 2)

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
            self.assertTrue(result.output.startswith(
                "Warning: Your timezone has changed"))

    def test_checkwithhook(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            a = self.addCommit("a")
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            self.addCommit("b")  # should not fail
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init --timezone-change=abort')
            self.assertEqual(result.exit_code, 0)
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            a = self.addCommit("a")
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            with self.assertRaises(git.GitCommandError):
                self.addCommit("b")

    def test_checkdifferentusers(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.ignoreTimezone", "false"])  # default is ignore
            os.environ['TZ'] = 'Europe/London'
            time.tzset()
            self.git.config(["user.email", "doe@example.com"])
            a = self.addCommit("a")
            os.environ['TZ'] = 'Europe/Berlin'
            time.tzset()
            result = self.invoke('check')
            self.assertEqual(result.exit_code, 2)
            self.git.config(["user.email", "johndoe@example.com"])
            result = self.invoke('check')
            self.assertEqual(result.exit_code, 0)
            self.assertIn(
                "info: Skipping tzcheck - no previous commits with this email",
                result.output,
            )

    def get_real_dates(self, commit):
        import gitprivacy.encoder.msgembed as msgenc
        conf = GitPrivacyConfig(".")
        crypto = conf.get_crypto()
        self.assertNotEqual(crypto, None)
        decoder = msgenc.MessageEmbeddingDecoder(crypto)
        return decoder.decode(commit)

    def test_encryptdates(self):
        from gitprivacy import utils
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 0)
            a = self.addCommit("a")
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertFalse("RealDate" in result.output)
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 0)
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertTrue("RealDate" in result.output)
            # check decrypted date correctness
            somedt = datetime(2020, 1, 1, 6, 0, tzinfo=timezone(timedelta(0, 1800)))
            self.assertEqual(utils.dt2gitdate(somedt), '1577856600 +0030')
            self.assertEqual(utils.gitdate2dt('1577856600 +0030'), somedt)
            self.assertEqual(
                a.authored_datetime,
                utils.gitdate2dt(utils.dt2gitdate(a.authored_datetime)),
            )
            ar = self.repo.head.commit
            real_ad, real_cd = self.get_real_dates(ar)
            self.assertEqual(real_ad, a.authored_datetime)
            self.assertEqual(real_cd, a.authored_datetime)

    def test_msgembedciphercompatability(self):
        import gitprivacy.encoder.msgembed as msgenc
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.password", "foobar"])
            self.git.config(["privacy.salt", "U16/n+bWLbp/MJ9DEo+Th+bbpJjYMZ7yQSUwJmk0QWQ="])
            conf = GitPrivacyConfig(".")
            crypto = conf.get_crypto()
            # old combined cipher mode
            ad, cd = msgenc._decrypt_from_msg(
                crypto,
                "a\n\nGitPrivacy: Tsfmwy/PQxvg5YkXT90G/7FmCYTzf1ionUnLAqCj08HMG6SAzTQSxLfoF/7OYMzHFXh6apb8OcqcIQY2fGnajGcrXauoQCMZYA==\n"
            )
            self.assertNotEqual(ad, None)
            self.assertNotEqual(cd, None)
            # separate cipher mode
            ad, cd = msgenc._decrypt_from_msg(
                crypto,
                "b\n\nGitPrivacy: 5+cmNIqj6DgRj2e00gHvTI+Llok5eOI6+o59IlGaize/SDHkKrLssqdXd8qzE7sbN6s6l+gen8E= NlfePlKFKT3L/Twi/9BcF/1pJYz0xoedTs7veoeAA9zpzMPOjg9vxMle3oYoPEFbrGb9pOgHqcU=\n"
            )
            self.assertNotEqual(ad, None)
            self.assertNotEqual(cd, None)

    def test_msgembedciphercompatability_keyfile(self):
        import gitprivacy.crypto as gpcrypto
        import gitprivacy.encoder.msgembed as msgenc
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.password", "foobar"])
            self.git.config(["privacy.salt", "U16/n+bWLbp/MJ9DEo+Th+bbpJjYMZ7yQSUwJmk0QWQ="])
            # migrate to keyfile
            result = self.invoke('keys --migrate-pwd')
            self.assertEqual(result.exit_code, 0)
            conf = GitPrivacyConfig(".")
            self.assertEqual(conf.password, "")
            self.assertEqual(conf.salt, "")
            crypto = conf.get_crypto()
            self.assertIsInstance(crypto, gpcrypto.MultiSecretBox)
            # old combined cipher mode
            ad, cd = msgenc._decrypt_from_msg(
                crypto,
                "a\n\nGitPrivacy: Tsfmwy/PQxvg5YkXT90G/7FmCYTzf1ionUnLAqCj08HMG6SAzTQSxLfoF/7OYMzHFXh6apb8OcqcIQY2fGnajGcrXauoQCMZYA==\n"
            )
            self.assertNotEqual(ad, None)
            self.assertNotEqual(cd, None)
            # separate cipher mode
            ad, cd = msgenc._decrypt_from_msg(
                crypto,
                "b\n\nGitPrivacy: 5+cmNIqj6DgRj2e00gHvTI+Llok5eOI6+o59IlGaize/SDHkKrLssqdXd8qzE7sbN6s6l+gen8E= NlfePlKFKT3L/Twi/9BcF/1pJYz0xoedTs7veoeAA9zpzMPOjg9vxMle3oYoPEFbrGb9pOgHqcU=\n"
            )
            self.assertNotEqual(ad, None)
            self.assertNotEqual(cd, None)


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


    def test_redatestability(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 0)
            a = self.addCommit("a")
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.head.commit
            self.assertNotEqual(a.hexsha, ar.hexsha)
            # do nothing to the repo
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            ar2 = self.repo.head.commit
            # redate should not have altered anything
            self.assertEqual(ar.message, ar2.message)
            self.assertEqual(ar.hexsha, ar2.hexsha)


    def test_commitdateupdate(self):
        import gitprivacy.encoder.msgembed as msgenc
        from gitprivacy import utils
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 0)
            a = self.addCommit("a")
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.head.commit
            real_ad, real_cd = self.get_real_dates(ar)
            self.assertEqual(real_ad, a.authored_datetime)
            self.assertEqual(real_cd, a.committed_datetime)
            time.sleep(1)  # make sure update commit date is different
            res, _, _ = self.git.commit([
                "-m",  ar.message,
                "--amend",
            ], with_extended_output=True)
            self.assertEqual(res, 0)
            au = copy.copy(self.repo.head.commit)
            # amend updated only commit date
            self.assertEqual(au.authored_datetime, ar.authored_datetime)
            self.assertNotEqual(au.committed_datetime, ar.committed_datetime)
            self.assertEqual(ar.message, au.message)
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            aur = copy.copy(self.repo.head.commit)
            self.assertNotEqual(au.message, aur.message)
            u_real_ad, u_real_cd = self.get_real_dates(aur)
            self.assertEqual(au.authored_datetime, aur.authored_datetime)
            self.assertNotEqual(au.committed_datetime, aur.committed_datetime)
            self.assertEqual(u_real_ad, a.authored_datetime)
            self.assertEqual(u_real_cd, au.committed_datetime)
            self.assertEqual(real_ad, u_real_ad)
            self.assertNotEqual(real_cd, u_real_cd)


    def load_exported_commit(self, path):
        from pkg_resources import resource_stream
        with resource_stream('tests', path) as input_fd:
            res, stdout, stderr = self.git.fast_import(
                "--force",  # discard existing commits
                istream=input_fd,
                with_extended_output=True,
            )
        self.assertEqual(res, 0)


    def test_cipherregression(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.password", "foobar"])
            self.git.config(["privacy.salt", "U16/n+bWLbp/MJ9DEo+Th+bbpJjYMZ7yQSUwJmk0QWQ="])
            # combined cipher format
            self.load_exported_commit('data/commit_cipher_combined')
            c = self.repo.head.commit
            real_ad, real_cd = self.get_real_dates(c)
            tzinfo = timezone(timedelta(0, 7200))
            self.assertEqual(real_ad, datetime(2020, 6, 29, 10, 6, 1, tzinfo=tzinfo))
            self.assertEqual(real_cd, datetime(2020, 6, 29, 10, 6, 1, tzinfo=tzinfo))
            # mixed cipher format
            self.load_exported_commit('data/commit_cipher_mixed')
            c = self.repo.head.commit
            real_ad, real_cd = self.get_real_dates(c)
            tzinfo = timezone(timedelta(0, 7200))
            self.assertEqual(real_ad, datetime(2020, 6, 29, 10, 6, 1, tzinfo=tzinfo))
            self.assertEqual(real_cd, datetime(2020, 6, 29, 11, 0, 24, tzinfo=tzinfo))
            # dedicated cipher format
            self.load_exported_commit('data/commit_cipher_dedicated')
            c = self.repo.head.commit
            real_ad, real_cd = self.get_real_dates(c)
            tzinfo = timezone(timedelta(0, 7200))
            self.assertEqual(real_ad, datetime(2020, 6, 29, 11, 3, 23, tzinfo=tzinfo))
            self.assertEqual(real_cd, datetime(2020, 6, 29, 11, 23, 41, tzinfo=tzinfo))
            # dedicated cipher format with different passwords
            self.load_exported_commit('data/commit_cipher_diffpwds')
            c = self.repo.head.commit
            real_ad, real_cd = self.get_real_dates(c)
            tzinfo = timezone(timedelta(0, 7200))
            self.assertEqual(real_ad, datetime(2020, 6, 29, 17, 22, 1, tzinfo=tzinfo))
            self.assertEqual(real_cd, None)  # diff password – not decryptable
            self.git.config(["privacy.password", "foobaz"])
            real_ad, real_cd = self.get_real_dates(c)
            self.assertEqual(real_ad, None)  # diff password – not decryptable
            self.assertEqual(real_cd, datetime(2020, 6, 29, 17, 23, 25, tzinfo=tzinfo))
            self.git.config(["privacy.password", "foobauz"])
            real_ad, real_cd = self.get_real_dates(c)
            self.assertEqual(real_ad, None)  # diff password – not decryptable
            self.assertEqual(real_cd, None)  # diff password – not decryptable


    def test_redactemail(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            email = "privat@example.com"
            self.git.config(["user.email", email])
            a = self.addCommit("a")
            self.assertEqual(a.author.email, email)
            result = self.invoke(f'redact-email')
            self.assertEqual(result.exit_code, 0)
            result = self.invoke(f'redact-email {email}')
            self.assertEqual(result.exit_code, 0)
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(email in result.output)
            commit = self.repo.head.commit
            self.assertNotEqual(commit.author.email, email)
            self.assertNotEqual(commit.committer.email, email)


    def test_redactemailcustomreplacement(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            name = "John Doe"
            email = "privat@example.com"
            repl = "public@example.com"
            self.git.config(["user.name", name])
            self.git.config(["user.email", email])
            a = self.addCommit("a")
            self.assertEqual(a.author.name, name)
            self.assertEqual(a.author.email, email)
            result = self.invoke(f'redact-email {email}:{repl}:too:many')
            self.assertEqual(result.exit_code, 2)
            result = self.invoke(f'redact-email {email}:{repl}')
            self.assertEqual(result.exit_code, 0)
            result = self.invoke('log')
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(email in result.output)
            self.assertTrue(repl in result.output)
            commit = self.repo.head.commit
            self.assertEqual(commit.author.name, name)
            self.assertEqual(commit.author.email, repl)
            self.assertEqual(commit.committer.email, repl)
            # replace back and change name
            new_name = "Doe, John"
            result = self.invoke(f'redact-email {repl}:{email}:"{new_name}"')
            self.assertEqual(result.exit_code, 0)
            commit = self.repo.head.commit
            self.assertEqual(commit.author.name, new_name)
            self.assertEqual(commit.author.email, email)
            self.assertEqual(commit.committer.name, new_name)
            self.assertEqual(commit.committer.email, email)

    def test_globaltemplate(self):
        templdir = os.path.join(self.home, ".git_template")
        with self.runner.isolated_filesystem():
            os.mkdir(self.home)
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init -g')
            self.assertEqual(result.exception, None)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, os.linesep.join(
                f"Installed {hook} hook"
                for hook in ["post-commit", "pre-commit", "post-rewrite",
                             "pre-push"]
            ) + os.linesep)
            # local Git repo initialised BEFORE global template was set up
            # hence the hooks are not present and active locally yet
            self.assertFalse(os.access(os.path.join(".git", "hooks", "post-commit"),
                                       os.R_OK | os.X_OK))  # not installed locally
            self.assertFalse(os.access(os.path.join(".git", "hooks", "pre-commit"),
                                       os.F_OK))
            self.assertTrue(os.access(os.path.join(templdir, "hooks", "post-commit"),
                                       os.R_OK | os.X_OK))
            self.assertTrue(os.access(os.path.join(templdir, "hooks", "pre-commit"),
                                      os.F_OK))
            a = self.addCommit("a")  # gitpython already returns the rewritten commit
            self.assertNotEqual(a.authored_datetime,
                             a.authored_datetime.replace(minute=0, second=0))

            # Now reinit local repo to fetch template hooks
            self.setUpRepo()
            self.assertTrue(os.access(os.path.join(".git", "hooks", "post-commit"),
                                       os.R_OK | os.X_OK))  # now installed locally too
            self.assertTrue(os.access(os.path.join(".git", "hooks", "pre-commit"),
                                      os.F_OK))
            b = self.addCommit("b")  # gitpython already returns the rewritten commit
            self.assertEqual(b.authored_datetime,
                             b.authored_datetime.replace(minute=0, second=0))

    def test_globaltemplate_init_outside_repo(self):
        home = ".home"
        templdir = os.path.join(home, ".git_template")
        with self.runner.isolated_filesystem(), \
                self.runner.isolation(env=dict(HOME=home)):
            os.mkdir(home)
            result = self.invoke('init -g')
            self.assertEqual(result.exit_code, 2)
            # installing a global hooks outside of a local repo is currently
            # not possible, as repo checks are run before any command

    def does_cherrypick_run_postcommit(self) -> bool:
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            hookdir = os.path.join(".git", "hooks")
            hookpath = os.path.join(hookdir, "post-commit")
            if not os.path.exists(hookdir):
                os.mkdir(hookdir)
            with open(hookpath, "w") as f:
                f.write("/bin/sh\n\necho DEADBEEF")
            os.chmod(hookpath, 0o755)
            a = self.addCommit("a")
            res, stdout, stderr = self.git.execute(
                ["git", "cherry-pick", "--keep-redundant-commits", "HEAD"],
                with_extended_output=True,
            )
        self.git = None
        self.repo = None
        return "DEADBEEF" in stderr

    def test_rebase(self):
        cherryhook_active = self.does_cherrypick_run_postcommit()
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            a = self.addCommit("a")
            c = self.addCommit("c")
            b = self.addCommit("b")
            def _log():
                return [c.message.strip() for c in self.repo.iter_commits()]
            self.assertEqual(_log(), ["b", "c", "a"])
            # swap last two commits
            def _rebase_cmds():
                return (
                    f"p {self.repo.commit('HEAD')}"
                    "\n"
                    f"p {self.repo.commit('HEAD^')}"
                )
            res, stdout, stderr = self.git.rebase(
                ["-q", "-i", "HEAD~2"],
                env=dict(GIT_SEQUENCE_EDITOR=f"echo '{_rebase_cmds()}' >"),
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            self.assertEqual(_log(), ["c", "b", "a"])
            self.assertEqual(stdout, "")
            self.assertNotIn("git.exc.GitCommandError", stderr)
            self.assertNotIn("cherry-pick in progress", stderr)
            # init git-privacy and try once more
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            # swap last two commits back
            res, stdout, stderr = self.git.rebase(
                ["-q", "-i", "HEAD~2"],
                env=dict(GIT_SEQUENCE_EDITOR=f"echo '{_rebase_cmds()}' >"),
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            self.assertEqual(_log(), ["b", "c", "a"])
            self.assertEqual(stdout, "")
            self.assertNotIn("git.exc.GitCommandError", stderr)
            self.assertIn("redate-rewrites", stderr)  # logged redates
            # check result of redating during rebase
            # depending on external factors a cherry-pick might not have
            # concluded. Distinguish both cases.
            br = self.repo.head.commit
            cr = self.repo.commit("HEAD^")
            if not cherryhook_active or "cherry-pick in progress" in stderr:
                # no redate
                self.assertEqual(b.authored_date, br.authored_date)
                self.assertEqual(c.authored_date, cr.authored_date)
            else:
                # redated
                self.assertNotEqual(b.authored_date, br.authored_date)
                self.assertNotEqual(c.authored_date, cr.authored_date)

    def test_rewritelog(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            # check redate empty repo
            result = self.invoke('redate-rewrites')
            self.assertEqual(result.exit_code, 128)
            # check redate without pending rewrites
            a = self.addCommit("a")
            result = self.invoke('redate-rewrites')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "No pending rewrites to redact\n")
            # make sure an amend does not log a rewrite
            # because the post-commit hook already took care
            res, _, stderr = self.git.commit([
                "--no-edit",
                "--amend",
            ], with_extended_output=True)
            self.assertEqual(res, 0)
            self.assertNotIn("redate-rewrites", stderr)
            # add two more commits and do some rebasing
            b = self.addCommit("b")
            c = self.addCommit("c")
            # swap last two commits
            def _rebase_cmds():
                return (
                    f"p {self.repo.commit('HEAD')}"
                    "\n"
                    f"p {self.repo.commit('HEAD^')}"
                )
            res, stdout, stderr = self.git.rebase(
                ["-q", "-i", "HEAD~2"],
                env=dict(GIT_SEQUENCE_EDITOR=f"echo '{_rebase_cmds()}' >"),
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            self.assertEqual(stdout, "")
            self.assertIn("redate-rewrites", stderr)  # logged redates
            br = self.repo.head.commit
            cr = self.repo.commit("HEAD^")
            rwpath = os.path.join(self.repo.git_dir, "privacy", "rewrites")
            with open(rwpath) as f:
                rewrites = f.read()
            self.assertEqual(len(rewrites.splitlines()), 2)
            self.assertIn(br.hexsha, rewrites)
            self.assertIn(cr.hexsha, rewrites)
            self.assertFalse(self._is_loose(br))
            self.assertFalse(self._is_loose(cr))
            # redate rewrites
            result = self.invoke('redate-rewrites')
            self.assertEqual(result.exit_code, 0)
            # check result of redating
            self.assertTrue(self._is_loose(br))
            self.assertTrue(self._is_loose(cr))
            # rw log should be deleted after redating
            self.assertFalse(os.path.exists(rwpath))

    def _is_loose(self, commit) -> bool:
        try:
            return self.git.branch("--contains", commit.hexsha) == ""
        except git.GitCommandError:
            return True  # cannot even find commit anymore

    def test_replace(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.replacements", "true"])
            # test replacement set by FilterRepoRewriter
            a = self.addCommit("a")
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.head.commit
            self.assertNotEqual(a, ar)
            rpls = self.git.replace("-l", "--format=medium").splitlines()
            self.assertEqual(len(rpls), 1)
            self.assertIn(f"{a.hexsha} -> {ar.hexsha}", rpls)
            # test replacement set by AmendRewriter
            b = self.addCommit("b")
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            br = self.repo.head.commit
            self.assertNotEqual(b, br)
            rpls = self.git.replace("-l", "--format=medium").splitlines()
            self.assertEqual(len(rpls), 2)
            self.assertIn(f"{b.hexsha} -> {br.hexsha}", rpls)
            # test without replacements
            self.git.config(["--unset", "privacy.replacements"])
            self.addCommit("c")
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 0)
            self.addCommit("d")
            result = self.invoke('redate --only-head')
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(len(rpls), 2)  # no further replacements

    def test_pwdmigration(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            self.git.config(["privacy.password", "foobar"])
            self.git.config(["privacy.salt", "U16/n+bWLbp/MJ9DEo+Th+bbpJjYMZ7yQSUwJmk0QWQ="])
            # any non-migrate command should fail – since there is still a
            # password set in the config
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 1)
            self.assertFalse(os.path.isfile(".git/privacy/keys/current"))
            # ... then migrate
            result = self.invoke('keys --migrate-pwd')
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.isfile(".git/privacy/keys/current"))
            # password and salt config settings are gone (commented out)
            with self.repo.config_reader() as config:
                self.assertFalse(config.has_option("privacy", "password"))
                self.assertFalse(config.has_option("privacy", "salt"))
            # now migrate should fail – since there is no password anymore
            result = self.invoke('keys --migrate-pwd')
            self.assertEqual(result.exit_code, 1)

    def test_pwdmigration_with_previous_key(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            # generate key
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 0)
            # set password
            self.git.config(["privacy.password", "foobar"])
            self.git.config(["privacy.salt", "U16/n+bWLbp/MJ9DEo+Th+bbpJjYMZ7yQSUwJmk0QWQ="])
            # ... then migrate
            result = self.invoke('keys --migrate-pwd')
            self.assertEqual(result.exit_code, 1)  # fails because no confirmation
            # password and salt config settings are still there
            with self.repo.config_reader() as config:
                self.assertTrue(config.has_option("privacy", "password"))
                self.assertTrue(config.has_option("privacy", "salt"))

    def test_key_activation_deactivation(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            # try disable key without any key present
            result = self.invoke('keys --disable')
            self.assertEqual(result.exit_code, 1)
            # init
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.isfile(".git/privacy/keys/current"))
            self.assertFalse(os.path.isfile(".git/privacy/keys/archive/1"))
            # disable key
            result = self.invoke('keys --disable')
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(os.path.isfile(".git/privacy/keys/current"))
            self.assertTrue(os.path.isfile(".git/privacy/keys/archive/1"))

    def test_key_renewal(self):
        current_p = pathlib.Path(".git/privacy/keys/current")
        archive1_p = pathlib.Path(".git/privacy/keys/archive/1")
        archive2_p = pathlib.Path(".git/privacy/keys/archive/2")
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            self.setConfig()
            # check renewal without previous key
            result = self.invoke('keys --new')
            self.assertEqual(result.exit_code, 1)
            # generate init key
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(current_p.is_file())
            self.assertFalse(archive1_p.is_file())
            old_key = current_p.read_text()
            # renew key
            result = self.invoke('keys --new')
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(current_p.is_file())
            self.assertTrue(archive1_p.is_file())
            a1_key = archive1_p.read_text()
            self.assertEqual(old_key, a1_key)
            # test --no-archive
            result = self.invoke('keys --new --no-archive')
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(archive2_p.is_file())
            # test repeated --init
            result = self.invoke('keys --init')
            self.assertEqual(result.exit_code, 1)

    def test_prepush_check(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            remote = self.setUpRemote()
            # commit before git-privacy init to produce unredacted ts
            a = self.addCommit("a")
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            # try to push them unredacted
            with self.assertRaises(git.GitCommandError) as cm:
                self.git.push(
                    [remote.name, self.repo.active_branch],
                )
            self.assertEqual(cm.exception.status, 1)
            self.assertIn(
                'You tried to push commits with unredacted timestamps:',
                cm.exception.stderr,
            )
            self.assertIn(a.hexsha, cm.exception.stderr)
            # make shure no redate base argument is suggested (first commit)
            self.assertRegex(cm.exception.stderr, r"(?m)git-privacy redate$")
            # make shure other remote warning is not shown
            self.assertNotRegex(cm.exception.stderr, r"(?m)^WARNING:")
            # try to force-push them unredacted – should make no difference
            with self.assertRaises(git.GitCommandError) as cm:
                self.git.push(
                    ["-f", remote.name, self.repo.active_branch],
                )
            self.assertEqual(cm.exception.status, 1)
            self.assertIn(
                'You tried to push commits with unredacted timestamps:',
                cm.exception.stderr,
            )
            # redate and then push – should work
            result = self.invoke('redate')
            self.assertEqual(result.exit_code, 0)
            ar = self.repo.head.commit
            res, _stdout, _stderr = self.git.push(
                [remote.name, self.repo.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            # now try with multiple non-initial unredacted commits
            # ... but remove post-commit hook before to prevent redating
            os.remove(".git/hooks/post-commit")
            b = self.addCommit("b")
            c = self.addCommit("c")
            with self.assertRaises(git.GitCommandError) as cm:
                res_tuple = self.git.push(
                    [remote.name, self.repo.active_branch],
                    with_extended_output=True,
                )
                raise RuntimeError(res_tuple)
            self.assertEqual(cm.exception.status, 1)
            self.assertIn(
                'You tried to push commits with unredacted timestamps:',
                cm.exception.stderr,
            )
            self.assertRegex(cm.exception.stderr, fr"(?m)^{b.hexsha}$")
            self.assertRegex(cm.exception.stderr, fr"(?m)^{c.hexsha}$")
            named_redate_base = utils.get_named_ref(ar)
            self.assertRegex(cm.exception.stderr,
                             fr"(?m)git-privacy redate {named_redate_base}$")
            # make shure other remote warning is not shown
            self.assertNotRegex(cm.exception.stderr, r"(?m)^WARNING:")
            # again, redate local changes and then push – should work
            result = self.invoke('redate origin/master')
            #self.assertEqual(result.output, "")
            self.assertEqual(result.exit_code, 0)
            cr = self.repo.head.commit
            self.assertNotEqual(cr.hexsha, c.hexsha)
            res, _stdout, _stderr = self.git.push(
                [remote.name, self.repo.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            # push to separate remote branch and delete it
            res, _stdout, _stderr = self.git.push(
                [remote.name, f"{self.repo.active_branch}:foobar"],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            res, _stdout, _stderr = self.git.push(
                ["-d", remote.name, "foobar"],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)

    def test_prepush_check_multiple_remotes(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            r_origin = self.setUpRemote()
            r_tomato = self.setUpRemote("tomato")
            # commit before git-privacy init to produce unredacted ts
            a = self.addCommit("a")
            b = self.addCommit("b")
            c = self.addCommit("c")
            # push to tomato before git-privacy init
            res, _stdout, _stderr = self.git.push(
                [r_tomato.name, self.repo.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            # setup git-privacy and try to push to origin
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            # try to push them unredacted – should fail
            with self.assertRaises(git.GitCommandError) as cm:
                self.git.push(
                    [r_origin.name, self.repo.active_branch],
                )
            self.assertEqual(cm.exception.status, 1)
            self.assertIn(
                'You tried to push commits with unredacted timestamps:',
                cm.exception.stderr,
            )
            self.assertRegex(cm.exception.stderr, fr"(?m)^{a.hexsha}$")
            self.assertRegex(cm.exception.stderr, fr"(?m)^{b.hexsha}$")
            self.assertRegex(cm.exception.stderr, fr"(?m)^{c.hexsha}$")
            # make shure no redate base argument is suggested (first commit)
            self.assertRegex(cm.exception.stderr, r"(?m)git-privacy redate$")
            # check for warning about tomato
            self.assertRegex(cm.exception.stderr, r"(?m)^WARNING:")
            self.assertRegex(cm.exception.stderr,
                             fr"(?m)^{r_tomato.name}/{self.repo.active_branch}$")

    def test_prepush_check_diverging_remote(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            # setup git-privacy
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            r = self.setUpRemote()
            # do a common commit
            self.addCommit("a")
            # push to remote before cloning
            res, _stdout, _stderr = self.git.push(
                [r.name, self.repo.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            # make a clone and push an update there
            clone = git.Repo.clone_from(r.url, "clone")
            self.configGit(clone.git)
            self.addCommit("b", repo=clone)
            res, _stdout, _stderr = clone.git.push(
                [r.name, clone.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            # make local diverge by adding c
            self.addCommit("c")
            # try to push – should fail and warn about skipping
            with self.assertRaises(git.GitCommandError) as cm:
                self.git.push(
                    [r.name, self.repo.active_branch],
                )
            self.assertEqual(cm.exception.status, 1)
            self.assertIn(
                'Detected diverging remote.',
                cm.exception.stderr,
            )
            # ... now force push. Warning remains
            res, _stdout, stderr = self.git.push(
                ["-f", r.name, self.repo.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            self.assertIn(
                'Detected diverging remote.',
                stderr,
            )

    def test_prepush_check_multiple_tags(self):
        with self.runner.isolated_filesystem():
            self.setUpRepo()
            # setup git-privacy
            self.setConfig()
            result = self.invoke('init')
            self.assertEqual(result.exit_code, 0)
            r = self.setUpRemote()
            # make some commits and tags
            self.addCommit("a")
            self.repo.create_tag("tag_a")
            self.addCommit("b")
            self.repo.create_tag("tag_b")
            # push to remote before cloning
            res, _stdout, _stderr = self.git.push(
                [r.name, self.repo.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)
            # ... now push all tags
            res, _stdout, stderr = self.git.push(
                ["--tags", r.name, self.repo.active_branch],
                with_extended_output=True,
            )
            self.assertEqual(res, 0)


if __name__ == '__main__':
    unittest.main()
