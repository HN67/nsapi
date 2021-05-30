"""Core mechanisms and wrappers for interacting with the NS API
See https://www.nationstates.net/pages/api.html for NS API details
"""

# Reconsider absolute_path:
# Linking everything to a __file__ based path has several problems,
# in that it works well when nsapi.py is a script, but gives the user less control than cwd
# essentially trades control for convience (not all users may understand cwd)
# Users not understanding cwd is unlikely to be a problem; e.g. running a script
# on windows by double clicking it typically makes the cwd the location of the script
# If a user ends up using cmd, cwd will still be somewhere sane (user root?) unless in administrator
# output files should probably be largely put into cwd, but perhaps __file__ is better
# for data files that the end user doesnt need to see.
# However, it can break completely when doing things such as compiling with pyinstaller,
# and probably wont work if trying to make a package.
# The probably conclusion is that abs_path is useful for scripts, but not the kind
# of package/library nsapi is becoming.
# A related concept is the data dumps, since they produce the most files (at decently large ones).
# Ideally, there should be an easy way to remove a dump, maybe automatically?
# Not sure how that would look, maybe once its done iterating it removes it.

# Allow for typing using not yet defined classes
from __future__ import annotations

# Standard library modules
# Code quality
import logging
import typing as t
from typing import (
    Callable,
    Collection,
    Container,
    Dict,
    Generator,
    Generic,
    Iterable,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    Set,
    Type,
    TypeVar,
)

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

# Basic type var used for generics
T = TypeVar("T")

# Setup logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def configure_logger(
    loggerObject: logging.Logger,
    *,
    level: t.Union[int, str] = logging.WARNING,
    force: bool = True,
) -> logging.Logger:
    """Performs standard configuration on the provided logger.

    Can be used to configure this modules logger or any user modules logger.

    Adds a default stream handler with a format string containing level, name, and message.

    Returns the logger passed.
    """
    # Add formatted handler
    FORMAT_STRING = "%(levelname)s - %(name)s - %(message)s"
    # Only add the handler if forced or none exist
    if force or len(loggerObject.handlers) == 0:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(FORMAT_STRING))
        loggerObject.addHandler(handler)
    # Set logging level
    loggerObject.setLevel(level)
    # Chain object
    return loggerObject


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


def download_file(url: str, fileName: str, *, headers: Mapping[str, str]) -> None:
    """Downloads a file from <url> to the location specified by <fileName>"""
    # Open request to url
    logger.info("Starting download of <%s> to <%s>", url, fileName)
    with requests.get(url, stream=True, headers=headers) as r:
        # Open file in write-byte mode
        with open(fileName, "wb") as f:
            # Copy data
            shutil.copyfileobj(r.raw, f)
    logger.info("Finished download of <%s> to <%s>", url, fileName)


def current_dump_day() -> datetime.date:
    """Calculates the latest day available for the data dump.
    A datadump is generated ~2230 PST for that day, so the dump will be considered
    available at 2300 PST or 0700 UTC the next day.
    Should match the day of the latest archive dump
    Returns a naive date
    """
    utc = datetime.datetime.utcnow()
    logger.info("Current time is %s UTC", utc)
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
    logger.info("Current time is %s UTC", utc)
    if utc.hour >= 6:
        utc = datetime.datetime.combine(utc.date(), datetime.time(hour=6))
    else:
        utc = datetime.datetime.combine(
            utc.date() - datetime.timedelta(days=1), datetime.time(hour=6)
        )
    return int(utc.timestamp())


class RateLimiter:
    """
    Class that keeps track of counts and time to ensure safely staying below a ratelimit.
    The update method will "lock" the ratelimiter for a certain amount of time based on conditions,
    and the wait method will cause a (blocking) delay until the lock expires.
    Developed to work with the NS API rate limit, where NS returns the current
    number of requests, removing the need to manually count and retire requests.
    However, this class can be used for any ratelimit task, especially simple ones.
    .update should be called after each action, and .wait before each action.
    """

    def __init__(self, requestLimit: int, cooldownPeriod: float, spacePeriod: float):
        """Constructs a RateLimiter using direct arguments.
        requestLimit: The maximum number of requests to allow; meeting this target with the count in
        .update will cause the ratelimiter to lock for the cooldownPeriod.
        cooldownPeriod: The period (in seconds) to wait if limit is reached.
        spacePeriod: The period (in seconds) to lock by default after each update.
        (Unless cooldown is engaged)
        """

        self.requestLimit: int = requestLimit
        self.cooldownPeriod: float = cooldownPeriod
        self.spacePeriod: float = spacePeriod

        # Timestamp that it will be safe to send another request at
        self.lockTime: float = 0
        # Current count, used to engage lock
        self.count: int = 0

    def update(self, count: Optional[int]) -> None:
        """Updates the ratelimiter, usually updating the lock.
        Optionally takes a count to check against the maximum limit,
        engaging the cooldown if neccesary.
        """
        # Copy count if provided
        if count:
            self.count = count
        # Check limit, if reached wait for the full cooldown
        if self.count >= self.requestLimit:
            self.lockTime = time.time() + self.cooldownPeriod
        # Otherwise just lock for the space period
        else:
            self.lockTime = time.time() + self.spacePeriod

    def wait(self) -> None:
        """Will wait until it is safe to send another request"""
        now = time.time()
        if now < self.lockTime:
            diff = self.lockTime - now
            logger.debug("Waiting %ss to avoid ratelimit", diff)
            time.sleep(diff)


