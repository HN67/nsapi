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
    Collection,
    Iterable,
    Mapping,
    Optional,
)

# Utility
import itertools

# Time modules
import time

# Core libraries that support most of this module
import xml.etree.ElementTree as etree
import requests

from nsapi.exceptions import APIError, AuthError, ResourceError

from nsapi.models import (
    NationStandard,
    RegionStandard,
    Census,
    CardIdentifier,
    DeckInfo,
    Issue,
    Trade,
    Dossier,
    Happening,
)

from nsapi.resources import DumpManager

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
        self, api: str, headers: Optional[Mapping[str, str]] = None
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
        self, headers: Optional[Mapping[str, str]] = None, **parameters: str
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
        headers: Optional[Mapping[str, str]] = None,
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

    def _key(self) -> Mapping[str, str]:
        """Determines the first key of the request, encodes the API and name"""
        return {self.api: self.name}

    def _headers(self) -> Mapping[str, str]:
        """Returns various headers to add to a request, such as authentication"""
        return {}

    def shards_response(
        self,
        *shards: str,
        headers: Optional[Mapping[str, str]] = None,
        **parameters: str,
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
        self,
        *shards: str,
        headers: Optional[Mapping[str, str]] = None,
        **parameters: str,
    ) -> Mapping[str, etree.Element]:
        """Returns a mapping from the shard name to the XML element returned
        Connects to the `<api>=<name>&q=<shards>` page of the api
        """
        return {
            node.tag.lower(): node
            for node in as_xml(
                self.shards_response(*shards, headers=headers, **parameters,).text
            )
        }

    def shards(
        self,
        *shards: str,
        headers: Optional[Mapping[str, str]] = None,
        **parameters: str,
    ) -> Mapping[str, str]:
        """Naively returns a mapping from the shard name to the text of that element
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

    def headers(self) -> Mapping[str, str]:
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

    def _headers(self) -> Mapping[str, str]:
        """Important headers to add to every request
        In particular, auth headers
        """
        return self.auth.headers() if self.auth else {}

    def shards_response(
        self,
        *shards: str,
        headers: Optional[Mapping[str, str]] = None,
        **parameters: str,
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
        return Dossier.from_xml(dossier=nodes["dossier"], rdossier=nodes["rdossier"])

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

    def standard(self) -> RegionStandard:
        """Returns a RegionStandard object for this Region"""
        return RegionStandard.from_xml(
            as_xml(self.requester.parameter_request(region=self.name).text)
        )


class World(API):
    """Reperesnts a live connection the the API of the World on NS"""

    def __init__(self, requester: NSRequester) -> None:
        super().__init__(requester, "world", "")

        # Maximum number of happenings returned by happenings shard in one response
        self.happeningsResponseLimit = 100

    def _key(self) -> Mapping[str, str]:
        return {}

    def _happenings_root(
        self, headers: Optional[Mapping[str, str]] = None, **parameters: str
    ) -> etree.Element:
        """Returns the NS API happenings query root element"""
        return self.shards_xml(
            "happenings", headers=headers, **self._key(), **parameters
        )["happenings"]

    def happenings(
        self,
        safe: bool = True,
        headers: Optional[Mapping[str, str]] = None,
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
                headers=headers,
                **parameters,
                beforeid=str(Happening.from_xml(root[-1]).id),
            )
            rootList.append(root)
        # https://docs.python.org/2/library/itertools.html#itertools.chain
        return (
            Happening.from_xml(node) for node in itertools.chain.from_iterable(rootList)
        )

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
    def _key(self) -> Mapping[str, str]:
        return {"cardid": str(self.id), "season": self.season}

    def shards_response(
        self,
        *shards: str,
        headers: Optional[Mapping[str, str]] = None,
        **parameters: str,
    ) -> requests.Response:
        # Injects an extra shard, i.e. `card`
        return super().shards_response("card", *shards, headers=headers, **parameters)

    def _trades_root(
        self, headers: Optional[Mapping[str, str]] = None, **parameters: str
    ) -> etree.Element:
        """Returns the NS API trades query root element"""
        return self.shards_xml("trades", headers=headers, **parameters)["trades"]

    def trades(
        self,
        safe: bool = True,
        headers: Optional[Mapping[str, str]] = None,
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


def main() -> None:
    """Main function; only for testing"""

    requester: NSRequester = NSRequester("HN67 API Reader")
    print(requester.request("a=useragent").text)


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
