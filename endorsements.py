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
    if nation["REGION"].text == "10000 Islands" and nation["UNSTATUS"].text == "WA Member":
        waMembers.append(nation)

# Pull nations who are not endorsed
logging.info("Collecting WA members who have not been endorsed")
unendorsed = [
    # Save name string, converting to lowercase, underscore format
    nation["NAME"].text.lower().replace(" ", "_") for nation in waMembers
    # Check if unendorsed by checking endorsements
    if nation["ENDORSEMENTS"].text is None or endorser not in nation["ENDORSEMENTS"].text
]

# Delete nation list to give RAM some relief
# Deletes the XML root itself, the last nationNode reference, and the nation reference
# Also deletes the waMembers list which contains NationStandards that reference the tree
# These should free up the XML tree for the GC
del nationsXML
del waMembers
del nationNode
del nation

# Output unendorsed nations
logging.info("Outputting results\n")
with open("output.txt", "w") as f:
    # Header
    print(f"{endorser} has not endorsed the following WA Members in 10000 Islands:", file=f)
    # Print each nation, with a URL generated
    for step, nation in enumerate(unendorsed):
        # Increment step so that it is 1-based
        print(f"{step+1}. https://www.nationstates.net/nation={nation}", file=f)

    # Wait for user input before ending (prevents closing command prompt)
    input("Press <Enter> to exit")
