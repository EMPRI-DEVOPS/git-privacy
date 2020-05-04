import git
import os

from . import Rewriter
from ..encoder import Encoder
from ..utils import fmtdate


class AmendRewriter(Rewriter):
    """Redates commits using git commit --amend."""

    def __init__(self, repo: git.Repo, encoder: Encoder) -> None:
        self.repo = repo
        self.encoder = encoder


    def rewrite(self) -> None:
        commit = self.repo.commit("HEAD")
        a_redacted, c_redacted, msg_extra = self.encoder.encode(commit)
        cmd = [
            "git", "commit", "--amend", "--allow-empty",
            f"--date=\"{fmtdate(a_redacted)}\"",
        ]
        if msg_extra:
            cmd += [
                f"--message={commit.message}",
                f"--message={msg_extra}",
            ]
        else:
            cmd.append("--no-edit")
        self.repo.git.execute(
            command=cmd,
            env=dict(
                GIT_COMMITTER_DATE=fmtdate(c_redacted),
                GITPRIVACY_ACTIVE="yes",
            ),
        )


    @staticmethod
    def is_already_active() -> bool:
        return os.getenv("GITPRIVACY_ACTIVE") == "yes"


    @staticmethod
    def is_upstream(repo: git.Repo, commit: git.Commit) -> bool:
        remotes = repo.git.branch(["-r", "--contains", commit.hexsha])
        return len(remotes) > 0
