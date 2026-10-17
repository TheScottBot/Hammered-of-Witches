"""The Malleus Maleficarum's passages (data/malleus.json, built by tools/malleus_build.py): loading, tagging,
picking one a server's filters allow, and how one looks in Discord."""

import json
import random
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import discord

from hammered import content

DATA = Path(__file__).resolve().parent / "data"
SOURCE = "Malleus Maleficarum (1486), tr. Montague Summers (1928)"
COLOR = discord.Color.from_str("#FF1A8C")  # The icon's pink
PART_NAMES = {"I": "Part I", "II": "Part II", "III": "Part III"}


@dataclass(frozen=True)
class Passage:
    id: str
    book: str  # The archive.org scan it was read from
    leaf: int  # Its page in that scan
    section: str  # "I.6", "II.1.7" (Part II has questions and chapters), "III.15"
    text: str
    tags: dict  # category -> level (content.py)
    checked: bool = False  # Hand-corrected against the page (ktdi's tips), not straight from the OCR

    @property
    def url(self) -> str:
        return f"https://archive.org/details/{self.book}/page/n{self.leaf}/mode/1up"


def reference(section: str) -> str:
    """'II.1.7' -> 'Part II, Question 1, Chapter 7'."""
    part, *numbers = section.split(".")
    labels = ["Question", "Chapter"]
    out = [PART_NAMES[part]]
    for label, number in zip(labels, numbers):
        if number != "0":
            out.append(f"{label} {number}")
    return ", ".join(out)


def load() -> tuple[list[Passage], dict[str, str]]:
    raw = json.loads((DATA / "malleus.json").read_text(encoding="utf-8"))
    sections = json.loads((DATA / "sections.json").read_text(encoding="utf-8"))
    passages = [Passage(p["id"], p["book"], p["leaf"], p["sec"], p["text"],
                        content.tag(p["text"], p.get("extra"), p["sec"]), p.get("checked", False)) for p in raw]
    return passages, sections


PASSAGES, SECTIONS = load()
BY_ID = {passage.id: passage for passage in PASSAGES}
# What a section's title would be tagged as, so a title isn't shown where its passage's server wouldn't want it
# ("...why women are chiefly addicted to evil superstitions").
SECTION_TAGS = {key: content.tag(title) for key, title in SECTIONS.items()}

# The last few passages shown in each server (or DM), so the same one doesn't come up twice in a row.
RECENT_SIZE = 50
recent: dict[int, deque] = {}


# Much of the book is scholastic argument ("Thomas when he discusses the power of the devil..."). The lore and the
# tales are the fun, so a random pick favours them: they're weighted up, nothing is left out.
LORE = re.compile(r"\b(milk|butter|cows?|cattle|hail|storms?|tempest|lightning|ointment|unguent|broom|fly|flew|"
                  r"flying|through the air|nests?|members?|cats?|toads?|wolf|wolves|serpents?|snakes?|wax|salt|"
                  r"holy water|threshold|bed|cradle|knife|pail|well|water|weep|tears|herbs?|shape|beasts?|horses?|"
                  r"incubus|succubus|familiar|homage|sabbath|night|market|harvest|crops|vine|bury|buried|bones|"
                  r"hair|eyes|glance|look|touch|apple|bread|kiss|dance|ride|rode|carried|ointments|spittle)\b", re.I)
STORY = re.compile(r"\b(a certain|in the town of|in the diocese of|there was|it happened|we have (found|known|seen)|"
                   r"we know|was seen|told us|came to|once|one day|in our (time|days)|in the city of|"
                   r"of whom|was taken|she confessed|he confessed|common report)\b", re.I)


def weight(passage: Passage) -> int:
    return 1 + 3 * bool(LORE.search(passage.text)) + 3 * bool(STORY.search(passage.text)) + 4 * passage.checked


WEIGHTS = {passage.id: weight(passage) for passage in PASSAGES}


def words_in(query: str) -> list[re.Pattern]:
    """Each word of a search, matched at the start of a word: 'milk cow' finds 'milked the cows'."""
    return [re.compile(rf"\b{re.escape(word)}", re.I) for word in re.findall(r"[A-Za-z']+", query)]


def matching(limits: dict[str, int], hidden: set[str] = frozenset(), about: str = "",
             must: re.Pattern | None = None) -> list[Passage]:
    patterns = words_in(about)
    return [p for p in PASSAGES if p.id not in hidden and content.allowed(p.tags, limits)
            and all(pattern.search(p.text) for pattern in patterns) and (must is None or must.search(p.text))]


def pick(where: int, limits: dict[str, int], hidden: set[str] = frozenset(), about: str = "",
         must: re.Pattern | None = None) -> Passage | None:
    """A random passage these limits allow (and about these words, if given), avoiding ones shown here lately."""
    candidates = matching(limits, hidden, about, must)
    if not candidates:
        return None
    shown = recent.setdefault(where, deque(maxlen=RECENT_SIZE))
    fresh = [p for p in candidates if p.id not in shown] or candidates
    passage = random.choices(fresh, weights=[WEIGHTS.get(p.id) or weight(p) for p in fresh])[0]
    shown.append(passage.id)
    return passage


def embed(passage: Passage, limits: dict[str, int], title: str = "🧹 Witch-finding advice") -> discord.Embed:
    result = discord.Embed(title=title, url=passage.url, color=COLOR,
                           description=f"> {discord.utils.escape_markdown(passage.text)}")
    section_title = SECTIONS.get(passage.section)
    heading = reference(passage.section)
    if section_title and content.allowed(SECTION_TAGS.get(passage.section, {}), limits):
        heading = f"{heading}: {section_title}"
    result.set_author(name=heading[:256])
    result.set_footer(text=f"{SOURCE} · #{passage.id}")
    return result
