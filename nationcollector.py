"""Collects all nations that meet criteria, such as residency in a region with a certain tag"""

import typing as t

import nsapi
import config


def filter_regions(
    requester: nsapi.NSRequester, exclude: t.Iterable[str], *tags: str
) -> t.Collection[str]:
    """Returns a collection of regions retrieved from the world region tag api,
    after filtering is applied.
    """

    excludeSet = set(nsapi.clean_format(exclusion) for exclusion in exclude)

    return [
        region
        for region in requester.world().regions_by_tag(*tags)
        if nsapi.clean_format(region) not in excludeSet
    ]


def get_nations_by_region(
    requester: nsapi.NSRequester, regions: t.Iterable[str]
) -> t.Mapping[str, t.Iterable[str]]:
    """Returns an mapping from region to all residents of that region.
    """

    regionSet = set(nsapi.clean_format(string) for string in regions)

    output: t.Dict[str, t.List[str]] = {}

    for region in requester.dumpManager().regions():
        if nsapi.clean_format(region.name) in regionSet:
            output[nsapi.clean_format(region.name)] = [
                nsapi.clean_format(name) for name in region.nations
            ]

    return output


def assemble_defender_announcment(requester: nsapi.NSRequester) -> str:
    """Custom function to create a ping text for defender events"""
    exclude = [
        "Artificial Solar System",
        "First World Order",
        "Dead Sea",
        "Wintreath",
        "Spear Danes",
        "Rogue Wolves",
        "Naval Air Station Keflavik",
        "Lily",
        "Army of Freedom",
        "Lardyland",
        "Common Jaguar Wilds",
        "The Reich",
        "The Center For Student Engagement",
    ]
    regions = filter_regions(requester, exclude, "defender", "-fascist")

    nationMap = get_nations_by_region(requester, regions)

    outputPieces = {
        region: "".join(f"[nation]{nation}[/nation]" for nation in nations)
        for region, nations in nationMap.items()
    }

    return "\n".join(f"{region}:{tags}" for region, tags in outputPieces.items()) + "\n"


def main() -> None:
    """Main function"""
    requester = nsapi.NSRequester(config.userAgent)
    with open("defenderNations.txt", "w") as f:
        print(assemble_defender_announcment(requester), file=f)


# Entry point
if __name__ == "__main__":
    main()
