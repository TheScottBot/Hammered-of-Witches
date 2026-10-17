"""What's in each passage, so each server can prune the Malleus to its own taste.

The Malleus is a manual for persecuting women, written by inquisitors; nearly every page has something in it that a
server might not want. Rather than cut the book down for everyone (as ktdi does), every passage is tagged here, per
category, as 0 (nothing), 1 (mild: in passing) or 2 (strong: the point of the passage), and each server chooses,
per category, how much it allows (hammered/settings.py): OFF allows 0, MILD up to 1, FULL anything.

Tagging is by patterns, not AI, so it can be read, tested and fixed. It errs on the side of tagging: a false tag
only hides a passage from a strict server, a missed one shows it. tests/test_content.py pins down the known cases;
when a passage gets through that shouldn't, add a pattern (or an "extra" tag on the passage in malleus.json, for
a one-off) and a test.

This module is plain Python, no Discord.
"""

import re
from dataclasses import dataclass, field

OFF, MILD, FULL = 0, 1, 2
LEVEL_NAMES = {OFF: "off", MILD: "mild", FULL: "full"}


def words(*patterns: str) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I)


@dataclass(frozen=True)
class Category:
    key: str  # As in /setup <key>
    name: str
    emoji: str
    about: str  # What it covers, for /setup and /help
    strong: re.Pattern  # Any match: level 2
    mild: re.Pattern  # Any match: level 1
    # Both needed for level 2 (e.g. a child, and harm). With mention_is_mild, the first alone is level 1 (a child
    # mentioned at all); without, it's nothing (a cow being milked).
    pairs: tuple[tuple[re.Pattern, re.Pattern], ...] = field(default=())
    mention_is_mild: bool = False

    def level(self, text: str) -> int:
        if self.strong.search(text) or any(a.search(text) and b.search(text) for a, b in self.pairs):
            return FULL
        if self.mild.search(text) or (self.mention_is_mild and any(a.search(text) for a, _ in self.pairs)):
            return MILD
        return OFF


HARM = words(r"\bkill", r"\bslay", r"\bslew\b", r"\bslain", r"murder", r"devour", r"\bate\b", r"\beat(s|en|ing)?\b",
             r"\bcook", r"\bboil", r"sacrific", r"\boffer(s|ed|ing)?\b.{0,40}\bdevils?", r"\bdrown", r"strangl",
             r"\bdeath\b", r"\bdead\b", r"\bdie[ds]?\b", r"\bdying\b", r"\bhurt", r"\binjur", r"\bharm", r"\bblood",
             r"tortur", r"\bburn", r"\bcut\b", r"\bpierc", r"\bwound", r"\blame\b", r"\bwither")

CHILD = words(r"\bchild", r"\binfant", r"\bbab(e|es|y|ies)\b", r"new-?born", r"unbaptized", r"\bboys?\b",
              r"\bgirls?\b", r"\bin the womb", r"\bcradle", r"little ones", r"\bfoetus", r"\bembryo")

ANIMAL = words(r"\bcattle", r"\bcows?\b", r"\bcalf", r"\bcalves", r"\bhorses?\b", r"\bmares?\b", r"\bsheep",
               r"\bpigs?\b", r"\bswine", r"\boxen\b", r"\bherds?\b", r"\bflocks?\b", r"\bbeasts?\b", r"\banimals?\b",
               r"\bdogs?\b", r"\bcats?\b", r"\bpoultry", r"\bhens?\b", r"\bfowls?\b")

