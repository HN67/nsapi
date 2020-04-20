"""Core mechanisms and wrappers for interacting with the NS API
See https://www.nationstates.net/pages/api.html for NS API details
"""

# Allow for typing using not yet defined classes
from __future__ import annotations

# Import logging for logging
import logging

# Import typing for parameter/return typing
import typing
from typing import Optional

# Import json and datetime to create custom cookie
import json
from datetime import date

# Import os for path stuff
import os

# Import shutil for copying download data
import shutil

# Import gzip to parse downloaded gz file
import gzip

# Import etree to parse data
import xml.etree.ElementTree as etree

# Import request to download data
import requests

# Set logging level
logging.basicConfig(level=logging.INFO)
# Reference logger
logger = logging.getLogger()


def absolute_path(path: str) -> str:
    """Returns the absolute path of a given path based on this file"""
    return os.path.join(os.path.dirname(__file__), path)


def download_file(url: str, fileName: str, *, headers: typing.Dict[str, str]) -> None:
    """Downloads a file from <url> to the location specified by <fileName>"""
    # Open request to url
    logging.info("Starting download of <%s> to <%s>", url, fileName)
    with requests.get(url, stream=True, headers=headers) as r:
        # Open file in write-byte mode
        with open(fileName, "wb") as f:
            # Copy data
            shutil.copyfileobj(r.raw, f)
    logging.info("Finished download of <%s> to <%s>", url, fileName)


class NSRequester:
    """Class to manage making requests from the NS API"""

    def __init__(self, userAgent: str):

        # Save user agent and construct headers object for later use
        self.headers = {"User-Agent": userAgent}

    # TODO make cookie more intelligent to reflect the fact that dump updates ~2230 PST
    def retrieve_nation_dump(self) -> etree.Element:
        """Returns the XML root node data of the daily nation data dump, only downloads if needed"""

        logging.info("Attempting to retrieve nations data dump")

        # Construct download command that references url and file destination
        def download() -> None:
            download_file(
                "https://www.nationstates.net/pages/nations.xml.gz",
                absolute_path("nations.xml.gz"),
                headers=self.headers,
            )

        # Notify of downloading
        logging.info("Checking cookie and downloading dump if needed")

        try:
            # Try loading cookie
            with open(absolute_path("cookie.json"), "r") as f:
                # Expected to contain dump_timestamp
                cookie = json.load(f)
        except FileNotFoundError:
            # Download if cookie does not exist
            # Write to the file
            logging.info(
                "Cookie does not exist, creating current cookie and downloading dump"
            )
            download()
            # Create cookie
            cookie = {"dump_timestring": date.today().isoformat()}
        else:
            # Check timestamp, redownload data if outdated
            if date.fromisoformat(cookie["dump_timestring"]) < date.today():
                logging.info("Cookie show outdated timestring, redownloading dump")
                # Write to the file
                download()
                # Update timestamp
                cookie["dump_timestring"] = date.today().isoformat()
            else:
                logging.info("Cookie is not outdated, attempting to use current dump")

        # Save the cookie
        with open(absolute_path("cookie.json"), "w") as f:
            json.dump(cookie, f)

        # Notify of start of parsing
        logging.info("Parsing XML tree")

        # Attempt to load the data
        try:
            with gzip.open(absolute_path("nations.xml.gz")) as dump:
                xml = etree.parse(dump).getroot()
        except FileNotFoundError:
            # If data does not exist, then download
            logging.info("Dump file missing, redownloading")
            download()

            # The data should have been downloaded
            logging.info("Attempting to parse XML tree")
            with gzip.open(absolute_path("nations.xml.gz")) as dump:
                xml = etree.parse(dump).getroot()

        # Return the xml
        logging.info("XML document retrieval and parsing complete")
        return xml

    def raw_request(
        self, api: str, shards: typing.Optional[typing.List[str]] = None
    ) -> str:
        """Returns the text retrieved the specified NS api
        Offers blind support for shards
        Queries "https://www.nationstates.net/cgi-bin/api.cgi?"+<api>+"&q="+<shards[0]>+...
        """
        # Make request (attaching the given api to NS's API page)
        # Prepare target
        target = "https://www.nationstates.net/cgi-bin/api.cgi?" + api + "&q="
        # Add shards if they exist
        if shards:
            target += "+".join(shards)
        request = requests.get(target, headers=self.headers)
        # Return parsed Element
        return request.text

    def xml_request(
        self, api: str, shards: typing.Optional[typing.List[str]] = None
    ) -> etree.Element:
        """Makes a request using self.raw_request and tries to parse the result into XML node"""
        return etree.fromstring(self.raw_request(api, shards))

    def nation_standard_request(self, nation_name: str) -> NationStandard:
        """Makes an self.xml_request using 'nation=<nation_name>' and encodes in a NationStandard"""
        return NationStandard(self.xml_request(f"nation={nation_name}"))

    def nation_shard_text(self, nation_name: str, shard: str) -> Optional[str]:
        """Returns the text retrieved from a single shard for a nation"""
        # XML is returned as a Nation node containing the shard, accesed with [0]
        return self.xml_request(f"nation={nation_name}", shards=[shard])[0].text


