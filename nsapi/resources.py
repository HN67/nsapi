"""Utilities that manage uncertain and retrievable resources.

Especially focused on NationStates data dumps.
"""


# Standard modules
import dataclasses
import datetime
import logging
from typing import Mapping, Optional, Container, Generator, Type

# File management
import gzip
import json
import os
import shutil

# Tech libraries
import xml.etree.ElementTree as etree
import requests

from nsapi.models import SParser, NationStandard, RegionStandard, CardStandard

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Determine the root path for downloading and producing files
# Default on the file location, but if not existant for some reason
# then fall back on the current working directory
try:
    basePath = __file__
except NameError:
    basePath = os.getcwd()


def absolute_path(path: str) -> str:
    """Return the absolute path of a given path based on this file.

    Use of this function is not recommended, prefer basing off the cwd.
    """
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
        Otherwise, returns a path based on resource.name.
        """
        return target or resource.name

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
            with open(self.markerFile, "r", encoding="utf-8") as f:
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
        with open(self.markerFile, "w", encoding="utf-8") as f:
            json.dump(marker, f)


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
        with gzip.open(self.resourceManager.resolve(resource, location), "rt") as dump:
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
        with gzip.open(self.resourceManager.resolve(resource, location), "rt") as dump:

            # Looking for start events allows us to retrieve
            # the starting, parent, element using the `next()` call.
            iterator = etree.iterparse(dump, events=("start", "end"))  # type: ignore
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