CATEGORIES = [
    Category(
        "misogyny", "Misogyny", "♀️",
        "The book's contempt for women: that they're weaker, lustful, liars, more prone to witchcraft. "
        "(Every witch in it is \"she\"; that alone isn't tagged.)",
        strong=words(r"wicked(ness)? (of )?(a )?wom[ae]n", r"\bwom[ae]n (are|is) (by nature |naturally )?(more |the )?"
                     r"(\w+ )?(credulous|impression|feeble|weak|liars?|deceiv|deceptive|carnal|lustful|insatiable|"
                     r"imperfect|vain|wicked|evil|quick|slippery|light|intemperate|defective|chiefly)",
                     r"\bfeminine\b.{0,40}\b(evil|wicked|fragile|feeble|weak)", r"\bfragile feminine", r"weaker sex",
                     r"necessary evil", r"imperfect animal", r"\binsatiable", r"defect (in|of) (the )?(formation|"
                     r"intellect)", r"\bbent rib", r"quicker to waver", r"\bfoe to friendship", r"natural temptation",
                     r"(evil|wicked|bad|lustful|carnal) wom[ae]n", r"\bwom[ae]n\b[^.]{0,80}\b(more|chiefly) "
                     r"(addicted|given|prone|infected)", r"\bthe sex\b[^.]{0,40}\b(weak|feeble|frail|wicked)",
                     r"\bfemina\b", r"\bless faith\b", r"more carnal than", r"\bfragile (a )?sex",
                     r"wom[ae]n more bitter than death", r"hunter's snare", r"more perilous than a snare",
                     r"rid of women", r"more powerful party", r"\bwom[ae]n\b[^.]{0,60}\bthan men\b"),
        mild=words(r"\bwomen are\b", r"\bwoman is\b", r"female sex", r"feminine sex", r"\bsex of women\b",
                   r"\bwomen\b[^.]{0,60}\b(than men|more than|rather than) men", r"\bmore women than men",
                   r"\bthe nature of (a )?wom[ae]n", r"\bwom[ae]n\b[^.]{0,60}\bwitchcraft", r"\bwitches\b[^.]{0,40}"
                   r"\bwomen\b", r"\bsuperstiti\w+\b[^.]{0,40}\bwom[ae]n", r"\bwom[ae]n\b[^.]{0,40}\bsuperstiti",
                   r"\badulteresses?\b", r"\bharlots?\b", r"\bwhores?\b", r"\bfornicatress")),
    Category(
        "faiths", "Other faiths & peoples", "✡️",
        "Contempt for Jews, Muslims (\"Saracens\", \"Turks\"), pagans and other peoples or faiths.",
        strong=words(r"\bjews?\b", r"\bjewish", r"\bjewess", r"\bsynagogue", r"\bsaracens?", r"\bturks?\b",
                     r"\bmoors?\b", r"\binfidels?", r"\bperfidious", r"mahomet", r"\bheathens?", r"\bgipsy|\bgypsy",
                     r"\bgipsies|\bgypsies", r"\bethiop", r"\bblackamoor", r"\bnegro"),
        mild=words(r"\bpagans?\b", r"\bgentiles?\b", r"\bidolat", r"\bhebrews?\b", r"\bunbelievers?",
                   r"\bthe unbelieving\b", r"\bbarbarian", r"\bschismatic")),
    Category(
        "lgbt", "Gender & sexuality (LGBTQ+)", "🏳️‍🌈",
        "Sodomy, \"vice against nature\", hermaphrodites, eunuchs, sex-changes, and gender or sexuality treated as "
        "sin, a joke or witchcraft. Set it off for an LGBTQ+-friendly server.",
        strong=words(r"sodom(?!a\b)", r"\bsodomit", r"against nature", r"unnatural (vice|sin|lust|act)",
                     r"\bhermaphrodit", r"\beunuchs?\b", r"\beffeminate", r"change[sd]? (of |their |his |her )?sex",
                     r"\b(men|man) into (a )?wom[ae]n", r"\b(women|woman) into (a )?m[ae]n\b", r"\bcatamite",
                     r"\bsapphi", r"\btribad", r"\bsame sex\b", r"\bof the same sex"),
        mild=words(r"\bincubus\b[^.]{0,80}\bmen\b", r"\bsuccub\w*\b[^.]{0,80}\bwom[ae]n\b",
                   r"\bassum\w+ the (form|shape|body) of a (wom|m)[ae]n", r"\bthe sex of\b",
                   r"\bmale\b[^.]{0,30}\bfemale\b[^.]{0,30}\b(body|form|shape)", r"\bunnatural",
                   r"\bwhich sex\b")),
    Category(
        "sex", "Sex & bodies", "🍆",
        "Copulation with devils, incubi and succubi, stolen \"members\", impotence spells and the like. "
        "(The book's most famous lore lives here.)",
        strong=words(r"copulat", r"\bcoit", r"\bsemen\b", r"\bseed\b[^.]{0,40}\b(inject|receiv|human|man)",
                     r"venereal", r"\bcarnal (act|intercourse|copulation|knowledge|connexion|union)",
                     r"\bmembers?\b[^.]{0,40}\b(male|virile|restor|remov|nest|organ|took|taken|lost)",
                     r"\b(male|virile|genital) (member|organ)", r"\bgenital", r"\berect", r"\bnaked",
                     r"\bpri[vy]y parts", r"\bfornicat", r"\badulter", r"\blust\b", r"\blustful", r"\blechery",
                     r"\bcopula\b", r"\bimpoten", r"\bact of (generation|coition)", r"\bprocreat", r"incub",
                     r"succub", r"\bwhore", r"\bharlot", r"\bvirginity", r"\bconsummat", r"\bbreasts?\b"),
        mild=words(r"\bcarnal", r"\bconcupiscence", r"\bgenerati(on|ve) (power|faculty|act|functions)",
                   r"\bpower of generation", r"\bfrigid", r"\bmarriage act", r"\bconjugal", r"\binordinate love",
                   r"\blove\b[^.]{0,30}\b(philtre|potion|spell|charm)", r"\bwanton", r"\bchastity", r"\blovers?\b",
                   r"\bbed\b", r"\bwomb", r"\bpregnan", r"\bconceiv", r"\bmembers?\b")),
    Category(
        "gore", "Torture & violence", "🩸",
        "The torture, burning and execution of the accused, and other violence. Mild is punishment in passing "
        "(\"handed to the secular court\"); strong is the rack, the stake and the rest.",
        strong=words(r"tortur", r"\bthe rack\b", r"\bracked\b", r"strappado", r"\bburn(ed|t|ing)?\b[^.]{0,40}"
                     r"\b(alive|stake|fire|witch|her|him|them|death)", r"\b(stake|pyre|faggots)\b", r"\bflames\b",
                     r"\bput to death", r"\bexecut", r"put to the question", r"\btorment", r"\bmutilat",
                     r"\bdismember", r"\bgallows", r"\bbehead", r"\bhanged\b", r"\bhang(ed|ing)? (her|him|them)",
                     r"red-hot", r"\bscourg", r"\bflog", r"\bwhip", r"engines of", r"\bsecular arm\b[^.]{0,80}\b"
                     r"(death|punish|fire)", r"\bbloodshed", r"\bentrails", r"\btear\w* (to|in) pieces",
                     r"\bdevour", r"\bslaughter", r"\bmurder", r"\bboil(ed|ing)? (it|them|her|him|the)",
                     r"\bcondemned to the fire", r"\bshav(e|ed|ing)\b[^.]{0,60}\b(hair|body|parts|head)"),
        mild=words(r"\bkill", r"\bslay", r"\bslain", r"\bslew\b", r"\bblood", r"\bwound", r"\bpunish",
                   r"\bpenalt", r"prison",r"\bchains?\b", r"\bfetter", r"\bsecular (arm|court|judge)",
                   r"\bsentenc", r"\bburn", r"\bfire\b", r"\bdeath\b", r"\bhang", r"\bbeat(en|ing)?\b", r"\bstrik",
                   r"\bviolen", r"\bcruel", r"\bpains?\b", r"\bsuffer", r"\bcorpse", r"\bbones?\b", r"\bflesh",
                   r"\bstrangl", r"\bdrown", r"\bdead\b", r"\bdie[ds]?\b", r"\bdying\b", r"\bhurt", r"\binjur",
                   r"\barrest", r"\bstrip(ped)?\b", r"\bconfiscat", r"\bdungeon", r"\bcell\b", r"\bcapital",
                   r"\bstripes\b", r"\bblows\b", r"\bunpunished")),
    Category(
        "children", "Harm to children", "🍼",
        "Witch-midwives killing, eating or offering babies, and other harm to children. Children mentioned "
        "harmlessly are mild.",
        strong=words(r"\bmidwi", r"\babort", r"\bunbaptized\b[^.]{0,60}\b(child|infant|bab)",
                     r"\b(eat|ate|devour\w*|cook\w*|boil\w*|kill\w*|offer\w*|sacrific\w*) (the |their |young |"
                     r"little |new-born |unbaptized )*(child|infant|bab)", r"\bkill the child",
                     r"\bmiscarr", r"\bstillborn"),
        mild=words(r"\bpregnan", r"\bin the womb"),
        pairs=((CHILD, HARM),), mention_is_mild=True),
    Category(
        "animals", "Cruelty to animals", "🐄",
        "Bewitched, killed or maimed cattle and other animals.",
        strong=words(r"\b(kill|slay|slew|maim|lame|cut|strangl|drown|torment|burn|flay|skin)\w*\b[^.]{0,30}\b"
                     r"(cattle|cows?|calf|calves|horses?|beasts|animals|sheep|pigs?|swine|oxen|dogs?|cats?)\b",
                     r"\b(cattle|cows?|calf|calves|horses?|beasts|animals|sheep|pigs?|swine|oxen)\b[^.]{0,40}\b"
                     r"(killed|slain|die[ds]?|dead|maimed|lamed|drowned|perished|struck)"),
        mild=words(r"\binjure\w* cattle", r"\bcattle\b[^.]{0,60}\b(injur|harm|hurt|bewitch|sick)",
                   r"\bmilk\b[^.]{0,60}\b(steal|stole|take|took|dry)"),
        pairs=((ANIMAL, HARM),)),
    Category(
        "suicide", "Suicide & self-harm", "🕯️",
        "People driven to kill or hang themselves, often by the devil, in prison.",
        strong=words(r"\b(kill|hang|drown|strangl|destroy)\w* (him|her|them)sel(f|ves)", r"\bsuicide",
                     r"\btake (his|her|their) own li(fe|ves)", r"\bself-murder", r"\blay(ing)? (violent )?hands "
                     r"on (him|her|them)sel"),
        mild=words(r"\bdespair", r"\bhopeless", r"\bweary of (life|living)", r"\bwish(ed)? to die")),
]
BY_KEY = {category.key: category for category in CATEGORIES}


