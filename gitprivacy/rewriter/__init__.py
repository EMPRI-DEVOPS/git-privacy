import abc

from ..encoder import Encoder


class Rewriter(abc.ABC):
    """Abstract Git history Rewriter."""
    pass


from .filterrewriter import FilterBranchRewriter
