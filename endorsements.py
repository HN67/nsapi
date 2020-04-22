"""Determines who has not been endorsed on NationStates"""

# Import logging
import logging

# Import nsapi
import nsapi
from nsapi import NationStandard as Nation

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)

# Setup API
API = nsapi.NSRequester("HN67 API Reader")

# Set endorser nation to check for
endorser = "hn67"

# Load downloaded nation file
nationsXML = API.retrieve_nation_dump()

# Pull all nations in 100000 Islands that are WA members
logging.info("Collecting 10000 Islands WA Members")
# Initalize empty list
waMembers = []
# Iterate through xml nodes
for nationNode in nationsXML:
    # Convert each node to a NationStandard object
    nation = Nation(nationNode)
    # If the nation is in XKI and WA, add to list
    if nation.basic("REGION") == "10000 Islands" and nation.basic(
        "UNSTATUS"
    ).startswith("WA"):
        waMembers.append(nation)

# Pull nations who are not endorsed
logging.info("Collecting WA members who have not been endorsed")
unendorsed = [
    # Save name string, converting to lowercase, underscore format
    nation.basic("NAME").lower().replace(" ", "_")
    for nation in waMembers
    # Check if unendorsed by checking endorsements
    if nation["ENDORSEMENTS"].text is None
    or endorser not in nation["ENDORSEMENTS"].text
]

# Output unendorsed nations
logging.info("Outputting results\n")
with open(nsapi.absolute_path("endorsements.txt"), "w") as f:
    # Header
    print(
        f"{endorser} has not endorsed the following WA Members in 10000 Islands:",
        file=f,
    )
    # Print each nation, with a URL generated
    for step, name in enumerate(unendorsed):
        # Increment step so that it is 1-based
        print(f"{step+1}. https://www.nationstates.net/nation={name}", file=f)
