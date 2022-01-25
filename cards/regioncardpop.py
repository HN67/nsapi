"""Iterates through the nations of a region to check who is involved in trading cards"""

from typing import Container, Sequence

import config
import nsapi


def check_region(
    requester: nsapi.NSRequester, region: str, previous: Container[str] = None
) -> Sequence[str]:
    """Checks all nations in the specified region for trading card activity.
    Makes at most 1 + region population requests (1 for each nation).
    A nation does not qualify if it is in the `previous` container.
    """
    # If a previous list is not provided, use an empty set
    if not previous:
        previous = set()

    participants = []

    # Grabs all residents of the region
    residents = requester.region(region).shard("nations").split(":")

    # Make a request for each resident
    for nation in residents:
        if nation not in previous:
            info = requester.nation(nation).deck_info()
            # Save the nation if it meets any of the requirments
            if (
                info.numCards > 0
                or info.bank > 0
                or info.lastValued
                or info.lastPackOpened
            ):
                participants.append(nation)

    return participants


def main() -> None:
    """Main function"""

    requester = nsapi.NSRequester(config.userAgent)

    print("Specify the region you want to search for card farmers.")
    region = input("Region: ")

    print(
        "\nOptionally, provide a previous output file that indicates nations to not count."
    )
    print(
        "(i.e. the script will only output nations not in the previous output, i.e. new farmers)."
    )
    print("Or, press enter to not use a previous file.")
    previousPath = input("Previous Output File: ")

    print("\nEnter the name of the output file (defaults to `participants.txt`)")
    outputPath = input("Output Path: ")
    if not outputPath:
        outputPath = "participants.txt"

    # Load previous file if provided
    previous: set[str] = set()
    if previousPath:
        with open(previousPath, "r", encoding="utf-8") as f:
            # Each nation name is surrounded by [nation]...[/nation] tags
            # we remove the leading ones, and then split on the trailing ones
            # this leaves an extra empty element due to the trailing end tag at the end,
            # so that is removed with the slice. This process is done for each line,
            # creating a 2D iterator, which is then flattened using `a for b in c for a in b`
            # (the double for acts like a nested for loop)
            previous = {
                nation
                for nationLine in (
                    line.replace("[nation]", "").split("[/nation]")[:-1]
                    for line in f.readlines()
                )
                for nation in nationLine
            }

    participants = check_region(requester, region, previous)

    with open(outputPath, "w", encoding="utf-8") as file:
        for participant in participants:
            print(f"[nation]{participant}[/nation]", file=file, end="")
        # Print a trailing newline
        print("", file=file)

    print(f"\nCollection complete. ({len(participants)} nations selected.)")


if __name__ == "__main__":
    main()
