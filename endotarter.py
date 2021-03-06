"""Script to help with endotarting."""

import typing as t

import config
import nsapi


def collect(
    requester: nsapi.NSRequester, region: str
) -> t.Mapping[str, t.Iterable[str]]:
    """Compiles the endorsees of every WA nation in the region."""

    # Cross-reference region nations and WA members
    region_nations = set(requester.region(region).nations())
    wa_nations = set(requester.wa().shard("members").split(","))
    members = region_nations & wa_nations

    # A dict mapping each WA member of this region to the nations they endorse
    endorsees: t.Dict[str, t.List[str]] = {member: [] for member in members}

    # Parse nation dump
    for nation in requester.dumpManager().nations():
        # Search for nations that are WA in this region
        if nation in members:
            for endorser in nation.endorsements:
                endorsees[endorser].append(nation.name)

    return endorsees


def store(file: str, endorsee_data: t.Mapping[str, t.Iterable[str]]) -> None:
    pass


def main() -> None:
    """Main entrypoint"""
    requester = nsapi.NSRequester(config.userAgent)


# Automatically enter main function when run as script
if __name__ == "__main__":
    main()