def joined_parameter(*values: str) -> str:
    """Formats the given values into a single string to be passed as a parameter"""
    return "+".join(values)


def as_xml(data: str) -> etree.Element:
    """Parse the given data as XML and returns the root node"""
    try:
        return etree.fromstring(data)
    except etree.ParseError as error:
        raise ValueError(
            f"Tried to parse malformed data as XML. Error: {error}, Got data: '{data}'"
        ) from error


def clean_format(string: str) -> str:
    """Casts the string to lowercase and replaces spaces with underscores"""
    return string.lower().replace(" ", "_")


@dataclasses.dataclass()
class Resource:
    """Class that describes a retrievable resource."""

    source: str
    name: str

    def outdated(
        self,
        previous: datetime.datetime,  # pylint: disable=unused-argument
        current: Optional[datetime.datetime] = None,  # pylint: disable=unused-argument
    ) -> bool:
        """Determines whether the Resource is outdated.

        Always returns False on base class.

        Based on comparing the current time to the previous time
        (i.e. when the resource was previously retrieved).
        Current defaults to now.
        """
        return False


@dataclasses.dataclass()
class DailyResource(Resource):
    """Describes a resource that updates daily at a certain time."""

    updateTime: datetime.time = datetime.time()

    def outdated(
        self, previous: datetime.datetime, current: Optional[datetime.datetime] = None
    ) -> bool:
        """Determines whether the Resource is outdated.

        The Resource is considered outdated if current falls on or after
        the first updateTime that occurs after previous.

        current defaults to (naive) utc now.
        """

        if current is None:
            current = datetime.datetime.utcnow()

        # Get the next datetime after previous that has the desired time
        nextUpdate = datetime.datetime.combine(previous.date(), self.updateTime)
        if nextUpdate < previous:
            nextUpdate += datetime.timedelta(days=1)

        return current >= nextUpdate


class ResourceManager:
    """Class to manage the downloading and updating of Resources."""

    def __init__(
        self, markerFile: str, headers: Optional[Mapping[str, str]] = None
    ) -> None:
        """Headers can optionally be provided that will be used in download requests."""

        self.markerFile = markerFile

        if headers is not None:
            self.headers = headers
        else:
            self.headers = {}

    def resolve(self, resource: Resource, target: str = None) -> str:
        """Returns target if provided, else a constructed path from Resource name.

        If target is truthy (i.e. not None or empty), it is returned unchanged.
        Otherwise, returns a path constructed by calling absolute_path(resource.name).
        """
        return target or absolute_path(resource.name)

    def download(self, resource: Resource, target: str = None) -> None:
        """Downloads the given resource by assuming the source is a HTTP URL.

        Saves to the resolved path (self.resolve) of the resource and target.
        """
        download_file(
            resource.source, self.resolve(resource, target), headers=self.headers
        )

    def verify(self, resource: Resource, target: str = None) -> None:
        """Verifies the resource exists, downloading if needed.

        Checks the resolved path for a file, if it doesnt exist, downloads
        from the source of the resource.
        """
        if not os.path.isfile(self.resolve(resource, target)):
            logger.info("File does not exist, downloading.")
            self.download(resource, target)

    def update(self, resource: Resource, target: str = None) -> None:
        """Downloads the resource only if certain conditions are met,
        i.e. the file doesn't already exist or it is outdated.

        When working with multiple resources, they should each have unique names,
        otherwise there could be collisions with tracking age.
        """

        # Notify of downloading
        logger.info("Checking resource timestamp marker.")
        try:
            # Try loading marker
            with open(self.markerFile, "r") as f:
                marker = json.load(f)
        except FileNotFoundError:
            # Download if marker does not exist
            logger.info("Marker file does not exist, downloading file.")
            self.download(resource, target)
            # Create marker
            marker = {resource.name: datetime.datetime.utcnow().isoformat()}
        else:
            # Check timestamp, redownload data if outdated
            if resource.name not in marker or resource.outdated(
                datetime.datetime.fromisoformat(marker[resource.name])
            ):
                logger.info("Marker shows outdated timestamp, redownloading file.")
                # Write to the file
                self.download(resource, target)
                # Update timestamp
                marker[resource.name] = datetime.datetime.utcnow().isoformat()
            else:
                # Verify that dump exists
                self.verify(resource, target)

        # Save the marker
        with open(self.markerFile, "w") as f:
            json.dump(marker, f)


class APIError(Exception):
    """Error interacting with NationStates API."""


