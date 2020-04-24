"""Core mechanisms and wrappers for interacting with the NS API
See https://www.nationstates.net/pages/api.html for NS API details
"""

# Allow for typing using not yet defined classes
from __future__ import annotations

# Import logging for logging
import logging

# Import typing for parameter/return typing
import typing
from typing import Dict, Generator

# Import json and datetime to create custom cookie
import json
import datetime

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


def current_dump_day() -> datetime.date:
    """Calculates the latest day available for the data dump.
    A datadump is generated ~2230 PST for that day, so the dump will be considered
    available at 2300 PST or 0700 UTC the next day.
    Returns a naive date"""
    utc = datetime.datetime.utcnow()
    logging.info("Current time is %s UTC", utc)
    return (
        utc.date() - datetime.timedelta(days=1)
        if utc.time().hour >= 7
        else utc.date() - datetime.timedelta(days=2)
    )


class NSRequester:
    """Class to manage making requests from the NS API"""

    def __init__(self, userAgent: str):

        # Save user agent and construct headers object for later use
        self.headers = {"User-Agent": userAgent}

        self.nationDumpPath: str = absolute_path("nations.xml.gz")

    def download_nation_dump(self) -> None:
        """Downloads the compressed nation dump"""
        download_file(
            "https://www.nationstates.net/pages/nations.xml.gz",
            self.nationDumpPath,
            headers=self.headers,
        )

    def update_nation_dump(self) -> None:
        """Downloads the compressed nation dump only if it is outdated or doesnt exist"""

        logging.info("Attempting to retrieve nations data dump")

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
            self.download_nation_dump()
            # Create cookie
            cookie = {"dump_timestring": current_dump_day().isoformat()}
        else:
            # Check timestamp, redownload data if outdated
            if (
                "dump_timestring" not in cookie
                or datetime.date.fromisoformat(cookie["dump_timestring"])
                < current_dump_day()
            ):
                logging.info("Cookie show outdated timestring, redownloading dump")
                # Write to the file
                self.download_nation_dump()
                # Update timestamp
                cookie["dump_timestring"] = current_dump_day().isoformat()
            else:
                # Verify that dump exists
                if not os.path.isfile(self.nationDumpPath):
                    logging.info(
                        "Cookie is not outdated but dump does not exist, so downloading"
                    )
                    self.download_nation_dump()

        # Save the cookie
        with open(absolute_path("cookie.json"), "w") as f:
            json.dump(cookie, f)

    def retrieve_nation_dump(self) -> etree.Element:
        """Returns the XML root node data of the daily nation data dump, only downloads if needed"""

        # Update data dump
        self.update_nation_dump()

        # Notify of start of parsing
        logging.info("Parsing XML tree")

        # Attempt to load the data
        with gzip.open(self.nationDumpPath) as dump:
            xml = etree.parse(dump).getroot()

        # Return the xml
        logging.info("XML document retrieval and parsing complete")
        return xml

    def iterated_nation_dump(self) -> Generator[etree.Element, None, None]:
        """A generator that iterates through the nations in the data dump"""

        # Update data dump
        self.update_nation_dump()

        logging.info("Starting iterative XML tree parse")

        # Attempt to load the data
        with gzip.open(self.nationDumpPath) as dump:
            # Define iterator
            iterator = etree.iterparse(dump, events=("start", "end"))
            # Get root
            _, root = next(iterator)

            # Yield elements
            for event, element in iterator:
                if event == "end" and element.tag == "NATION":
                    yield element
                    root.clear()

    def raw_request(
        self, api: str, shards: typing.Optional[typing.Iterable[str]] = None
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
        self, api: str, shards: typing.Optional[typing.Iterable[str]] = None
    ) -> etree.Element:
        """Makes a request using self.raw_request and tries to parse the result into XML node"""
        return etree.fromstring(self.raw_request(api, shards))

    def nation_standard_request(self, nation_name: str) -> NationStandard:
        """Makes an self.xml_request using 'nation=<nation_name>' and encodes in a NationStandard"""
        return NationStandard(self.xml_request(f"nation={nation_name}"))

    def nation_shard_text(self, nation_name: str, shard: str) -> str:
        """Returns the text retrieved from a single shard for a nation"""
        # XML is returned as a Nation node containing the shard, accesed with [0]
        text = self.xml_request(f"nation={nation_name}", shards=[shard])[0].text
        return text if text else ""

    def nation(self, nation: str) -> Nation:
        """Returns a Nation object using this requester"""
        return Nation(self, nation)


class Nation:
    """Represents a live connection to the API of a Nation on NS"""

    def __init__(self, api: NSRequester, name: str) -> None:
        self.api = api
        self.name = name

    def standard(self) -> NationStandard:
        """Returns a NationStandard object for this Nation"""
        return self.api.nation_standard_request(self.name)

    def shards(self, *shards: str) -> Dict[str, str]:
        """Naively returns a Dict mapping from the shard name to the text of that element
        Not all shards are one level deep, and as such have no text,
        but this method will only return the empty string, with no warning
        """
        return {
            shard: node.text if node.text else ""
            for node in self.api.xml_request(f"nation={self.name}", shards)
            for shard in shards
        }

    def shard(self, shard: str) -> str:
        """Naively returns the text associated with the shard node, which may be empty"""
        return self.shards(shard)[shard]


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
        """Attempts to retrieve a Element, sepcified by tag name"""
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

    def basic(self, key: str) -> str:
        """Attempts to retrive the text associated with a basic field, such as endorsements.
        Returns an empty string if the node has no text
        """
        value = self[key].text
        return value if value else ""

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

    print(API.raw_request("a=useragent"))

    print(current_dump_day())


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
