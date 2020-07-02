import abc
import git  # type: ignore

from ..encoder import Encoder


class Rewriter(abc.ABC):
    """Abstract Git history Rewriter."""

    def __init__(self, repo: git.Repo, encoder: Encoder,
                 replace: bool = False) -> None:
        self.repo = repo
        self.encoder = encoder
        self.replace = replace


from .amendrewriter import AmendRewriter
from .filterrewriter import FilterRepoRewriter
