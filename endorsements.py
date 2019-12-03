"""Determines who has not been endorsed on NationStates"""

# Import lxml
from lxml import etree

# Set endorser nation to check for
endorser = "hn67"

# Load downloaded nation file
nationsXML = etree.parse("nations.xml.gz").getroot()

# Pull all nations in 100000 Islands that are WA members
waMembers = set(
    # Save nation tag
    nation for nation in nationsXML
    # Check region (child [8]) and WA status (child [5])
    if nation[8].text == "10000 Islands" and nation[5].text == "WA Member"
)

# Pull nations who are not endorsed
unendorsed = [
    # Save name ([0]) string, converting to lowercase, underscore format
    nation[0].text.lower().replace(" ", "_") for nation in waMembers
    # Check if unendorsed by checking endorsements ([6])
    if nation[6].text is None or endorser not in nation[6].text
]

# Output unendorsed nations
for step, nation in enumerate(unendorsed):
    # Increment step so that it is 1-based
    print(f"{step+1}. https://www.nationstates.net/nation={nation}")
