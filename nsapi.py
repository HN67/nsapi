"""Core mechanisms and wrappers for interacting with the NS API
See https://www.nationstates.net/pages/api.html for NS API details
"""

# Allow for typing using not yet defined classes
from __future__ import annotations

# Import logging for logging
import logging

# Import typing for parameter/return typing
import typing
from typing import Dict, Generator, List, Iterable, Optional

# Import json and datetime to create custom cookie
import json
import datetime

# Import time for managing ratelimiting
import time

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


class RateLimiter:
    """Class that tracks counts and time to ensure safely staying below ratelimits
    Developed to work with the NS API rate limit, where NS returns the current
    number of requests, removing the need to manually count and retire requests.
    """

    def __init__(self, requestLimit: int, waitPeriod: int):

        self.requestLimit: int = requestLimit
        self.waitPeriod: int = waitPeriod

        # Timestamp that it will be safe to send another request at
        self.lockTime: float = 0
        # Current count, used to engage lock
        self.count: int = 0

    def set_count(self, count: int) -> None:
        """Set the count to a number, engages lock if exceeds limit"""
        # Copy count
        self.count = count
        # Check limit, if reached change lock time
        if self.count >= self.requestLimit:
            self.lockTime = time.time() + self.waitPeriod

    def wait(self) -> None:
        """Will wait until it is safe to send another request"""
        now = time.time()
        if now < self.lockTime:
            logging.info("Waiting to avoid ratelimit")
            time.sleep(self.lockTime - now)


class NSRequester:
    """Class to manage making requests from the NS API"""

    def __init__(self, userAgent: str):

        # Save user agent and construct headers object for later use
        self.headers = {"User-Agent": userAgent}

        # Create ratelimiter object
        self.rateLimiter = RateLimiter(40, 30)

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

    def retrieve_region_wa(self, region: str) -> Dict[str, List[str]]:
        """Collects live endorsement data for an entire region
        Can take a long time due to respecting NS API ratelimit
        """

    def request(self, api: str) -> str:
        """Returns the text retrieved from the specified NS api.
        Queries "https://www.nationstates.net/cgi-bin/api.cgi?"+<api>
        """
        # Prepare target (attaching the given api to NS's API page)
        target = "https://www.nationstates.net/cgi-bin/api.cgi?" + api
        # Wait on ratelimiter
        self.rateLimiter.wait()
        # Make request
        response = requests.get(target, headers=self.headers)
        # Update ratelimiter
        self.rateLimiter.set_count(int(response.headers["X-Ratelimit-Requests-Seen"]))
        # Return parsed text
        return response.text

    def shard_request(self, api: str, shards: Optional[Iterable[str]] = None) -> str:
        """Returns the raw text from the specified NS api
        Attaches the given shards to the `q` parameter, joined with `+`
        """
        # Prepare api string
        target = api + "&q="
        # Add shards if they exist
        if shards:
            target += "+".join(shards)
        # Return request
        return self.request(target)

    def xml_request(
        self, api: str, shards: Optional[Iterable[str]] = None
    ) -> etree.Element:
        """Makes a request using self.raw_request and tries to parse the result into XML node"""
        return etree.fromstring(self.shard_request(api, shards))

    def nation(self, nation: str) -> Nation:
        """Returns a Nation object using this requester"""
        return Nation(self, nation)

    def region(self, region: str) -> Region:
        """Returns a Region object using this requester"""
        return Region(self, region)

    def world(self) -> World:
        """Returns a World object using this requester"""
        return World(self)

    def wa(self, council: str = "1") -> WA:
        """Returns a WA object using this requester"""
        return WA(self, council)


class API:
    """Represents a live connection to the API of a NS model"""

    def __init__(self, requester: NSRequester, api: str, name: str) -> None:
        self.requester = requester
        self.api = api
        self.name = name

    def _key(self) -> str:
        """Determines the first key of the request, encodes the API and name"""
        return f"{self.api}={self.name}"

    def shards(self, *shards: str) -> Dict[str, str]:
        """Naively returns a Dict mapping from the shard name to the text of that element
        Connects to the `<api>=<name>&q=<shards>` page of the api
        Not all shards are one level deep, and as such have no text,
        but this method will only return the empty string, with no warning
        """
        return {
            node.tag.lower(): node.text if node.text else ""
            for node in self.requester.xml_request(self._key(), shards)
        }

    def shard(self, shard: str) -> str:
        """Naively returns the text associated with the shard node, which may be empty"""
        return self.shards(shard)[shard]


class Nation(API):
    """Represents a live connection to the API of a Nation on NS"""

    def __init__(self, requester: NSRequester, name: str) -> None:
        super().__init__(requester, "nation", name)

    def standard(self) -> NationStandard:
        """Returns a NationStandard object for this Nation"""
        return NationStandard(self.requester.xml_request(f"nation={self.name}"))


class Region(API):
    """Represents a live connection to the API of a Region on NS"""

    def __init__(self, requester: NSRequester, name: str) -> None:
        super().__init__(requester, "region", name)


class World(API):
    """Reperesnts a live connection the the API of the World on NS"""

    def __init__(self, requester: NSRequester) -> None:
        super().__init__(requester, "world", "")

    def _key(self) -> str:
        return ""


class WA(API):
    """Represents a live connection the the API of a WA Council on NS
    Defaults to General Assembly
    """

    def __init__(self, requester: NSRequester, council: str = "1") -> None:
        super().__init__(requester, "wa", council)


class Happening:
    """Class that represents a NS happening.
    There should be little need to manually instantiate this class,
    instead instances are returned by the World.happenings method.

    Attributes:
    self.id (int) - the event ID of the happening
    self.timestamp (Optional[int]) - the int timestamp the happening occured at
    self.text (str) - the raw text of the happening
    """

    def __init__(self, node: etree.Element) -> None:
        """Parse a happening from an XML format.
        Expects an EVENT node, as returned by NS api for happenings.
        (See https://www.nationstates.net/cgi-bin/api.cgi?q=happenings)
        Does not save a reference to the node.
        """
        self.id: int = int(node.attrib["id"])
        self.timestamp: Optional[int] = int(node[0].text) if node[0].text else None
        self.text: str = node[1].text if node[1].text else ""


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

    requester = NSRequester("HN67 API Reader")

    print(requester.request("a=useragent"))

    citizens = set(requester.wa().shard("members").split(",")) & set(
        requester.region("10000 islands").shard("nations").split(":")
    )
    print(len(citizens))

    print(requester.world().shard("happenings"))


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
