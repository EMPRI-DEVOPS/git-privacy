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

    def __init__(self, repo: git.Repo, encoder: Encoder,
                 replace: bool = False) -> None:
        super().__init__(repo, encoder, replace)
        self.commits_to_rewrite: Set[str] = set()


    def update(self, commit: git.Commit) -> None:
        self.commits_to_rewrite.add(commit.hexsha)

    def _rewrite(self, commit: fr.Commit, metadata) -> None:
        hexid = commit.original_id.decode()
        if hexid not in self.commits_to_rewrite:
            # do nothing
            return
        g_commit = self.repo.commit(hexid)  # get pygit Commit object
        a_redacted, c_redacted, new_msg = self.encoder.encode(g_commit)
        commit.author_date = utils.dt2gitdate(a_redacted).encode()
        commit.committer_date = utils.dt2gitdate(c_redacted).encode()
        if new_msg:
            commit.message = new_msg.encode()


    def finish(self) -> None:
        if self.replace:
            replace_opt = "update-or-add"
        else:
            replace_opt = "update-no-add"
        args = fr.FilteringOptions.parse_args([
            '--source', self.repo.git_dir,
            '--force',
            '--quiet',
            '--replace-refs', replace_opt,
        ])
        filter = fr.RepoFilter(args, commit_callback=self._rewrite)
        filter.run()


    @staticmethod
    def is_upstream(repo: git.Repo, commit: git.Commit) -> bool:
        remotes = repo.git.branch(["-r", "--contains", commit.hexsha])
        return len(remotes) > 0
