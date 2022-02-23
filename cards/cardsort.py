"""Parses the trading card decks of nations"""

# Import types
from typing import Iterable, Mapping, MutableMapping

# Import core modules
import itertools
import logging
from pathlib import Path
import time

# Core library and modules
import nsapi
import config

# Set logging level
level = logging.INFO
logging.basicConfig(
    level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def sorted_cards(
    requester: nsapi.NSRequester, nations: Iterable[str]
) -> Mapping[str, Mapping[str, Mapping[nsapi.CardIdentifier, int]]]:
    """Searchs the trading card decks of the given nations (by name), and sorts by rarity
    Returns a mapping with {rarity: {nation: {card: quantity}}} structure.
    Always includes exactly `common`, `uncommon`, `rare`, `ultra-rare`, `epic`, and `legendary`
    """
    # Prepare output structure with rarities
    # empty string key should catch any Card objects that dont have a category for some reason
    out: MutableMapping[
        str, MutableMapping[str, MutableMapping[nsapi.CardIdentifier, int]]
    ] = {
        "common": {},
        "uncommon": {},
        "rare": {},
        "ultra-rare": {},
        "epic": {},
        "legendary": {},
        "": {},
    }
    # Sort the deck of each nation
    for nation in nations:
        # Retrieve the deck of the nation (1 request)
        deck = requester.nation(nation).deck()
        # Parse each card in the deck, sorting into appropriate rarity bin
        for card in deck:
            # We dont wrap the out[] indexing in a try, since there should never be a error:
            # if for some reason the card doesnt have a category, it should have "" and
            # get placed in that bin
            rarityDict = out[card.rarity]
            # ensure this nation exists in this rarity bin
            try:
                nationDict = rarityDict[nation]
            except KeyError:
                rarityDict[nation] = {}
                nationDict = rarityDict[nation]
            # creates the card: num key-value pair if it doesnt exist
            # otherwise, increment the count
            try:
                nationDict[card] += 1
            except KeyError:
                nationDict[card] = 1

    return out


def extracted_cards(
    data: Mapping[str, Mapping[str, Mapping[nsapi.CardIdentifier, int]]]
) -> Iterable[nsapi.CardIdentifier]:
    """Returns a sequence of all Cards contained in the complex data returned by card sort."""
    return (
        card
        for nations in data.values()
        for cards in nations.values()
        for card in cards.keys()
    )


def named_cards(
    requester: nsapi.NSRequester,
    cards: Iterable[nsapi.CardIdentifier],
) -> Mapping[int, str]:
    """Maps each CardIdentifier to the nation name,
    using the card dumps. Returns a mapping from id to name
    """
    cardMap = {card.id: "" for card in cards}
    for standard in itertools.chain(
        requester.dumpManager().cards(season="1"),
        requester.dumpManager().cards(season="2"),
    ):
        if standard.id in cardMap:
            cardMap[standard.id] = standard.name
    return cardMap


def main() -> None:
    """Main function"""

    # Provide proper user agent to api requester
    requester = nsapi.NSRequester(config.userAgent)

    # Function arguments, could be connected to command line, etc

    # Get nations
    nations = []

    print("Enter the name of the file to load nations from.")
    print("Nation names in the file can be divided by commas and lines.")
    print("If you dont wont to load from a file, just press enter.")
    fileName = input("File name: ")
    if fileName != "":
        # Read each line, and split on ,
        with open(fileName, "r", encoding="utf-8") as file:
            for line in file:
                nations.extend(line.strip().split(","))

    print("\nEnter the names of any regions to search.")
    print("Every nation in any of the regions provided will be searched.")
    print(
        "Seperate multiple regions with a comma, no space (e.g. 'REGION1,REGION 2,REGION 3')."
    )
    print("Enter nothing to not search any regions.")
    regionsInput = input("Regions: ")
    if regionsInput != "":
        regions = regionsInput.split(",")
        for region in regions:
            nations.extend(requester.region(region).shard("nations").split(":"))

    print("\nEnter the names of additional nations you want to search.")
    print("Seperate names with a comma, no space (e.g. 'NATION,NATION II,NATION III').")
    extraNations = input("Nations: ")
    # If they enter nothing, we dont want to add an empty string
    if extraNations != "":
        nations.extend(extraNations.split(","))

    print(f"\n Checking the following nations: {nations}.")

    print("\nEnter the card rarities you want to view.")
    print(
        "Possibile rarities are: 'common', 'uncommon', 'rare', 'ultra-rare', 'epic', 'legendary'."
    )
    print("You can provide multiple by seperating with a comma, no space.")
    print("(e.g. 'common,ultra-rare,legendary')")
    print("Alternatively, enter nothing to view all rarities.")
    raritiesInput = input("Rarities: ")
    if raritiesInput == "":
        rarities = ["common", "uncommon", "rare", "ultra-rare", "epic", "legendary"]
    else:
        # rarities are case insensitive
        rarities = [rarity.lower() for rarity in raritiesInput.split(",")]

    print("Enter whether to collect duplicates of a card on the same nation.")
    print("Enter 'yes'/'y' to collect duplicates, or 'no' (or anything else) to not.")
    print("'no' will cause each card to have its own row, even if they are duplicates.")
    collectInput = input("Collect duplicates? ").lower()
    if collectInput in ("yes", "y"):
        collect = True
        print("Will collect duplicates.")
    else:
        collect = False
        print("Will not collect duplicates.")

    # Actually run the bulk logic
    data = sorted_cards(requester, nations)
    names = named_cards(requester, extracted_cards(data))
    # Output the data as a csv file format
    path = Path("cardsort.csv").resolve()
    with open(path, "w", encoding="utf-8") as f:
        # Write the csv headers
        headers = "card, cardName, nation, rarity"
        # Only add copies header if collecting
        if collect:
            headers += ", copies"
        print(headers, file=f)
        # Unpack the (triple?) mapping, which basically sorts for us
        for rarity, rarityData in data.items():
            # Only output the rarity if desired
            if rarity in rarities:
                for nation, nationData in rarityData.items():
                    for card, count in nationData.items():
                        # Unroll duplicates if collect option is false
                        row = (
                            "https://www.nationstates.net/page=deck/"
                            f"card={card.id}/season={card.season}"
                            f", {names[card.id]}, {nation}, {rarity}"
                        )
                        if not collect:
                            for _ in range(count):
                                print(
                                    row,
                                    file=f,
                                )
                        # Write each data in a different column
                        else:
                            print(
                                row + f", {count}",
                                file=f,
                            )
    print(f"Outputted to {path}")
    # prevents the window from immediately closing if opened standalone
    time.sleep(2)


# Main function convention
if __name__ == "__main__":
    main()