# Some sections colour everything in them, whatever a passage's own words: Question VI is the book's case against
# women (its "she" is women in general, not a witch), and Part III's Questions 13-16 and 22 are the torture.
SECTION_FLOORS = [
    (re.compile(r"^I\.6$"), words(r"\b(wom[ae]n|she|her|female|feminine|wife|wives)\b"), {"misogyny": MILD}),
    (re.compile(r"^III\.(13|14|15|16|22)$"), re.compile(""), {"gore": MILD}),
    (re.compile(r"^(I\.11|II\.1\.13)$"), CHILD, {"children": FULL}),  # The witch-midwives
]


def tag(text: str, extra: dict[str, int] | None = None, section: str = "") -> dict[str, int]:
    """Each category's level in a passage: only the ones above OFF. `section` is where it is in the book ("I.6"),
    and `extra` raises levels by hand (a passage's "extra" in malleus.json)."""
    tags = {c.key: level for c in CATEGORIES if (level := c.level(text))}
    floors = [floor for where, needs, floor in SECTION_FLOORS if where.match(section) and needs.search(text)]
    for key, level in [item for floor in floors for item in floor.items()] + list((extra or {}).items()):
        tags[key] = max(tags.get(key, OFF), level)
    return tags


def allowed(tags: dict[str, int], limits: dict[str, int]) -> bool:
    """Whether a passage with these tags may be shown where these limits (category -> highest level) apply."""
    return all(level <= limits.get(key, OFF) for key, level in tags.items())


