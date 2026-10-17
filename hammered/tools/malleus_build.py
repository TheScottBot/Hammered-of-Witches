"""Builds hammered/data/malleus.json: the Malleus Maleficarum (1928 Summers translation), as passages.

    python -m hammered.tools.malleus_build      (needs: pip install -e ".[build]")

Unlike ktdi, nothing is left out here for taste: every readable passage about witches, devils, magic and witch
trials is kept, torture and all, and each server prunes what it shows with /setup (hammered/content.py tags the
passages as the bot loads them).

What *is* left out is what isn't the Malleus or can't be read: Summers' introduction and footnotes, running heads,
and OCR debris. The OCR of the 1928 scans is rough (columns run together, drop capitals, broken words), so a sentence
is only kept if every word in it is a real one: short words from SHORT_WORDS, longer ones used three times in the
book or common in English (wordfreq). Typos are one-offs, so this drops nearly all the garbage, along with some
good sentences, which is the right way round for a bot that quotes them.

Two scans of the same edition are read, since their OCR goes wrong in different places: the one ktdi links to,
then the Wellcome Library's, for the sentences the first one garbled. A passage links to its page in whichever it
came from.

The 45 tips hand-corrected for ktdi (hammered/data/picked.json) are kept as they are, marked "checked", in place of
the OCR's version of the same passage.

The OCR is downloaded once into build/malleus/ (gitignored).
"""

import gzip
import hashlib
import json
import re
import sys
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BUILD = ROOT / "build" / "malleus"
DATA = ROOT / "hammered" / "data"


@dataclass
class Scan:
    book: str  # archive.org identifier
    prefix: str  # its file names' prefix


# Best OCR first: a sentence comes from the first scan that reads it cleanly.
SCANS = [Scan("b3136245x", "b3136245x"), Scan("bf-1569-a-2-i-5-1928", "BF1569_A2I5_1928")]
PICKED_FROM = "bf-1569-a-2-i-5-1928"  # The scan ktdi's hand-checked tips (picked.json) give leaves in

# A passage must be about the book's subject: a stray sentence of scholastic argument isn't witch-finding advice.
WITCHY = re.compile(r"witch|wizard|sorcer|devil|demon|incub|succub|spell|enchant|magic|glamour|illusion|prestidig|"
                    r"ointment|unguent|\bhail|tempest|charm|amulet|exorcis|possess|satan|fiend|evil spirit|"
                    r"superstiti|divinat|necroman|\bpact|homage|philt|metamorpho|wolves|werewol|image of wax|"
                    r"holy water|agnus dei|consecrated|inquisit|heretic|heresy|familiar|transported|\bjudge|accused|"
                    r"suspect|confess|tortur|cattle|\bmilk|\bbeasts?\b|\bwolf|\btoad|\bwax|remed|\bcure|sacrament|"
                    r"midwi|virile|\bmember|bewitch|apostas|abjur|sabbath|broom|\bfly\b|through the air|the stars",
                    re.I)
# A running head: "Part II. Qn 1. Ch. 7", "Parr I. Question 6.", with the OCR's usual slips.
HEAD = re.compile(r"^[\W\d_]{0,6}(?:\w{1,4}\s+)?(?:MALLEUS\s+)?P[ae]r[rt][.,]?\s+(?P<part>[IlT1H]{1,3})\b[.,]?\s*"
                  r"(?:(?P<q>Q[\w!]*\.?\s*[\w!]{0,3})[.,:\-]?\s*)?(?:[CG][hu][.,]?\s*(?P<ch>\d+|g)\b[.,]?)?"
                  r"(?:\s*MALEFI\w*(?:\s+\d+)?)?")
