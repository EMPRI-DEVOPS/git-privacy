"""
Bulk rewriting of Git history using git-filter-repo
"""
import git  # type: ignore
import git_filter_repo as fr  # type: ignore

from typing import List, Set

from . import Rewriter
from .. import utils
from ..encoder import Encoder


class FilterRepoRewriter(Rewriter):
    """Redates commits using git-filter-repo."""

    def __init__(self, repo: git.Repo, encoder: Encoder,
                 replace: bool = False) -> None:
        super().__init__(repo, encoder, replace)
        self.commits_to_rewrite: List[git.Commit] = []
        self.commits_oid_set: Set[str] = set()
        self.with_initial_commit = False


    def update(self, commit: git.Commit) -> None:
        if not commit.parents:
            self.with_initial_commit = True
        self.commits_to_rewrite.append(commit)
        self.commits_oid_set.add(commit.hexsha)

    def _rewrite(self, commit: fr.Commit, _metadata) -> None:
        hexid = commit.original_id.decode()
        if hexid not in self.commits_oid_set:
            # do nothing
            return
        g_commit = self.repo.commit(hexid)  # get pygit Commit object
        a_redacted, c_redacted, new_msg = self.encoder.encode(g_commit)
        commit.author_date = utils.dt2gitdate(a_redacted).encode()
        commit.committer_date = utils.dt2gitdate(c_redacted).encode()
        if new_msg:
            commit.message = new_msg.encode()


    def finish(self) -> None:
        if not self.commits_to_rewrite:
            return  # nothing to do
        if self.replace:
            replace_opt = "update-or-add"
        else:
            replace_opt = "update-no-add"
        # Use reference based names instead of OIDs.
        # This avoid Git's object name warning and
        # otherwise filter-repo fails to replace the objects.
        def rev_name(commit: git.Commit) -> str:
            return commit.name_rev.split()[1]
        first = self.commits_to_rewrite[0]
        last = self.commits_to_rewrite[-1]
        assert first == last or first in last.iter_parents(), "Wrong commit order"
        first_rev = rev_name(first)
        last_rev = rev_name(last)
        if self.with_initial_commit:
            refs = last_rev
        else:
            refs = f"{first_rev}^..{last_rev}"  # ^ to include 'first' in the range
        args = fr.FilteringOptions.parse_args([
            '--source', self.repo.git_dir,
            '--force',
            '--quiet',
            '--preserve-commit-encoding',
            '--replace-refs', replace_opt,
            '--refs', refs,
        ])
        rfilter = fr.RepoFilter(args, commit_callback=self._rewrite)
        rfilter.run()
