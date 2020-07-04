"""Core mechanisms and wrappers for interacting with the NS API
See https://www.nationstates.net/pages/api.html for NS API details
"""

# Allow for typing using not yet defined classes
from __future__ import annotations

# Standard library modules
# Code quality
import logging
from typing import Dict, Generator, Iterable, Mapping, Optional, Sequence, Set

# Utility
import dataclasses
import itertools

# Time modules
import datetime
import time

# File management
import gzip
import json
import os
import shutil

# Core libraries that support most of this module
import xml.etree.ElementTree as etree
import requests

# Set logging level
logging.basicConfig(level=logging.INFO)
# Reference logger
logger = logging.getLogger()

# Determine the root path for downloading and producing files
# Default on the file location, but if not existant for some reason
# then fall back on the current working directory
try:
    basePath = __file__
except NameError:
    basePath = os.getcwd()


def absolute_path(path: str) -> str:
    """Returns the absolute path of a given path based on this file"""
    return os.path.join(os.path.dirname(basePath), path)


def download_file(url: str, fileName: str, *, headers: Dict[str, str]) -> None:
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
    Should match the day of the latest archive dump
    Returns a naive date
    """
    utc = datetime.datetime.utcnow()
    logging.info("Current time is %s UTC", utc)
    return (
        utc.date() - datetime.timedelta(days=1)
        if utc.time().hour >= 7
        else utc.date() - datetime.timedelta(days=2)
    )


def last_dump_timestamp() -> int:
    """Returns the timestamp that the most recent data dump was generated at
    Any events after this timestamp were likely not included in the data dump
    Specifically, corresponds to the last 2200 PST or 0600 UTC
    """
    utc = datetime.datetime.utcnow()
    logging.info("Current time is %s UTC", utc)
    if utc.hour >= 6:
        utc = datetime.datetime.combine(utc.date(), datetime.time(hour=6))
    else:
        utc = datetime.datetime.combine(
            utc.date() - datetime.timedelta(days=1), datetime.time(hour=6)
        )
    return int(utc.timestamp())


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


def joined_parameter(*values: str) -> str:
    """Formats the given values into a single string to be passed as a parameter"""
    return "+".join(values)


def as_xml(data: str) -> etree.Element:
    """Parse the given data as XML and returns the root node"""
    return etree.fromstring(data)


def clean_format(string: str) -> str:
    """Casts the string to lowercase and replaces spaces with underscores"""
    return string.lower().replace(" ", "_")


class DumpManager:
    """Class to manage downloading and updating data dumps from NS API"""

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


class NSRequester:
    """Class to manage making requests from the NS API"""

    def __init__(self, userAgent: str):

        # Save user agent and construct headers object for later use
        self.headers = {"User-Agent": userAgent}

        # Create ratelimiter object
        self.rateLimiter = RateLimiter(40, 30)

    def dumpManager(self) -> DumpManager:
        """Returns a DumpManager with the same settings (such as userAgent) as this requester"""
        return DumpManager(self.headers["User-Agent"])

    def request(
        self, api: str, headers: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """Returns the text retrieved from the specified NS api.
        Queries "https://www.nationstates.net/cgi-bin/api.cgi?"+<api>
        Adds the given headers (if any) to the default headers of the this requester
        (such as user agent). Any conflicts will prioritize the parameter headers
        """
        # Prepare target (attaching the given api to NS's API page)
        target = "https://www.nationstates.net/cgi-bin/api.cgi?" + api
        # Logging
        logging.info("Requesting %s", target)
        # Wait on ratelimiter
        self.rateLimiter.wait()
        # Create headers
        if headers:
            # Combine dictionaries
            headers = {**self.headers, **headers}
        else:
            headers = self.headers
        # Make request
        response = requests.get(target, headers=headers)
        # Update ratelimiter
        self.rateLimiter.set_count(int(response.headers["X-Ratelimit-Requests-Seen"]))
        # Return parsed text
        return response

    def parameter_request(
        self, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> requests.Response:
        """Returns the response retrieved from the specified NS api.
        The api is constructed by passing the given key-value pairs as parameters
        """
        # Prepare query string
        query: str = "&".join(f"{key}={value}" for key, value in parameters.items())
        # Subcall default request method to use ratelimit, etc
        return self.request(query, headers=headers)

    def get_autologin(self, nation: str, password: str) -> str:
        """Attempts to authenticate with the given nation (using the ping shard)
        and returns the X-Autologin header value of the response if succsessful
        """
        response = self.parameter_request(
            headers={"X-Password": password}, nation=nation, q="ping"
        )
        return response.headers["X-Autologin"]

    def shard_request(
        self,
        shards: Optional[Iterable[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **parameters: str,
    ) -> requests.Response:
        """Returns the response from the specified NS api
        Attaches the given shards to the `q` parameter, joined with `+`
        """
        # Prepare api string
        # Create shard parameter if given
        if shards:
            return self.parameter_request(
                headers=headers, **parameters, q=joined_parameter(*shards)
            )
        return self.parameter_request(headers=headers, **parameters)
        # target = api + "&q="
        # # Add shards if they exist
        # if shards:
        #     target += "+".join(shards)
        # # Return request
        # return self.request(target)

    def nation(self, nation: str, auth: Optional[Auth] = None) -> Nation:
        """Returns a Nation object using this requester"""
        return Nation(self, nation, auth=auth)

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

    def _key(self) -> Dict[str, str]:
        """Determines the first key of the request, encodes the API and name"""
        return {self.api: self.name}

    def _headers(self) -> Dict[str, str]:
        """Returns various headers to add to a request, such as authentication"""
        return {}

    def shards_response(
        self, *shards: str, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> requests.Response:
        """Returns the Response returned from the `<api>=<name>&q=<shards>` page of the api
        """
        # Add extra headers if given
        if headers:
            headers = {**self._headers(), **headers}
        else:
            headers = self._headers()
        return self.requester.shard_request(
            shards, headers=headers, **self._key(), **parameters,
        )

    def shards_xml(
        self, *shards: str, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> Dict[str, etree.Element]:
        """Returns a Dict mapping from the shard name to the XML element returned
        Connects to the `<api>=<name>&q=<shards>` page of the api
        """
        return {
            node.tag.lower(): node
            for node in as_xml(
                self.shards_response(*shards, headers=headers, **parameters,).text
            )
        }

    def shards(
        self, *shards: str, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> Dict[str, str]:
        """Naively returns a Dict mapping from the shard name to the text of that element
        Uses the xml_shards method.
        Not all shards are one level deep, and as such have no text,
        but this method will only return the empty string, with no warning.
        Additional parameters can be passed using keyword arguments.
        """
        return {
            name: node.text if node.text else ""
            for name, node in self.shards_xml(
                *shards, headers=headers, **parameters
            ).items()
        }

    def shard(self, shard: str) -> str:
        """Naively returns the text associated with the shard node, which may be empty"""
        return self.shards(shard)[shard]


class Auth:
    """Handles producing headers to authenticate for NS API."""

    def __init__(self, autologin: Optional[str] = None, password: Optional[str] = None):
        """Can be constructed using at least one of an autologin or password.
        For security, autologin is recommended.
        An autologin can be obtained from a nation and password using
        NSRequester.get_autologin
        """
        # Must provide at least either autologin
        if autologin is None and password is None:
            raise ValueError("Auth must be provided with one of autologin or password")

        # Define attributes
        # Transform None to "" so that the headers can still be constructed,
        # they will just not authenticate
        if not autologin:
            autologin = ""
        self.autologin = autologin

        self.pin = ""

        if not password:
            password = ""

        self.password = password

    def headers(self) -> Dict[str, str]:
        """Returns authentication headers"""
        return {
            "X-Pin": self.pin,
            "X-Autologin": self.autologin,
            "X-Password": self.password,
        }

    def update(self, response: requests.Response) -> None:
        """Updates the auth with a response,
        notably provides it with the X-Pin header
        """
        # logging.info("Recieved headers %s", response.headers)
        # If a pin or autologin is returned, save it.
        # Autologin is provided when authenticating with password
        # Pin should be provided when authenticating with password/autologin
        if "X-Pin" in response.headers:
            self.pin = response.headers["X-Pin"]
        if "X-Autologin" in response.headers:
            self.autologin = response.headers["X-Autologin"]


class Nation(API):
    """Represents a live connection to the API of a Nation on NS"""

    def __init__(
        self, requester: NSRequester, name: str, auth: Optional[Auth] = None
    ) -> None:
        super().__init__(requester, "nation", name)
        self.auth = auth

        # Save the nationname, needed to cludged card method
        self.nationname = name

    def _headers(self) -> Dict[str, str]:
        """Important headers to add to every request
        In particular, auth headers
        """
        return self.auth.headers() if self.auth else {}

    def shards_response(
        self, *shards: str, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> requests.Response:
        """Returns the Response returned from the `<api>=<name>&q=<shards>` page of the api
        """
        # Inject auth updating, allows using pin
        logging.info("Making Nation request")
        response = super().shards_response(*shards, headers=headers, **parameters)
        if self.auth:
            self.auth.update(response)
        return response

    def login(self, autologin: str) -> Auth:
        """Replaces this Nation's Auth with a new one based on the autologin.
        Returns the Auth to potentially allow for other API objects to use.
        Does not actually make an API request.
        """
        self.auth = Auth(autologin)
        return self.auth

    def ping(self) -> bool:
        """Makes a ping API request to this nation, registering a login (for activity)."""
        # consider 200 to be successful
        response = self.shards_response("ping")
        return response.status_code == 200

    def standard(self) -> NationStandard:
        """Returns a NationStandard object for this Nation"""
        return NationStandard(
            as_xml(self.requester.parameter_request(nation=self.name).text)
        )

    def dossier(self) -> Dossier:
        """Returns a Dossier representing the dossier of this nation"""
        nodes = self.shards_xml("dossier", "rdossier")
        return Dossier(dossier=nodes["dossier"], rdossier=nodes["rdossier"])

    def deck(self) -> Iterable[Card]:
        """Returns a iterable of the cards currently owned by this nation"""
        # for some reason cards are treated quite different by NS api currently
        # so we cant simply make a shards call. for now we make a direct call
        # to the requester shards_xml method, since it does not insert the
        # `nation=name` parameter
        # this request returns a <CARDS><DECK><CARD/>...</DECK><CARDS> structure,
        # so we immedietly retrieve the DECK node (which contains multiple CARD nodes)
        # with [0]
        deck = as_xml(
            self.requester.shard_request(
                shards=["cards", "deck"], nationname=self.nationname
            ).text
        )[0]
        return [Card.from_xml(node) for node in deck]

    def issues(self) -> Iterable[Issue]:
        """Returns an iterable of the Issues this nation currently has.
        Requires authentication.
        """
        # Make request
        issues = self.shards_xml("issues")["issues"]
        # Return boxed Issues (may crash badly if authentication failed)
        return [Issue.from_xml(node) for node in issues]

    def answer_issue(self, issue: int, option: int) -> etree.Element:
        """Answers the specified issue (by id) with the specified option (by id).
        Requires authentication.
        Returns the XML describing the results of the action.
        Note that the XML node returned is called ISSUE, but is fundamentally
        different than the ISSUE node that represents a comprehensive issue and is
        used to create a Issue object, rather, it contains data on the effects of
        the chosen issue option.
        """
        issueEffect = self.shards_xml(c="issue", issue=str(issue), option=str(option))[
            "issue"
        ]
        return issueEffect

    def gift_card(self, cardid: int, season: int, to: str) -> None:
        """Attempts to gift the specified card (by id and season)
        to the receiving nation (by name 'to').
        Requires authentication.
        May badly fail if the sending nation does not have sufficient bank.
        """
        self.execute_command(
            command="giftcard", cardid=str(cardid), season=str(season), to=to
        )

    def execute_command(self, command: str, **parameters: str) -> etree.Element:
        """Executes the specified command, using any given parameters.
        Automatically handles the double-request method required by the NS API.
        This method should not be used for answering issues, since
        that does not use the double-request method.
        Returns the root xml node returned by the succsesful command.
        """
        # Prepare command
        # Need to specify no extra headers cause otherwise its funky
        # even though the headers param is supposed to be optional
        # (the ** splat causes the funkiness i think)
        prepare = self.shards_response(
            c=command, headers=None, mode="prepare", **parameters
        )
        # response Returns <NATION id="name"><SUCCESS/ERROR></SUCCESS/ERROR></NATION> format
        # we should probably throw an error if SUCCESS is not returned,
        # but too lazy / not sure what kind of error to throw
        # (should maybe create a custom tree?)
        node = as_xml(prepare.text)[0]
        if node.tag != "SUCCESS":
            raise ValueError(
                f"Command 'command={command}' {parameters} was not succesful."
                f" Got message: '{node.text}'"
            )
        token = node.text if node.text else ""
        # Execute command using the returned token
        execute = self.shards_response(
            c=command, headers=None, mode="execute", token=token, **parameters
        )
        return as_xml(execute.text)


class Region(API):
    """Represents a live connection to the API of a Region on NS"""

    def __init__(self, requester: NSRequester, name: str) -> None:
        super().__init__(requester, "region", name)


class World(API):
    """Reperesnts a live connection the the API of the World on NS"""

    def __init__(self, requester: NSRequester) -> None:
        super().__init__(requester, "world", "")

    def _key(self) -> Dict[str, str]:
        return {}

    def _happenings_root(
        self, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> etree.Element:
        """Returns the NS API happenings query root element"""
        return self.shards_xml(
            "happenings", headers=headers, **self._key(), **parameters
        )["happenings"]

    def happenings(
        self,
        safe: bool = True,
        headers: Optional[Dict[str, str]] = None,
        **parameters: str,
    ) -> Iterable[Happening]:
        """Queries the NS happenings api shard, appending any given parameters.
        Returns the data as a sequence of Happening objects.
        If `safe` is true, there is a hard limit of 100 happenings (inherited from NS API).
        If `safe` is false, it will keep requesting until it receives a response
        with < 100 happenings, since 100 likely indicates the enforced max.
        Note that with poorly designed parameters (such as only beforetime),
        in unsafe mode this method can potentially make a huge number of requests,
        essentially freezing the program.
        """
        root = self._happenings_root(headers=headers, **parameters)
        rootList = [root]
        # 100 is the max number of happenings that the request will return
        # however, this is a bit of magic number and should be fixed
        while not safe and len(root) == 100:
            root = self._happenings_root(
                headers=headers, **parameters, beforeid=str(Happening(root[-1]).id)
            )
            rootList.append(root)
        # https://docs.python.org/2/library/itertools.html#itertools.chain
        return (Happening(node) for node in itertools.chain.from_iterable(rootList))


class WA(API):
    """Represents a live connection the the API of a WA Council on NS
    Defaults to General Assembly
    """

    def __init__(self, requester: NSRequester, council: str = "1") -> None:
        super().__init__(requester, "wa", council)


class Dossier:
    """Class that represents a NS nation's dossier
    May contain nation, region, or both, records,
    depending on the XML element used to construct this.
    Objects are usually obtained from the Nation.dossier method

    Attributes:
    self.dossier: A collection of nations
    self.rdossier: A collection of regions
    """

    def __init__(self, dossier: etree.Element, rdossier: etree.Element) -> None:
        """Parses DOSSIER and/or RDOSSIER nodes, as returned by NS api nation shards.
        (See https://www.nationstates.net/cgi-bin/api.cgi?nation=testlandia&q=dossier+rdossier)
        (Requires auth, see https://www.nationstates.net/pages/api.html#authenticating)
        Does not save references to the nodes
        """
        # [R]DOSSIER nodes are simply nodes with nations/regions as children, with names as text
        self.dossier: Set[str] = set(node.text if node.text else "" for node in dossier)
        self.rdossier: Set[str] = set(
            node.text if node.text else "" for node in rdossier
        )


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


@dataclasses.dataclass(frozen=True)
class Card:
    """Class that represents a NS trading card.
    Can be created from a node, or is returned by shards such as nation decks
    """

    id: int
    category: str
    season: str

    @classmethod
    def from_xml(cls, node: etree.Element) -> Card:
        """Parses a Card from XML format.
        Expects a CARD node, as returned by NS api for nation decks or card info
        (See https://www.nationstates.net/cgi-bin/api.cgi?q=cards+deck;nationname=testlandia)
        Does not save a reference to the node.
        0 or empty string indicate that the given node did not have that data
        """
        return cls(
            int(node[0].text) if node[0].text else 0,
            node[1].text if node[1].text else "",
            node[2].text if node[2].text else "",
        )


# TODO fix this, apparently some issues dont have pic1/pic2, which completely breaks the options
@dataclasses.dataclass()
class Issue:
    """Class that represents a NS Issue"""

    id: int
    title: str
    text: str
    author: str
    editors: Sequence[str]
    pic1: str
    pic2: str
    options: Mapping[int, str]

    @classmethod
    def from_xml(cls, node: etree.Element) -> Issue:
        """Creates an Issue from an XML ISSUE node
        (See https://www.nationstates.net/cgi-bin/api.cgi?nation=testlandia&q=issues)
        """
        return cls(
            id=int(node.attrib["id"]),
            title=node[0].text if node[0].text else "",
            text=node[1].text if node[1].text else "",
            author=node[2].text if node[2].text else "",
            editors=node[3].text.split(", ") if node[3].text else [],
            pic1=node[4].text if node[4].text else "",
            pic2=node[5].text if node[5].text else "",
            options={
                int(sub.attrib["id"]): (sub.text if sub.text else "")
                for sub in node[6:]
                if sub.tag == "OPTION"
            },
        )


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

    requester: NSRequester = NSRequester("HN67 API Reader")
    print(requester.request("a=useragent").text)


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
