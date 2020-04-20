"""Determines who has not endorsed someone on NationStates"""

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

# Set target nation to check against
target = "kuriko"

# Pull target endorsement list
endorsers = set(API.nation_shard_text(target, "ENDORSEMENTS").split(","))

# Load downloaded nation file
nationsXML = API.retrieve_nation_dump()

# Pull all nations in 100000 Islands that are WA members
logging.info("Collecting 10000 Islands WA Members")
# Initalize empty list
waMembers = set()
# Iterate through xml nodes
for nationNode in nationsXML:
    # Convert each node to a NationStandard object
    nation = Nation(nationNode)
    # If the nation is in XKI and WA, add to list
    if (
        nation["REGION"].text == "10000 Islands"
        and nation["UNSTATUS"].text == "WA Member"
    ):
        # Add the formatted name
        waMembers.add(nation["NAME"].text.lower().replace(" ", "_"))

# Delete nation list to give RAM some relief
# Deletes the XML root itself, the last nationNode reference, and the nation reference
# These should free up the XML tree for the GC
del nationsXML
del nationNode
del nation

logging.info("Comparing WA Member list with target endorsers")
# Determine WA members who have not endorsed target
nonendorsers = waMembers - endorsers

# Print output in formatted manner
logging.info("Outputting results\n")
with open("endorsed.txt", "w") as f:
    # Header
    print(
        f"The following WA Members of 10000 Islands have not endorsed {target}:", file=f
    )
    for step, nonendorser in enumerate(nonendorsers):
        # Increment step so that it is 1-based
        print(f"{step+1}. https://www.nationstates.net/nation={nonendorser}", file=f)

    # Wait for user input before ending (prevents closing command prompt)
    input("Press <Enter> to exit")
