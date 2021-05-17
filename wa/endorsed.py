"""Determines who has not endorsed someone on NationStates"""

# Import logging
import logging

# Import nsapi
import nsapi
import config

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)

# Setup API
requester = nsapi.NSRequester(config.userAgent)

# Set target nation to check against
target = "kuriko"

# Collect region
region = requester.nation(target).shard("region")

# Pull target endorsement list
endorsers = set(requester.nation(target).shard("endorsements").split(","))

# Pull all nations in the region that are WA members
logging.info("Collecting %s WA Members", region)

# Pull all world wa nations
worldWA = set(requester.wa().shard("members").split(","))

# Pull all region nations
regionNations = set(requester.region(region).shard("nations").split(":"))

# Intersect wa members and region members
citizens = worldWA & regionNations

logging.info("Comparing WA Member list with target endorsers")
# Determine WA members who have not endorsed target
nonendorsers = citizens - endorsers

# Print output in formatted manner
logging.info("Outputting results\n")
with open(nsapi.absolute_path("endorsed.txt"), "w") as f:
    # Header
    print(f"The following WA Members of {region} have not endorsed {target}:", file=f)
    for step, nonendorser in enumerate(nonendorsers):
        # Increment step so that it is 1-based
        print(f"{step+1}. https://www.nationstates.net/nation={nonendorser}", file=f)