class AuthError(APIError):
    """Error with authentication for NS API."""


class ResourceError(APIError, ValueError):
    """Error with retrieving a resource from NS API."""


class DumpManager:
    """Specific class to manage downloading and updating data dumps from NS API"""

    generationTime = datetime.time(hour=6)

    resources = {
        "regions": DailyResource(
            "https://www.nationstates.net/pages/regions.xml.gz",
            "regions.xml.gz",
            generationTime,
        ),
        "nations": DailyResource(
            "https://www.nationstates.net/pages/nations.xml.gz",
            "nations.xml.gz",
            generationTime,
        ),
        "cardlist_S1": Resource(
            "https://github.com/HN67/nsapi/raw/master/resources/cardlist_S1.xml.gz",
            "cardlist_S1.xml.gz",
        ),
        "cardlist_S2": Resource(
            "https://github.com/HN67/nsapi/raw/master/resources/cardlist_S2.xml.gz",
            "cardlist_S2.xml.gz",
        ),
    }

    @staticmethod
    def archived_dump(date: datetime.date, dump: str) -> Resource:
        """Constructs a resource for the archived dump.

        dump should be either 'regions' or 'nations'.
        """
        name = f"{date.isoformat()}-{dump}-xml.gz"
        source = f"https://www.nationstates.net/archive/{dump}/{name}"

        # Archive dumps are static
        return Resource(source, name)

    def __init__(self, userAgent: str, markerFile: str = "marker.json"):

        self.resourceManager = ResourceManager(
            markerFile, headers={"User-Agent": userAgent}
        )

    def retrieve(self, resource: Resource, location: str = None) -> etree.Element:
        """Returns the XML root node of the given dump,
        looking in the specified location (calculated with ResourceManager.resolve).
        """

        logger.info("Parsing XML tree")
        # Attempt to load the data
        with gzip.open(self.resourceManager.resolve(resource, location)) as dump:
            xml = etree.parse(dump).getroot()

        # Return the xml
        logger.info("XML document retrieval and parsing complete")
        return xml

    def retrieve_iterator(
        self,
        resource: Resource,
        location: str = None,
        tags: Optional[Container[str]] = None,
    ) -> Generator[etree.Element, None, None]:
        """Iteratively traverses the dump,
        without storing the entirety in memory simultaneously.
        Will only yield nodes who's tag is in the given container.
        If `tags` is None, every node is returned (including a empty root node).
        """

        logger.info("Iteratively parsing XML")
        # Attempt to load the data
        with gzip.open(self.resourceManager.resolve(resource, location)) as dump:

            # Looking for start events allows us to retrieve
            # the starting, parent, element using the `next()` call.
            iterator = etree.iterparse(dump, events=("start", "end"))
            # We get the root so that we can clear from it, removing
            # xml nodes references after they have been yielded.
            _, root = next(iterator)

            # Yield elements
            for event, element in iterator:
                # `end` signifies the element is fully parsed
                # the right conjunct is true if tags is None
                # or the element tag is in the set
                if event == "end" and ((not tags) or element.tag in tags):
                    yield element
                    root.clear()

    def _named_daily_dump(
        self,
        resourceName: str,
        tagName: str,
        parser: Type[SParser],
        date: datetime.date = None,
        location: str = None,
        update: bool = True,
    ) -> Generator[SParser, None, None]:
        """Iteratively parses each object in a dump.

        See .nations or .regions for more info.
        """

        if date is None:
            resource = self.resources[resourceName]
        else:
            resource = self.archived_dump(date, resourceName)

        if update:
            self.resourceManager.update(resource, location)
        else:
            self.resourceManager.verify(resource, location)

        return (
            parser.from_xml(node)
            for node in self.retrieve_iterator(resource, location, tags={tagName})
        )

    def nations(
        self, date: datetime.date = None, location: str = None, update: bool = True
    ) -> Generator[NationStandard, None, None]:
        """Iteratively parses each nation in the most recent dump.
        Checks for the dump in the given location, which defaults to `nations.xml.gz`.
        If `update` is true (the default), the dump will be redownloaded if it is outdated,
        otherwise it will only be downloaded if it doesnt exist.
        Note that archive dumps will never be outdated.
        """
        return self._named_daily_dump(
            "nations",
            "NATION",
            NationStandard,
            date=date,
            location=location,
            update=update,
        )

    def regions(
        self, date: datetime.date = None, location: str = None, update: bool = True
    ) -> Generator[RegionStandard, None, None]:
        """Iteratively parses each region in the most recent dump.
        Checks for the dump in the given location, which defaults to `regions.xml.gz`.
        If `update` is true (the default), the dump will be redownloaded if it is outdated,
        otherwise it will only be downloaded if it doesnt exist.
        Note that archive dumps will never be outdated.
        """
        return self._named_daily_dump(
            "regions",
            "REGION",
            RegionStandard,
            date=date,
            location=location,
            update=update,
        )

    def cards(
        self, season: str, location: str = None
    ) -> Generator[CardStandard, None, None]:
        """Iteratively parses each card in the specified season dump.
        Checks for the dump in the given location, which defaults to `cardlist_S{season}.xml.gz`.
        Will download if not found (but wont update every day since the list is static).
        Note that the automatic download from the NS API will likely not work, since it contains
        malformed XML and characters.
        """
        resource = self.resources[f"cardlist_S{season}"]
        self.resourceManager.verify(resource, location)

        return (
            CardStandard.from_xml(node)
            for node in self.retrieve_iterator(resource, location, tags={"CARD"})
        )


