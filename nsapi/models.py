"""Models of object structures returned from the NationStates API."""

from __future__ import annotations

import dataclasses
import typing as t
from typing import Sequence, Mapping, Optional, Callable, Generic, Set

import xml.etree.ElementTree as etree

from nsapi.parser import NodeParse, label_children, content, sequence

T = t.TypeVar("T")


# TODO update these 2 classes to be dataclasses with .from_xml
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
SParser = t.TypeVar("SParser", NationStandard, RegionStandard)
