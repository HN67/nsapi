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
# Collect region
region = API.nation(target).shard("region")

# Pull target endorsement list
endorsers = set(API.nation(target).shard("ENDORSEMENTS").split(","))

# Load downloaded nation file
nationsXML = API.iterated_nation_dump()

# Pull all nations in the region that are WA members
logging.info("Collecting %s WA Members", region)
# Initalize empty list
waMembers = set()
# Iterate through xml nodes
for nationNode in nationsXML:
    # Convert each node to a NationStandard object
    nation = Nation(nationNode)
    # If the nation is in the region and WA, add to list
    if nation.basic("REGION") == region and nation.basic("UNSTATUS").startswith("WA"):
        # Add the formatted name
        waMembers.add(nation.basic("NAME").lower().replace(" ", "_"))

logging.info("Comparing WA Member list with target endorsers")
# Determine WA members who have not endorsed target
nonendorsers = waMembers - endorsers

# Print output in formatted manner
logging.info("Outputting results\n")
with open(nsapi.absolute_path("endorsed.txt"), "w") as f:
    # Header
    print(f"The following WA Members of {region} have not endorsed {target}:", file=f)
    for step, nonendorser in enumerate(nonendorsers):
        # Increment step so that it is 1-based
        print(f"{step+1}. https://www.nationstates.net/nation={nonendorser}", file=f)
