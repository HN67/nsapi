"""Sorts all regions by their WA population."""

import nsapi
import config

requester = nsapi.NSRequester(config.userAgent)


def top_regions_by_wa_members() -> None:
    """Prints out the top 100 regions by WA members"""

    waMembers = set(requester.wa().shard("members").split(","))

    populations = {}

    for regionStandard in requester.dumpManager().regions():
        populations[regionStandard.name] = set(regionStandard.nations) & waMembers

    rankings = sorted(
        populations.keys(), key=lambda pop: len(populations[pop]), reverse=True
    )

    for rank in range(100):
        print(f"{rankings[rank]}: {len(populations[rankings[rank]])}")


def top_regions_by_delegate_votes() -> None:
    """Prints out the top 100 regions by Delegate votes"""

    votes = {}

    for regionStandard in requester.dumpManager().regions():
        votes[regionStandard.name] = regionStandard.delegateVotes

    rankings = sorted(votes.keys(), key=lambda region: votes[region], reverse=True)

    for rank in range(100):
        print(f"{rankings[rank]}: {votes[rankings[rank]]}")


top_regions_by_delegate_votes()
