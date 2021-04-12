import sys

from typing import List, Optional, Set

import click
import git  # type: ignore

import gitprivacy.utils as utils


NULL_HEX_SHA = '0000000000000000000000000000000000000000'


@click.command('pre-push', hidden=True)
@click.argument('remote_name', type=str)
@click.argument('remote_location', type=str)
@click.pass_context
def check_push(ctx: click.Context, remote_name: str,
               remote_location: str) -> None:
    """Pre-push checks to be called by Git pre-push hook.

    Pushes are aborted if any commit that would be pushed contains dates that
    have not been redated according to the current redate pattern.
    In that case the user is shown a git-privacy statement to execute that
    redate.
    It is also lists if and which remote branches (other than the push
    target) already contain a version of those unredated commits and will thus
    diverge after a redate.
    """
    del remote_name
    del remote_location
    repo = ctx.obj.repo
    # read references from stdin (cf. githooks)
    lines = sys.stdin.readlines()

    if len(lines) == 0:
        # this might happen when pushing to a diverging remote without force
        # just let it pass and Git will complain for us
        # Note: In some cases a diverging remote will NOT cause this effect
        # hence we cannot rely on sorting out that case here completely.
        ctx.exit(0)
    if len(lines) > 1:
        raise ValueError(f"Unexpected number of lines from stdin\n{lines}")

    # stdin format:
    # <local ref> SP <local sha1> SP <remote ref> SP <remote sha1> LF
    lref, lhash, _rref, rhash = lines[0].strip().split(" ")

    if lref == "(delete)":
        assert lhash == NULL_HEX_SHA
        ctx.exit(0)  # allow deletes in any case

    lref_commit = repo.commit(lhash)
    if rhash == NULL_HEX_SHA:  # remote is empty
        refs = lhash  # all commits reachalbe from lhash
        rref_commit: Optional[git.Commit] = None
        linear = True  # empty remotes are always in line
        redate_base = ""
    else:
        # all reachable from lhash but not from rhash
        # if l and r diverge it's equivalent to lhash
        # if l is behind r it means refs is empty (all commits reachable)
        try:
            rref_commit = repo.commit(rhash)
        except ValueError:
            # rhash not found locally, i.e. is not part of local history
            linear = False
        else:
            linear = _is_parent_of(rref_commit, lref_commit)

        if not linear:
            # r diverges from l – push will fail unless forced
            # Note: We can only detect force pushes by checking the
            # arguments of the caller process (e.g., with psutil).
            # However this is a hack and requires additional dep.
            # In case of a non-force push displaying unredacted commits
            # distracts from the diverging issue and the check makes more
            # sense for the subsequent push (after merge or rebase) anyway.
            # Force pushes should by far be the rarer case.
            # Ergo: We warn the user and skip the check at the risk of
            # missing force pushes ith unredacted commits.
            click.echo("Detected diverging remote. "
                       "Skip pre-push check for unredacted commits.", err=True)
            ctx.exit(0)
        else:
            refs = f"{rhash}..{lhash}"
            redate_base = utils.get_named_ref(rref_commit)

    # check for unredated commits
    redacter = ctx.obj.get_dateredacter()
    found_dirty = False
    for commit in repo.iter_commits(rev=refs):
        is_redacted = utils.is_already_redacted(redacter, commit)
        if not is_redacted:
            if not found_dirty:
                click.echo(
                    "You tried to push commits with unredacted "
                    "timestamps:",
                    err=True,
                )
                found_dirty = True
            click.echo(commit.hexsha, err=True)

    # get potential remote branches containing revs
    rbranches = list_containing_remote_branches(repo, refs)

    if found_dirty:
        redate_param = f" {redate_base}" if redate_base else ""
        click.echo("\nTo redact and redate run:\n"
                   f"\tgit-privacy redate{redate_param}",
                   err=True)
        if rbranches:
            click.echo(click.wrap_text(
                "\nWARNING: Those commits seem to be part of the following"
                " remote branches."
                " After a redate your local history will diverge from them:\n"
            ), err=True)
            click.echo("\n".join(rbranches), err=True)
            click.echo(click.wrap_text(
                "\nNote: To push them without a redate pass the '--no-verify'"
                " option to git push."
            ), err=True)
        ctx.exit(1)
    ctx.exit(0)


def _is_parent_of(commit: git.Commit, child: git.Commit) -> bool:
    return commit in child.iter_parents()


def list_containing_remote_branches(repo: git.Repo, revs: str) -> List[str]:
    """Identify remote branches that contain commits of the given rev."""
    branches: Set[str] = set()
    commits_remote = list(repo.iter_commits([revs, "--remotes"]))
    for commit in commits_remote:
        branches.update(list_containing_branches(repo, commit.hexsha))
    return list(branches)


def list_containing_branches(repo: git.Repo, hexsha: str) -> List[str]:
    out = repo.git.branch(["-r", "--contains", hexsha])
    return [b.strip() for b in out.splitlines()]
