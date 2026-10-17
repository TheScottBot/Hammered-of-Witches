"""hammered/malleus.py and its data (data/malleus.json, built by tools/malleus_build.py)."""

import json
import re

from hammered import content, malleus
from hammered.tools import malleus_build


def test_the_data_is_tidy():
    raw = json.loads((malleus.DATA / "malleus.json").read_text(encoding="utf-8"))
    assert len(raw) >= 1500
    assert len({p["id"] for p in raw}) == len(raw)
    for p in raw:
        assert set(p) <= {"id", "book", "leaf", "sec", "text", "checked", "extra"}, p
        assert p["id"] == malleus_build.passage_id(p["text"]), p  # Ids are stable: servers hide passages by them
        assert p["book"] in {scan.book for scan in malleus_build.SCANS} and isinstance(p["leaf"], int)
        assert p["sec"] in malleus.SECTIONS, p
        assert 40 < len(p["text"]) <= 1000 and p["text"][-1] in ".?!\"'", p["text"]
        assert not re.search(r"[€©™¥|{}<>*_~$@#%]|\s[,;.]|\b\d{2,}\b", p["text"]), p["text"]  # No OCR debris
        assert p.get("checked") or malleus_build.WITCHY.search(p["text"]), p["text"]
        for key in p.get("extra", {}):
            assert key in content.BY_KEY


def test_ktdis_hand_checked_tips_are_all_kept():
    picked = json.loads((malleus.DATA / "picked.json").read_text(encoding="utf-8"))
    checked = {p.text for p in malleus.PASSAGES if p.checked}
    assert checked == {tip["text"] for tip in picked}


def test_every_part_of_the_book_is_there():
    sections = {p.section for p in malleus.PASSAGES}
    assert len(sections) >= 70
    for part in ("I", "II", "III"):
        assert sum(p.section.split(".")[0] == part for p in malleus.PASSAGES) >= 300, part


def test_reference():
    assert malleus.reference("I.6") == "Part I, Question 6"
    assert malleus.reference("II.1.7") == "Part II, Question 1, Chapter 7"
    assert malleus.reference("II.2.0") == "Part II, Question 2"
    assert malleus.reference("III.0") == "Part III"


def passage(section="I.6", text="Witches *collect* members in a bird's nest.", tags=None):
    return malleus.Passage("abc123", "b3136245x", 83, section, text, tags or {})


def test_embed():
    embed = malleus.embed(passage("II.1.7"), content.every(content.FULL))
    assert embed.title == "🧹 Witch-finding advice"
    assert embed.description == "> Witches \\*collect\\* members in a bird's nest."
    assert embed.url == "https://archive.org/details/b3136245x/page/n83/mode/1up"
    assert embed.author.name == "Part II, Question 1, Chapter 7: How, as it were, they deprive man of his virile member"
    assert embed.footer.text == "Malleus Maleficarum (1486), tr. Montague Summers (1928) · #abc123"


def test_a_section_title_the_server_wouldnt_allow_is_left_out():
    tame = content.PRESETS_BY_KEY["tame"].limits
    assert malleus.embed(passage("I.6"), tame).author.name == "Part I, Question 6"
    assert malleus.embed(passage("II.1.7"), tame).author.name == "Part II, Question 1, Chapter 7"
    assert malleus.embed(passage("II.1.14"), tame).author.name == "Part II, Question 1, Chapter 14"  # Cattle harm
    assert malleus.embed(passage("II.1.3"), tame).author.name == \
        "Part II, Question 1, Chapter 3: How witches are transported from place to place"


def test_pick_follows_the_filters_and_avoids_repeats():
    tame = content.PRESETS_BY_KEY["tame"].limits
    shown = [malleus.pick(1, tame) for _ in range(40)]
    assert all(content.allowed(p.tags, tame) for p in shown)
    assert len({p.id for p in shown}) == 40


def test_pick_about_and_hidden():
    everything = content.every(content.FULL)
    nest = malleus.pick(1, everything, about="bird's nest")
    assert "nest" in nest.text and "bird" in nest.text
    nests = malleus.matching(everything, about="bird's nest")
    assert malleus.pick(1, everything, hidden={p.id for p in nests}, about="bird's nest") is None
    assert malleus.pick(1, everything, about="zzyzx") is None
