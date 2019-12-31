"""Determines who has not endorsed someone on NationStates"""

# Import logging
import logging

# Import requests and lxml
import requests
from lxml import etree

# Import nsapi
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)

# Set target nation to check against
target = "kuriko"

# Pull target endorsement list
# Make page request and parse with bs4
endorsersRequest = requests.get(
    "https://www.nationstates.net/cgi-bin/api.cgi?"
    +f"nation={target}&q=endorsements"
)
# Should return Nation Element
endorsersXML = etree.fromstring(endorsersRequest.text)
# Parse XML into endorser list
# Expected format is <Nation><Endorsements>nation,nation2,nation3
# Access endorsement tag using [0], and content using .text, and then split on ,
# Creates set of names
endorsers = set(endorsersXML[0].text.split(","))

# Load downloaded nation file
nationsXML = etree.parse("nations.xml.gz").getroot()

# Pull all nations in 100000 Islands that are WA members, and convert to name strings
waMembers = set(
    # Save name (child [8]) string, converting to lowercase, underscore format
    nation[0].text.lower().replace(" ", "_") for nation in nationsXML
    # Check region (child [8]) and WA status (child [5])
    if nation[8].text == "10000 Islands" and nation[5].text == "WA Member"
)

# Determine WA members who have not endorsed target
nonendorsers = waMembers - endorsers

# Print output in formatted manner
for step, nonendorser in enumerate(nonendorsers):
    # Increment step so that it is 1-based
    print(f"{step+1}. https://www.nationstates.net/nation={nonendorser}")
