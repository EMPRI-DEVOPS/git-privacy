import git

from . import Rewriter
from ..encoder import Encoder
from ..dateredacter import DateRedacter
from ..utils import fmtdate


class FilterBranchRewriter(Rewriter):
    """Redates commits using git filter-branch."""

    def __init__(self, repo: git.Repo, encoder: Encoder) -> None:
        self.repo = repo
        self.encoder = encoder
        self.env_cmd = ""
        self.msg_cmd = ""


    def update(self, commit: git.Commit) -> None:
        a_redacted, c_redacted, msg_extra = self.encoder.encode(commit)
        self.env_cmd += (
            f"if test \"$GIT_COMMIT\" = \"{commit.hexsha}\"; then "
            f"export GIT_AUTHOR_DATE=\"{fmtdate(a_redacted)}\"; "
            f"export GIT_COMMITTER_DATE=\"{fmtdate(c_redacted)}\"; fi; "
        )
        if msg_extra:
            append_cmd = f"&& echo && echo \"{msg_extra}\""
        else:
            append_cmd = ""
        self.msg_cmd += (
            f"if test \"$GIT_COMMIT\" = \"{commit.hexsha}\"; then "
            f"cat {append_cmd}; fi; "
        )


    def finish(self, rev: str) -> None:
        filter_cmd = ["git", "filter-branch", "-f",
                      "--env-filter", self.env_cmd,
                      "--msg-filter", self.msg_cmd,
                      "--",
                      rev]
        self.repo.git.execute(command=filter_cmd)


    @staticmethod
    def is_upstream(repo: git.Repo, commit: git.Commit) -> bool:
        remotes = repo.git.branch(["-r", "--contains", commit.hexsha])
        return len(remotes) > 0