class NSRequester:
    """Class to manage making requests from the NS API"""

    def __init__(self, userAgent: str):

        # Save user agent and construct headers object for later use
        self.headers = {"User-Agent": userAgent}

        # Create ratelimiter object
        self.rateLimiter = RateLimiter(
            requestLimit=49, cooldownPeriod=35, spacePeriod=0.65
        )

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
        # Create headers
        if headers:
            # Combine dictionaries
            headers = {**self.headers, **headers}
        else:
            headers = self.headers
        # Wait on ratelimiter
        self.rateLimiter.wait()
        # Logging
        logger.info("Requesting %s", target)
        # Make request
        response = requests.get(target, headers=headers)
        # Update ratelimiter
        self.rateLimiter.update(int(response.headers["X-Ratelimit-Requests-Seen"]))
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

    def card(self, cardid: int, season: str) -> Card:
        """Returns a Card object using this requester"""
        return Card(self, cardid, season)


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
        # logger.info("Recieved headers %s", response.headers)
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
        # logger.info("Making Nation request")
        response = super().shards_response(*shards, headers=headers, **parameters)
        # response.ok is true iff status_code < 400
        if not response.ok:
            if response.status_code == 404:
                raise ResourceError(f"Nation '{self.nationname}' does not exist.")
            elif response.status_code == 403:
                raise AuthError(f"Authentication failed for '{self.nationname}'.")
            else:
                raise APIError(f"Error with retrieving info for '{self.nationname}'.")
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

    def get_autologin(self) -> str:
        """Returns the autologin for this nation.
        If this Nation's Auth already has an autologin, it is returned,
        otherwise an authenticated request is made to retrieve it.
        """
        # The lack of autologin is represented by empty string
        if self.auth:
            # Retrieve autologin if neccesary
            if self.auth.autologin == "":
                # Ping will cause this Nation to run shards_response, updating the auth
                success = self.ping()
                # If ping unsuccseful, raise informative message
                if not success:
                    raise ValueError(
                        "Authentication failed, probably incorrect password."
                    )
            # Return autologin
            return self.auth.autologin
        # Not authenticated at all, raise error probably
        raise TypeError(
            "Nation object does not have an Auth, can't retrieve autologin."
        )

    def standard(self) -> NationStandard:
        """Returns a NationStandard object for this Nation"""
        return NationStandard.from_xml(
            as_xml(self.requester.parameter_request(nation=self.name).text)
        )

    def wa(self) -> str:
        """Returns the WA status of this Nation"""
        return self.shards("wa")["unstatus"]

    def dossier(self) -> Dossier:
        """Returns a Dossier representing the dossier of this nation"""
        nodes = self.shards_xml("dossier", "rdossier")
        return Dossier(dossier=nodes["dossier"], rdossier=nodes["rdossier"])

    def censuses(self, *scales: int) -> Mapping[int, Census]:
        """Returns a mapping of all requested census scales.

        If no scales are provided, defaults to all existing census scales.
        """
        return {
            # Map id to the whole census object
            census.id: census
            # The dict is created from a generating parsing the nodes
            for census in (
                Census.from_xml(node)
                # an XML node can be used as an iterator, where it yields children
                for node in self.shards_xml(
                    "census",
                    # we want to grab all the values, since a Census requires them
                    mode=joined_parameter("score", "rank", "rrank", "prank", "prrank"),
                    # gets all the different stats for us
                    scale=joined_parameter(*(str(scale) for scale in scales))
                    if scales
                    else "all",
                )["census"]
            )
        }

    def cards_xml(self, *shards: str) -> Mapping[str, etree.Element]:
        """Seperate method to make requests to the cards apis associated with a nation,
        since its different than the nation api.
        """
        # The cards are actually attached to
        # the world (or no) api, so we take advantage of that.
        return self.requester.world().shards_xml(
            "cards", *shards, nationname=self.nationname
        )

    def deck(self) -> Iterable[CardIdentifier]:
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
        return [CardIdentifier.from_xml(node) for node in deck]

    def deck_info(self) -> DeckInfo:
        """Returns a DeckInfo object containing the deck info of this nation"""
        return DeckInfo.from_xml(self.cards_xml("info")["info"])

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

    def nations(self) -> Collection[str]:
        """Returns a collection of the member nations of this region."""
        return self.shard("nations").split(":")


