"""
Bulk rewriting of Git history using git-filter-repo
"""
import git  # type: ignore
import git_filter_repo as fr  # type: ignore

from typing import Set

from . import Rewriter
from .. import utils
from ..encoder import Encoder
from ..dateredacter import DateRedacter


class FilterRepoRewriter(Rewriter):
    """Redates commits using git-filter-repo."""

    def __init__(self, repo: git.Repo, encoder: Encoder) -> None:
        self.repo = repo
        self.encoder = encoder
        self.commits_to_rewrite: Set[str] = set()


    def update(self, commit: git.Commit) -> None:
        self.commits_to_rewrite.add(commit.hexsha)

    def _rewrite(self, commit: fr.Commit, metadata) -> None:
        hexid = commit.original_id.decode()
        if hexid not in self.commits_to_rewrite:
            # do nothing
            return
        a_redacted, c_redacted, msg_extra = self.encoder.encode(
            self.repo.commit(hexid)  # get pygit Commit object
        )
        commit.author_date = utils.dt2gitdate(a_redacted).encode()
        commit.committer_date = utils.dt2gitdate(c_redacted).encode()
        if msg_extra:
            commit.message += b"\n" + msg_extra.encode()


    def finish(self, rev: str) -> None:
        args = fr.FilteringOptions.parse_args([
            '--source', self.repo.git_dir,
            '--force',
            '--quiet',
            '--replace-refs', 'update-no-add',
        ])
        filter = fr.RepoFilter(args, commit_callback=self._rewrite)
        filter.run()


    @staticmethod
    def is_upstream(repo: git.Repo, commit: git.Commit) -> bool:
        remotes = repo.git.branch(["-r", "--contains", commit.hexsha])
        return len(remotes) > 0