MALLEUS_LINE = re.compile(r"^.{0,8}(?:THE\s+)?(?:MALLEUS|MALEFIC\w*|MALEFIG\w*)[\W\d\s]*(?:MALEFIC\w*)?[\W\d\s]*$")
HEADING_QUESTION = re.compile(r"^(?:THE \w+ HEAD\s+)?QUESTION\s+(?P<n>[IVXLT]+)\b")
HEADING_CHAPTER = re.compile(r"^CHAPTER\s+(?P<n>[IVXLT]+)\b")
FOOTNOTE = re.compile(r"^\W{0,3}(?:[*†‡§]|t\s*[“\"‘]|[*©]+\s*[“\"‘])")
# OCR debris is mostly short ("fo", "ead", "tbe"), and short junk passes for a word in any word list, so words of
# three letters or fewer must be real ones from this list.
SHORT_WORDS = set("""a A I O S am an as at be by do go he if in is it me my no of oh on or so to up us we ye lo ox ah ay
and any are art ask ate bad bed bid big bit boy but can cat cow cry cut day did die dog dry due ear eat egg end err eve
eye far fed few fit fly for fox get god got had has hat her him his hot how ice ill its joy key kin lad law lay led leg
let lie lip low mad man may men met mix mud nay net new nor not now nun oak oat odd off oft oil old one our out owe own
pan pay pit pot put raw red rid rod row rub run sad sat saw say sea see set sex she shy sin sit six sky son sow spy sum
sun tax ten the thy tie toe too top try two use vow war was way web wed wet who why wit woe won yea yes yet you ash axe
bag ban bar bow box bud cap cup dew dig dim dip dug dye elm fat fee fig fir fur gem hen hid hog hop hue hut inn jar jaw
lap lid lot map mat mid nap nod nut ore pad paw pea pen per pet pie pig pin ram rat ray rib rot rug rye sap sew sip sod
tag tan tap tar tea tin tip toy tub urn vat vex via wag wax wee wig win wry yew doe fie hie ere aye thee ewe all act
air aid add etc age ago arm awe beg buy eel era fan gap hum jug kid log oar pal pat pry rag rim rip sly sob tug yon
SS St Job Eve Lot Ham Abel Cain Adam Noah Gog Dan Eli""".split())
ROMAN = re.compile(r"^[ivxlc]+$", re.I)


def download(scan: Scan) -> tuple[str, list]:
    """The scan's OCR text and its page index: [start, end, ...] offsets into the text for each leaf."""
    BUILD.mkdir(parents=True, exist_ok=True)
    out = []
    for kind in ("hocr_searchtext.txt.gz", "hocr_pageindex.json.gz"):
        name = f"{scan.prefix}_{kind}"
        path = BUILD / name
        if not path.exists():
            print(f"Downloading {name}...")
            urllib.request.urlretrieve(f"https://archive.org/download/{scan.book}/{name}", path)
        out.append(gzip.decompress(path.read_bytes()).decode("utf-8"))
    return out[0], json.loads(out[1])


def roman(numeral: str) -> int:
    numeral = numeral.upper().replace("T", "I")
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for i, char in enumerate(numeral):
        value = values.get(char, 0)
        total += -value if i + 1 < len(numeral) and values.get(numeral[i + 1], 0) > value else value
    return total


def ocr_number(token: str) -> int | None:
    """A question number as the OCR read it: 7, 'g' (9), 'i', '!' or 'x' (1), 'IV'."""
    token = token.strip(".,:-")
    if token.isdigit():
        return int(token)
    if token == "g":
        return 9
    if token in {"i", "!", "x", "l", "I", "r"}:
        return 1
    if token and re.fullmatch(r"[IVXLT]+", token):
        return roman(token)
    return None


def head_section(match: re.Match) -> tuple | None:
    """The (part, question, chapter) a running head names, or None if it can't be read."""
    part = len(match["part"])
    question, chapter = 0, 0
    if match["q"]:
        q = match["q"].strip()
        tail = re.sub(r"^Q\w*?(?:TION|tion|Ion|IOn|ion|n)", "", q, count=1).strip()
        if part == 2:  # Part II has only two questions: "Qn 1", "Qni", "Qne" (2), "QUESTION 2."
            question = 2 if "2" in q or q.endswith("e") else 1
        else:
            question = ocr_number(tail.split()[0]) if tail.split() else None
            if question is None:
                return None
    if match["ch"]:
        chapter = 9 if match["ch"] == "g" else int(match["ch"])
    if part == 1 and question == 0:
        return None
    return part, question, chapter