class World(API):
    """Reperesnts a live connection the the API of the World on NS"""

    def __init__(self, requester: NSRequester) -> None:
        super().__init__(requester, "world", "")

        # Maximum number of happenings returned by happenings shard in one response
        self.happeningsResponseLimit = 100

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
        while not safe and len(root) == self.happeningsResponseLimit:
            root = self._happenings_root(
                headers=headers, **parameters, beforeid=str(Happening(root[-1]).id)
            )
            rootList.append(root)
        # https://docs.python.org/2/library/itertools.html#itertools.chain
        return (Happening(node) for node in itertools.chain.from_iterable(rootList))

    def regions_by_tag(self, *tags: str) -> Iterable[str]:
        """Returns an iterable of the names of all regions,
        filtered by the tags provided.

        Use the syntax '-tag' to omit regions with that tag
        instead of include.

        Wraps the API provideded by
        'https://www.nationstates.net/cgi-bin/api.cgi?q=regionsbytag;tags='
        """
        node = self.shards_xml("regionsbytag", tags=",".join(tags))["regions"]
        text = node.text if node.text else ""
        return text.split(",")


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


class Card(API):
    """NS API object for card-related requests"""

    def __init__(self, requester: NSRequester, cardid: int, season: str) -> None:
        """A Card is identified by its id and the season."""
        # Kinda messy here. We could pass `"cardid"` and `cardid` as the api and name,
        # but still need to inject season somehow, and it would probably be more confusing
        # if the two were split up, so both are jammed in the overridden _key method
        # Should API be extended to handle multiple keys? maybe, maybe not.
        super().__init__(requester, "card", "")

        self.id = cardid
        self.season = season

        # The maximum number of trades returned by the trade shard in one request
        self.tradeResponseLimit = 50

    # Injected into super .shard_response as parameters
    def _key(self) -> Dict[str, str]:
        return {"cardid": str(self.id), "season": self.season}

    def shards_response(
        self, *shards: str, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> requests.Response:
        # Injects an extra shard, i.e. `card`
        return super().shards_response("card", *shards, headers=headers, **parameters)

    def _trades_root(
        self, headers: Optional[Dict[str, str]] = None, **parameters: str
    ) -> etree.Element:
        """Returns the NS API trades query root element"""
        return self.shards_xml("trades", headers=headers, **parameters)["trades"]

    def trades(
        self,
        safe: bool = True,
        headers: Optional[Dict[str, str]] = None,
        **parameters: str,
    ) -> Iterable[Trade]:
        """Queries the NS trades api shard of this card, appending any given parameters.
        Returns the data as a sequence of Trade objects.
        If `safe` is true, there is a hard limit of 50 trades (inherited from NS API).
        If `safe` is false, it will keep requesting until it receives a response
        with < 50 trades, since 50 likely indicates the enforced max.
        Omitting a lower bound (i.e. beforetime) will likely cause it to return
        all historical trades, which could potentially be a large number of requests,
        blocking the program.
        """
        root = self._trades_root(headers=headers, **parameters)
        rootList = [root]
        while not safe and len(root) == self.tradeResponseLimit:
            root = self._trades_root(
                headers=headers,
                **parameters,
                beforetime=str(Trade.from_xml(root[-1]).timestamp),
            )
            rootList.append(root)
        # https://docs.python.org/2/library/itertools.html#itertools.chain
        return (
            Trade.from_xml(node) for node in itertools.chain.from_iterable(rootList)
        )


@dataclasses.dataclass(frozen=True)
class CardIdentifier:
    """Class that identifies a NS trading card.
    Can be created from a node, or is returned by shards such as nation decks
    """

    id: int
    rarity: str
    season: str

    @classmethod
    def from_xml(cls, node: etree.Element) -> CardIdentifier:
        """Parses a Card from XML format.
        Expects a CARD node, as returned by NS api for nation decks or card info
        (See https://www.nationstates.net/cgi-bin/api.cgi?q=cards+deck;nationname=testlandia)
        Does not save a reference to the node.
        0 or empty string indicate that the given node did not have that data
        """
        return cls(
            id=int(node[0].text) if node[0].text else 0,
            rarity=node[1].text if node[1].text else "",
            season=node[2].text if node[2].text else "",
        )


@dataclasses.dataclass(frozen=True)
class CardInfo:
    """Class that contains info on a NS Card.
    (Such as https://www.nationstates.net/cgi-bin/api.cgi?q=card+info;cardid=1;season=1).
    """

    id: int
    rarity: str
    season: str

    flag: str
    government: str
    marketValue: float
    name: str
    region: str

    slogan: str
    classification: str

    @classmethod
    def from_xml(cls, node: etree.Element) -> CardInfo:
        """Constructs a CardInfo object from a XML CARD node.
        See https://www.nationstates.net/cgi-bin/api.cgi?q=card+info;cardid=1;season=1
        """
        data = NodeParse(node)
        return cls(
            id=int(data.simple("CARDID")),
            rarity=data.simple("CATEGORY"),
            season=data.simple("SEASON"),
            flag=data.simple("FLAG"),
            government=data.simple("GOVT"),
            marketValue=int(data.simple("MARKET_VALUE")),
            name=data.simple("NAME"),
            region=data.simple("REGION"),
            slogan=data.simple("SLOGAN"),
            classification=data.simple("TYPE"),
        )

    def identifier(self) -> CardIdentifier:
        """Returns a CardIdentifier that is a subset of this CardInfo.
        Creates the CardIdentifier by copying the respective attributes from
        this CardInfo.
        """
        return CardIdentifier(id=self.id, rarity=self.rarity, season=self.season)


@dataclasses.dataclass(frozen=True)
class CardStandard:
    """Class that contains the info on a card that is included in a data dump."""

    id: int
    name: str
    rarity: str

    classification: str
    motto: str
    region: str

    government: str

    flag: str
    description: str

    badges: Sequence[str]
    trophies: Mapping[str, int]

    @classmethod
    def from_xml(cls, node: etree.Element) -> CardStandard:
        """Constructs a CardStandard using a CARD element from the cards dump,
        see https://www.nationstates.net/pages/api.html#dumps and
        https://www.nationstates.net/pages/cardlist_S2.xml.gz.
        """
        data = NodeParse(node)
        return cls(
            id=int(data.simple("ID")),
            name=data.simple("NAME"),
            rarity=data.simple("CARDCATEGORY"),
            classification=data.simple("TYPE"),
            motto=data.simple("MOTTO"),
            region=data.simple("REGION"),
            government=data.simple("CATEGORY"),
            flag=data.simple("FLAG"),
            description=data.simple("DESCRIPTION"),
            badges=sequence(data.first("BADGES"), key=content),
            trophies={
                child.get("type", default=""): int(content(child))
                for child in data.first("TROPHIES")
            },
        )


@dataclasses.dataclass(frozen=True)
class Trade:
    """Class that represents the trade of a NS trading card"""

    buyer: str
    seller: str

    price: float
    timestamp: int

    @classmethod
    def from_xml(cls, node: etree.Element) -> Trade:
        """Constructs a Trade from a XML TRADE node, as seen in
        https://www.nationstates.net/cgi-bin/api.cgi?q=card+trades;cardid=1;season=1
        """
        data = NodeParse(node)
        return cls(
            buyer=data.simple("BUYER"),
            seller=data.simple("SELLER"),
            price=0 if data.simple("PRICE") == "" else float(data.simple("PRICE")),
            timestamp=int(data.simple("TIMESTAMP")),
        )


@dataclasses.dataclass()
class DeckInfo:
    """Class that contains the info returned by the deck info shard.
    (i.e. https://www.nationstates.net/cgi-bin/api.cgi?q=cards+info;nationname=testlandia)
    """

    bank: float
    deckCapacity: int
    deckValue: float

    id: int

    lastPackOpened: Optional[int]
    lastValued: Optional[int]

    name: str
    numCards: int
    rank: int
    regionRank: int

    @classmethod
    def from_xml(cls, node: etree.Element) -> DeckInfo:
        """Creates a DeckInfo object using a XML node, such as returned by
        https://www.nationstates.net/cgi-bin/api.cgi?q=cards+info;nationname=testlandia
        """
        data = NodeParse(node)
        return cls(
            bank=float(data.simple("BANK")),
            deckCapacity=int(data.simple("DECK_CAPACITY_RAW")),
            deckValue=float(data.simple("DECK_VALUE")),
            id=int(data.simple("ID")),
            lastPackOpened=int(data.simple("LAST_PACK_OPENED"))
            if data.simple("LAST_PACK_OPENED")
            else None,
            lastValued=int(data.simple("LAST_VALUED"))
            if data.simple("LAST_VALUED")
            else None,
            name=data.simple("NAME"),
            numCards=int(data.simple("NUM_CARDS")),
            rank=int(data.simple("RANK")),
            regionRank=int(data.simple("REGION_RANK")),
        )


@dataclasses.dataclass()
class Census:
    """Class that represents a NS census category.

    id corresponds to the trend page
    (such as https://www.nationstates.net/nation=hn67/detail=trend/censusid=78)
    or can be found at https://forum.nationstates.net/viewtopic.php?f=15&t=159491.

    score is the raw value of the census.

    rank is the world/regional position.

    percentage is the top percentage group the census value is part of,
    e.g. percentage=15 means "top 15%".
    """

    id: int

    score: float

    rank: int
    regionalRank: int

    percentage: float
    regionalPercentage: float

    @classmethod
    def from_xml(cls, node: etree.Element) -> Census:
        """Creates a Census from an XML SCALE node
        (See https://www.nationstates.net/cgi-bin/api.cgi?nation=testlandia&q=census&mode=score+rank+rrank+prank+prrank&scale=all)
        """  # noqa pylint: disable=line-too-long
        parse = NodeParse(node)
        return cls(
            id=int(node.attrib["id"]),
            score=float(parse.simple("SCORE")),
            rank=int(parse.simple("RANK")),
            regionalRank=int(parse.simple("RRANK")),
            percentage=float(parse.simple("PRANK")),
            regionalPercentage=float(parse.simple("PRRANK")),
        )


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
        parse = NodeParse(node)
        return cls(
            id=int(node.attrib["id"]),
            title=parse.simple("TITLE"),
            text=parse.simple("TEXT"),
            author=parse.simple("AUTHOR"),
            editors=(
                parse.simple("EDITOR").split(", ") if parse.simple("EDITOR") else []
            ),
            pic1=parse.simple("PIC1") if parse.has_name("PIC1") else "",
            pic2=parse.simple("PIC2") if parse.has_name("PIC2") else "",
            options={
                int(child.attrib["id"]): content(child)
                for child in parse.from_name("OPTION")
            },
        )


@dataclasses.dataclass()
class Freedoms(Generic[T]):
    """Dataclass that contains info on freedoms"""

    civilRights: T
    economy: T
    politicalFreedom: T

    @classmethod
    def from_xml(
        cls, node: etree.Element, converter: Callable[[str], T]
    ) -> Freedoms[T]:
        """Constructs a Freedoms object using the given node.
        Casts the content of each subnode using the converter.
        """
        data = NodeParse(node)
        return cls(
            civilRights=converter(data.simple("CIVILRIGHTS")),
            economy=converter(data.simple("ECONOMY")),
            politicalFreedom=converter(data.simple("POLITICALFREEDOM")),
        )


@dataclasses.dataclass()
class DeathCause:
    """Dataclass of the type of death and percentage"""

    cause: str
    percentage: float

    @classmethod
    def from_xml(cls, node: etree.Element) -> DeathCause:
        """Constructs a DeathCause from a CAUSE node, as contained in the NS deaths shard
        (https://www.nationstates.net/cgi-bin/api.cgi?nation=testlandia&q=deaths).
        """
        return cls(cause=node.attrib["type"], percentage=float(content(node)))


@dataclasses.dataclass()
class NationStandard:
    """Dataclass of the data returned by standard request to nation API,
    or the data of a nation in the nations data dump.
    """

    name: str
    classification: str
    fullName: str
    motto: str
    governmentCategory: str
    WAStatus: str
    endorsements: Sequence[str]
    issuesAnswered: int
    freedom: Freedoms[str]
    region: str
    population: int
    tax: float
    animal: str
    currency: str
    demonym: str
    demonym2: str
    demonym2Plural: str
    flag: str
    majorIndustry: str
    governmentPriority: str
    government: Mapping[str, float]
    founded: str
    firstLogin: int
    lastLogin: int
    influence: str
    freedomScores: Freedoms[int]
    publicSector: float
    deaths: Sequence[DeathCause]
    leader: str
    capital: str
    religion: str
    factbooks: int
    dispatches: int
    dbid: int

    @classmethod
    def from_xml(cls, node: etree.Element) -> NationStandard:
        """Constructs a NationStandard using a NATION node"""
        data = NodeParse(node)
        return cls(
            name=data.simple("NAME"),
            classification=data.simple("TYPE"),
            fullName=data.simple("FULLNAME"),
            motto=data.simple("MOTTO"),
            governmentCategory=data.simple("CATEGORY"),
            WAStatus=data.simple("UNSTATUS"),
            endorsements=(
                data.simple("ENDORSEMENTS").split(",")
                if data.simple("ENDORSEMENTS")
                else []
            ),
            issuesAnswered=int(data.simple("ISSUES_ANSWERED")),
            freedom=Freedoms.from_xml(data.first("FREEDOM"), str),
            region=data.simple("REGION"),
            population=int(data.simple("POPULATION")),
            tax=float(data.simple("TAX")),
            animal=data.simple("ANIMAL"),
            currency=data.simple("CURRENCY"),
            demonym=data.simple("DEMONYM"),
            demonym2=data.simple("DEMONYM2"),
            demonym2Plural=data.simple("DEMONYM2PLURAL"),
            flag=data.simple("FLAG"),
            majorIndustry=data.simple("MAJORINDUSTRY"),
            governmentPriority=data.simple("GOVTPRIORITY"),
            government={
                child.tag: float(content(child)) for child in data.first("GOVT")
            },
            founded=data.simple("FOUNDED"),
            firstLogin=int(data.simple("FIRSTLOGIN")),
            lastLogin=int(data.simple("LASTLOGIN")),
            influence=data.simple("INFLUENCE"),
            freedomScores=Freedoms.from_xml(data.first("FREEDOMSCORES"), int),
            publicSector=float(data.simple("PUBLICSECTOR")),
            deaths=sequence(data.first("DEATHS"), DeathCause.from_xml),
            leader=data.simple("LEADER"),
            capital=data.simple("CAPITAL"),
            religion=data.simple("RELIGION"),
            factbooks=int(data.simple("FACTBOOKS")),
            dispatches=int(data.simple("DISPATCHES")),
            dbid=int(data.simple("DBID")),
        )


@dataclasses.dataclass()
class Officer:
    """Class that represents a Officer for a region,
    and the related available data.
    """

    nation: str  # Name of officer
    office: str  # Name of office
    authority: str  # Authority permissions (each letter is a perm)
    time: int  # Timestamp they were appointed at
    by: str  # Who appointed the officer
    order: str  # Position in officer list on NS

    @classmethod
    def from_xml(cls, node: etree.Element) -> Officer:
        """Method that parses a Officer object from
        an OFFICER xml node, as contained by the OFFICERS shard.
        """
        data = label_children(node)
        return cls(
            nation=content(data["NATION"]),
            office=content(data["OFFICE"]),
            authority=content(data["AUTHORITY"]),
            time=int(content(data["TIME"])),
            by=content(data["BY"]),
            order=content(data["ORDER"]),
        )


@dataclasses.dataclass()
class Embassy:
    """Class that represents the data of an embassy for a Region."""

    region: str
    status: str

    @classmethod
    def from_xml(cls, node: etree.Element) -> Embassy:
        """Method that parses a Embassy object from a EMBASSY XML node"""
        return cls(
            region=content(node),
            status=node.attrib["type"] if "type" in node.attrib else "open",
        )


@dataclasses.dataclass()
class RegionStandard:
    """Class that represents the API standard data for a Region.
    Mostly used as the object returned by the region dump.
    """

    name: str
    factbook: str

    numnations: int
    nations: Sequence[str]

    delegate: str
    delegateVotes: int
    delegateAuth: str

    founder: str
    founderAuth: str

    officers: Sequence[Officer]

    power: str
    flag: str
    embassies: Sequence[Embassy]
    lastUpdate: int

    @classmethod
    def from_xml(cls, node: etree.Element) -> RegionStandard:
        """Parses standard Region data from XML format"""
        shards = label_children(node)
        return cls(
            name=content(shards["NAME"]),
            factbook=content(shards["FACTBOOK"]),
            numnations=int(content(shards["NUMNATIONS"])),
            nations=content(shards["NATIONS"]).split(":"),
            delegate=content(shards["DELEGATE"]),
            delegateVotes=int(content(shards["DELEGATEVOTES"])),
            delegateAuth=content(shards["DELEGATEAUTH"]),
            founder=content(shards["FOUNDER"]),
            founderAuth=content(shards["FOUNDERAUTH"]),
            officers=sequence(node=shards["OFFICERS"], key=Officer.from_xml),
            power=content(shards["POWER"]),
            flag=content(shards["FLAG"]),
            embassies=sequence(node=shards["EMBASSIES"], key=Embassy.from_xml),
            lastUpdate=int(content(shards["LASTUPDATE"])),
        )


# StandardParser
SParser = TypeVar("SParser", NationStandard, RegionStandard)

# # XMLTransformer/Parser logic
# """Tools for describing the transformation from XML to Python"""


class NodeParse:
    """Class to ease the transformation from XML data to a Python object."""

    def __init__(self, node: etree.Element) -> None:
        """Wraps a root node"""
        self.node = node

        child_tags: MutableMapping[str, MutableSequence[etree.Element]] = {}
        for child in node:
            if child.tag in child_tags:
                child_tags[child.tag].append(child)
            else:
                child_tags[child.tag] = [child]

        # 'Freeze' the child tags attribute so that it appears immutable
        self.child_tags: Mapping[str, Sequence[etree.Element]] = child_tags

    def has_name(self, name: str) -> bool:
        """Checks whether the given name is a tag of one of the child nodes."""
        return name in self.child_tags

    def from_name(self, name: str) -> Sequence[etree.Element]:
        """Returns a sequence of all nodes that have
        the given parameter as a tag.
        Runs in O(1) time since a map is pre-created.
        Raises KeyError if the tag doesnt exist.
        """
        return self.child_tags[name]

    def first(self, name: str) -> etree.Element:
        """Returns the first node with the given tag.
        O(1) time complexity.
        """
        return self.from_name(name)[0]

    def simple(self, name: str) -> str:
        """Returns the text content of the first subnode with a matching tag"""
        return content(self.first(name))


def label_children(node: etree.Element) -> Mapping[str, etree.Element]:
    """Returns a mapping from node tag name to node
    for each child node of the parameter.
    Note that if there are multiple children with the same tag,
    the last one will overwrite previous ones in the returned map.
    """
    return {child.tag: child for child in node}


def content(node: etree.Element) -> str:
    """Function to parse simple tags that contain the data as text"""
    return node.text if node.text else ""


def sequence(node: etree.Element, key: Callable[[etree.Element], T]) -> Sequence[T]:
    """Traverses the subnodes of a given node,
    retrieving the result from the key function for each child.
    """
    return [key(sub) for sub in node]


def main() -> None:
    """Main function; only for testing"""

    requester: NSRequester = NSRequester("HN67 API Reader")
    print(requester.request("a=useragent").text)


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