@dataclass(frozen=True)
class Preset:
    key: str
    name: str
    about: str
    limits: dict[str, int]


def every(level: int, **overrides: int) -> dict[str, int]:
    return {c.key: overrides.get(c.key, level) for c in CATEGORIES}


PRESETS = [
    Preset("tame", "🕊️ Tame", "Nothing from any category: the lore and the inquisitors' advice without the ugliness. "
           "Still plenty of hailstorms, flying ointments and bewitched butter.", every(OFF)),
    Preset("default", "⚖️ Tasteful", "Where every server starts. Passing mentions of sex, violence, animals and the "
           "book's view of women stay (the stolen-member lore is mild-to-strong sex, so it's in); bigotry about "
           "faiths, LGBTQ+ people and harm to children, torture, and suicide are out.",
           every(MILD, sex=FULL, faiths=OFF, lgbt=OFF, children=OFF, suicide=OFF)),
    Preset("spicy", "🌶️ Spicy", "Everything strong except the bigotry: sex, torture and the misogyny in full, "
           "but nothing against faiths or LGBTQ+ people, and no harm to children or suicide.",
           every(FULL, faiths=OFF, lgbt=OFF, children=OFF, suicide=MILD)),
    Preset("unabridged", "🔥 Unabridged", "The whole book, as the inquisitors wrote it. All of it.", every(FULL)),
]
PRESETS_BY_KEY = {preset.key: preset for preset in PRESETS}
DEFAULT = PRESETS_BY_KEY["default"]


def preset_for(limits: dict[str, int]) -> Preset | None:
    """The preset these limits match exactly, if any."""
    return next((preset for preset in PRESETS if preset.limits == limits), None)