def plausible(new: tuple, current: tuple, jump: int) -> bool:
    """Sections only go forward, and not by much: an OCR'd 'Question 8' in Question 2 is a misreading."""
    if new <= current:
        return False
    if new[0] != current[0]:
        return new[0] == current[0] + 1
    if new[1] != current[1]:
        return new[1] - current[1] <= jump
    return new[2] - current[2] <= jump


def section_key(section: tuple) -> str:
    part, question, chapter = section
    return f"II.{question}.{chapter}" if part == 2 else f"{'I' * part}.{question}"


def read_body(text: str, pages: list) -> list[tuple[int, tuple, str]]:
    """(leaf, section, line) for each line of the Malleus itself: no introduction, footnotes or running heads."""
    started = False
    section = (1, 1, 0)
    out = []
    for leaf, (start, end, *_) in enumerate(pages):
        in_footnote = False
        for line in text[start:end].split("\n"):
            line = re.sub(r"\s+", " ", line).replace("¬", "-").strip()  # The Wellcome OCR: double spaces, ¬ hyphens
            if not started:
                started = line.startswith("THE FIRST PART TREAT")
                continue
            head = HEAD.match(line)
            if head and (len(line) < 60 or head["q"]):
                new = head_section(head)
                if new and plausible(new, section, 3):
                    section = new
                in_footnote = False  # A new page.
                line = line[head.end():].strip()  # Sometimes the OCR runs the head into the text.
                if len(line) < 20:
                    continue
            if MALLEUS_LINE.match(line):
                in_footnote = False
                continue
            if re.match(r"^THE (SECOND|THIRD) PART", line):
                new = (2, 1, 0) if "SECOND" in line else (3, 0, 0)
                section = max(section, new)
                continue
            heading = HEADING_QUESTION.match(line) or HEADING_CHAPTER.match(line)
            if heading:
                n = roman(heading["n"])
                if line.startswith("CHAPTER"):
                    new = (section[0], section[1], n)
                else:
                    new = (section[0], n, 0)
                if plausible(new, section, 2):
                    section = new
                continue
            if FOOTNOTE.match(line):
                in_footnote = True  # Until the next page: footnotes come at the bottom.
            if not in_footnote:
                out.append((leaf, section, line))
    return out


def tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,;:.?!])", r"\1", text)  # The 1928 printing (or its OCR) puts spaces before ; and :
    text = re.sub(r"([“‘(])\s+", r"\1", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\bS\$\.", "S.", text)
    text = re.sub(r"(?<=\w)[*†‡}]+|\s[*†‡]\s|_", " ", text)  # Footnote markers (the OCR reads some as "}")
    text = re.sub(r"\b1s\b", "is", text)
    return re.sub(r"\s+", " ", text).strip()


def join_hyphens(text: str, vocabulary: Counter) -> str:
    """'consum- mated' -> 'consummated', but 'self- evident' -> 'self-evident' when the book hyphenates it."""
    def fix(match: re.Match) -> str:
        first, second = match[1], match[2]
        if vocabulary[f"{first}-{second}".lower()] and not vocabulary[(first + second).lower()]:
            return f"{first}-{second}"
        return first + second
    return re.sub(r"([A-Za-z]+)-\s+([a-z]+)", fix, text)


def recaser(text: str):
    """The OCR reads some lower-case letters as capitals mid-sentence ("was Seized by the Count and accused of Various
    evil works"). This puts back a capitalised word the book almost always writes in lower case."""
    lower = Counter(re.findall(r"\b[a-z]+\b", text))
    upper = Counter(re.findall(r"\b[A-Z][a-z]+\b", text))

    def fix(match: re.Match) -> str:
        word = match[2]
        if upper[word] <= 2 and lower[word.lower()] >= 8 and word[0] in "SVCOWXZUP":
            return match[1] + word.lower()
        return match[0]
    return lambda chunk: re.sub(r"([a-z,;] )([A-Z][a-z]+)\b", fix, chunk)


ABBREVIATIONS = re.compile(r"\b(S|SS|St|viz|cf|ch|Ch|cap|lib|art|dist|Dist|q|i\.e|e\.g|Mr|Dr|ii|iii|iv|vi|vii|viii|"
                           r"ix|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx|v|x|i)\.\s")


def sentences(text: str) -> list[str]:
    text = ABBREVIATIONS.sub(lambda m: m[0][:-1] + " ", text)
    parts = re.split(r"(?:(?<=[.?!])|(?<=[.?!][\"')]))\s+(?=[\"'(]?[A-Z])", text)
    return [part.replace(" ", " ").strip() for part in parts if part.strip()]


def known(word: str, vocabulary: Counter) -> bool:
    from wordfreq import zipf_frequency
    bare = re.sub(r"'s$", "", word)
    if len(bare) <= 3:
        return bare in SHORT_WORDS or bare.lower() in SHORT_WORDS or bool(ROMAN.match(bare) and bare.islower())
    return vocabulary[bare.lower()] >= 3 or zipf_frequency(bare.lower(), "en") >= 2.5


def readable(sentence: str, vocabulary: Counter) -> bool:
    if not 40 <= len(sentence) <= 700 or sentence[-1] not in ".?!\"'" or not re.match(r"[\"'(]?[A-Z]", sentence):
        return False
    if re.search(r"[^A-Za-z ,.;:?!'\"()\-—&]", sentence) or re.search(r"\.\.|,,|;;|::|\s-\s|\s'\s|\(\)", sentence):
        return False
    if sentence.count('"') % 2 or sentence.count("(") != sentence.count(")") or re.search(r"\b[A-Z]\.$", sentence):
        return False  # Unbalanced, or cut off at "S." (Saint), as in "especially S."
    for word in re.findall(r"[A-Za-z]+(?:'[a-z]+)?", sentence):
        if len(word) > 1 and word.isupper() and not ROMAN.match(word) and word not in {"SS", "I"}:
            return False  # Drop capitals ("HERE is" for "There is") and headings.
        if re.search(r"[a-z][A-Z]", word) or not known(word, vocabulary):
            return False  # "aD error", "belicve"
    return True


def normal(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def passage_id(text: str) -> str:
    return hashlib.sha1(normal(text).encode()).hexdigest()[:6]


def scan_passages(scan: Scan) -> list[dict]:
    """The readable, witchy passages of one scan: a sentence, or a short one with the next."""
    text, pages = download(scan)
    lines = read_body(text, pages)
    raw = tidy(" ".join(line for *_, line in lines))
    vocabulary = Counter(word.lower() for word in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)?", raw))
    vocabulary = Counter(word.lower() for word in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)?", join_hyphens(raw, vocabulary)))
    recase = recaser(raw)

    # Sentences run across pages, so they're split from the whole text, then given the page they start on.
    runs: list[list] = []
    for leaf, section, line in lines:
        if runs and runs[-1][0] == leaf and runs[-1][1] == section:
            runs[-1][2].append(line)
        else:
            runs.append([leaf, section, [line]])
    starts, chunks, offset = [], [], 0
    for leaf, section, run_lines in runs:
        chunk = recase(join_hyphens(tidy(" ".join(run_lines)), vocabulary))
        starts.append((offset, leaf, section))
        chunks.append(chunk)
        offset += len(chunk) + 1
    whole = " ".join(chunks)
    found, position, run = [], 0, 0
    for sentence in sentences(whole):
        # A chapter's drop capital: "IT has already been stated". Longer ones lose a letter ("HERE" for "There").
        sentence = re.sub(r"^([\"']?)(IT|IN|AS|AT|BY|IF|OF|ON|SO|TO|WE|HE|NO|OR)\b", lambda m: m[1] + m[2].title(),
                          sentence)
        at = whole.find(sentence[:30], position)
        position = at if at >= 0 else position
        while run + 1 < len(starts) and starts[run + 1][0] <= position:
            run += 1
        found.append((sentence, starts[run][1], starts[run][2], readable(sentence, vocabulary)))

    passages, i = [], 0
    while i < len(found):
        sentence, leaf, section, ok = found[i]
        i += 1
        if not ok:
            continue
        # A short sentence takes the next one with it, if that reads too: "Answer. ..." alone says little.
        if len(sentence) < 140 and i < len(found) and found[i][3] and len(sentence) + len(found[i][0]) < 700:
            sentence = f"{sentence} {found[i][0]}"
            i += 1
        capitals = re.findall(r"\b[A-Z][a-z]+", sentence[1:])
        if len(capitals) > 0.25 * len(sentence.split()):
            continue  # A chapter heading: "Whether the Accused is to be Imprisoned, and..."
        if WITCHY.search(sentence) and len(sentence) >= 60:
            passages.append({"id": passage_id(sentence), "book": scan.book, "leaf": leaf,
                             "sec": section_key(section), "text": sentence})
    return passages


def sentence_keys(text: str) -> set[str]:
    """What identifies a passage's sentences across the two scans: the first 30 letters of each (the scans' OCR
    differs in punctuation and the odd letter, and a passage may be one sentence in one and two in the other)."""
    return {normal(s)[:30] for s in sentences(text) if len(normal(s)) >= 25}


def build() -> list[dict]:
    seen: set[str] = set()
    everything = []

    by_scan = {scan.book: scan_passages(scan) for scan in SCANS}

    # ktdi's tips give leaves in its scan; their section is the one most passages on that leaf are in.
    picked = json.loads((DATA / "picked.json").read_text(encoding="utf-8"))
    sections_by_leaf: dict[int, Counter] = {}
    for passage in by_scan[PICKED_FROM]:
        sections_by_leaf.setdefault(passage["leaf"], Counter())[passage["sec"]] += 1
    for tip in picked:
        near = next((sections_by_leaf[leaf] for leaf in (tip["leaf"], tip["leaf"] - 1, tip["leaf"] + 1)
                     if leaf in sections_by_leaf), None)
        everything.append({"id": passage_id(tip["text"]), "book": PICKED_FROM, "leaf": tip["leaf"],
                           "sec": near.most_common(1)[0][0] if near else "I.1", "text": tip["text"], "checked": True})
        seen |= sentence_keys(tip["text"])

    for passages in by_scan.values():
        for passage in passages:
            keys = sentence_keys(passage["text"])
            if keys & seen:
                continue
            seen |= keys
            everything.append(passage)

    order = {key: n for n, key in enumerate(json.loads((DATA / "sections.json").read_text(encoding="utf-8")))}
    everything.sort(key=lambda p: (order.get(p["sec"], 999), p["book"] != SCANS[0].book, p["leaf"]))
    ids = Counter(p["id"] for p in everything)
    assert all(count == 1 for count in ids.values()), [i for i, c in ids.items() if c > 1]
    return everything


def main():
    passages = build()
    out = DATA / "malleus.json"
    body = ",\n".join(" " + json.dumps(p, ensure_ascii=False) for p in passages)
    out.write_text(f"[\n{body}\n]\n", encoding="utf-8")
    books = Counter(p["book"] for p in passages)
    print(f"Wrote {len(passages)} passages ({sum(p.get('checked', False) for p in passages)} hand-checked; "
          f"by scan: {dict(books)}) from {len({p['sec'] for p in passages})} sections to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
