"""Parses the trading card decks of nations"""

# Import types
from typing import Iterable, Mapping, MutableMapping

# Import core modules
import logging

# Core library and modules
import nsapi
import config

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def sorted_cards(
    requester: nsapi.NSRequester, nations: Iterable[str]
) -> Mapping[str, Mapping[str, Mapping[nsapi.Card, int]]]:
    """Searchs the trading card decks of the given nations (by name), and sorts by rarity
    Returns a mapping with {rarity: {nation: {card: quantity}}} structure.
    Always includes exactly `common`, `uncommon`, `rare`, `ultra-rare`, `epic`, and `legendary`
    """
    # Prepare output structure with rarities
    # empty string key should catch any Card objects that dont have a category for some reason
    out: MutableMapping[str, MutableMapping[str, MutableMapping[nsapi.Card, int]]] = {
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
            rarityDict = out[card.category]
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


def main() -> None:
    """Main function"""

    # Provide proper user agent to api requester
    requester = nsapi.NSRequester(config.userAgent)

    # Function arguments, could be connected to command line, etc
    print("Enter the names of nations you want to search.")
    print("Seperate names with a comma, no space (e.g. 'NATION,NATION II,NATION III').")
    nations = input("Nations: ").split(",")

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
        rarities = raritiesInput.split(",")

    # Actually run the bulk logic
    data = sorted_cards(requester, nations)
    # Output the data as a csv file format
    path = nsapi.absolute_path("cardsort.csv")
    with open(path, "w") as f:
        # Write the csv headers
        print("card, nation, rarity, copies", file=f)
        # Unpack the (triple?) mapping, which basically sorts for us
        for rarity, rarityData in data.items():
            # Only output the rarity if desired
            if rarity in rarities:
                for nation, nationData in rarityData.items():
                    for card, count in nationData.items():
                        # Write each data in a different column
                        print(
                            (
                                "https://www.nationstates.net/page=deck/"
                                f"card={card.id}/season={card.season}"
                                f", {nation}, {rarity}, {count}"
                            ),
                            file=f,
                        )
    print(f"Outputted to {path}")


# Main function convention
if __name__ == "__main__":
    main()
