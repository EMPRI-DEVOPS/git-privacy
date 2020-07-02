import git  # type: ignore
import os
import sys

from . import Rewriter
from ..encoder import Encoder
from ..utils import fmtdate


class AmendRewriter(Rewriter):
    """Redates commits using git commit --amend."""

    def rewrite(self) -> None:
        commit = self.repo.commit("HEAD")
        a_redacted, c_redacted, new_msg = self.encoder.encode(commit)
        cmd = [
            "git", "commit", "--amend", "--allow-empty", "--quiet",
            # skip repeated pre-commit hook to avoid gitpython locale issues
            "--no-verify",
            f"--date=\"{fmtdate(a_redacted)}\"",
        ]
        if new_msg:
            cmd.append(f"--message={new_msg}")
        else:
            cmd.append("--no-edit")
        res, stdout, stderr = self.repo.git.execute(
            command=cmd,
            env=dict(
                GIT_COMMITTER_DATE=fmtdate(c_redacted),
                GITPRIVACY_ACTIVE="yes",
            ),
            with_extended_output=True,
        )
        # forward outputs to stdout/stderr
        # Note: This indirection is necessary since git.execute does not allow
        # for passing stdout/stderr directly
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)

        # map replacement
        if self.replace:
            new_commit = self.repo.head.commit
            assert commit.hexsha != new_commit.hexsha
            res, _, err = self.repo.git.replace(
                commit.hexsha,
                new_commit.hexsha,
                with_extended_output=True,
            )
            if res != 0:
                raise RuntimeError(err)


    @staticmethod
    def is_already_active() -> bool:
        return os.getenv("GITPRIVACY_ACTIVE") == "yes"


    @staticmethod
    def is_upstream(repo: git.Repo, commit: git.Commit) -> bool:
        remotes = repo.git.branch(["-r", "--contains", commit.hexsha])
        return len(remotes) > 0