class NationStandard:
    """Wrapper for a Nation Standard XML data provided by NS"""

    # Maps tag names to index number based on API Version 9
    tag_list = [
        "NAME",
        "TYPE",
        "FULLNAME",
        "MOTTO",
        "CATEGORY",
        "UNSTATUS",
        "ENDORSEMENTS",
        "FREEDOM",
        "REGION",
        "POPULATION",
        "TAX",
        "ANIMAL",
        "CURRENCY",
        "DEMONYM",
        "DEMONYM2",
        "DEMONYM2PLURAL",
        "FLAG",
        "MAJORINDUSTRY",
        "GOVTPRIORITY",
        "GOVT",
        "FOUNDED",
        "FIRSTLOGIN",
        "LASTLOGIN",
        "LASTACTIVITY",
        "INFLUENCE",
        "FREEDOMSCORES",
        "PUBLICSECTOR",
        "DEATHS",
        "LEADER",
        "CAPITAL",
        "RELIGION",
        "FACTBOOKS",
        "DISPATCHES",
        "CARDCATEGORY",
    ]
    # Transpose the tag_list into into a dictionary
    tag_map = {tag: index for index, tag in enumerate(tag_list)}

    def __init__(self, node: etree.Element):
        """Wrapper for NATION XML node povided by NS Standard Nation API"""
        # Reference node
        self.node = node

    def __getitem__(self, key: str) -> etree.Element:
        """Attempts to retrieve a tag, sepcified by name"""
        # Check if tag is known
        if key in self.tag_map:
            child = self.node[self.tag_map[key]]
            # Check if this is indeed the correct tag
            if key == child.tag:
                # Correct tag, return
                return child
            else:
                # Incorrect tag, search manually
                # Raise warning
                logging.warning(
                    "NationStandard tag_map returned wrong index for key <%s>", key
                )
                return self.find_tag(key)
        else:
            # Unknown tag, search manually
            logging.info("NationStandard tag_map does not contain key <%s>", key)
            return self.find_tag(key)

    def find_tag(self, key: str) -> etree.Element:
        """Searches through the Nation node's children for a tag based on given name"""
        # Iterate through node children
        for child in self.node:
            # Compare tag name with given key
            if child.tag == key:
                # Return on success
                return child
        # No child with key was found since loop didnt return
        # Raise error
        raise ValueError(f"Child with tag <{key}> not found in node {self}")


def main() -> None:
    """Main function; only for testing"""

    API = NSRequester("HN67 API Reader")

    print(API.nation_standard_request("the_grendels")["LEADER"].text)

    print(API.raw_request("a=useragent"))


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
