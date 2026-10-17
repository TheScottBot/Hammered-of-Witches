"""hammered/content.py: tagging passages, and which ones each server's filters allow."""

import re

import pytest

from hammered import content, malleus
from hammered.content import FULL, MILD, OFF


@pytest.mark.parametrize("text, expected", [
    # The book's most famous lore: sex, strongly.
    ("And what, then, is to be thought of those witches who in this way sometimes collect male organs in great "
     "numbers, as many as twenty or thirty members together, and put them in a bird's nest?", {"sex": FULL}),
    ("All witchcraft comes from carnal lust, which is in women insatiable.", {"misogyny": FULL, "sex": FULL}),
    ("Therefore a wicked woman is by her nature quicker to waver in her faith.", {"misogyny": FULL}),
    ("Why it is that Women are chiefly addicted to Evil Superstitions.", {"misogyny": FULL}),
    ("And I have found a woman more bitter than death, who is the hunter's snare.", {"misogyny": FULL, "gore": MILD}),
    ("The devils shall blush at your iniquities, meaning vices against nature.", {"lgbt": FULL}),
    ("And the Jews were said to have done this in the synagogue.", {"faiths": FULL}),
    ("The next step of the Judge should be that, if after being fittingly tortured she refuses to confess the "
     "truth, he should have other engines of torture brought before her.", {"gore": FULL}),
    ("Witch midwives kill the child conceived in the womb and offer new-born children to devils.",
     {"children": FULL, "sex": MILD, "gore": MILD}),
    ("The devil drove her to hang herself in prison.", {"suicide": FULL, "gore": FULL}),
    ("And suddenly the devil takes the milk from the udder of that cow, and brings it to where the witch is sitting.",
     {}),
    ("If she be a witch she will not be able to weep: although she will assume a tearful aspect and smear her cheeks "
     "and eyes with spittle to make it appear that she is weeping.", {}),
])
def test_tags(text, expected):
    assert content.tag(text) == expected


def test_section_colours_its_passages():
    # In Question VI "she" is women in general; elsewhere it's just a witch.
    text = "When they are governed by an evil spirit, she indulges the worst possible vices."
    assert content.tag(text, section="I.6") == {"misogyny": MILD}
    assert content.tag(text, section="I.7") == {}
    assert content.tag("The judge shall then examine her.", section="III.15") == {"gore": MILD}
    assert content.tag("A thing.", extra={"lgbt": FULL}) == {"lgbt": FULL}


def test_allowed():
    assert content.allowed({}, content.every(OFF))
    assert content.allowed({"gore": MILD}, content.every(MILD))
    assert not content.allowed({"gore": FULL}, content.every(MILD))
    assert not content.allowed({"gore": MILD, "lgbt": MILD}, content.every(FULL, lgbt=OFF))


def test_presets():
    assert [p.key for p in content.PRESETS] == ["tame", "default", "spicy", "unabridged"]
    for preset in content.PRESETS:
        assert set(preset.limits) == set(content.BY_KEY)
        assert content.preset_for(dict(preset.limits)) is preset
    assert content.preset_for(content.every(FULL, gore=OFF)) is None
    # The default keeps bigotry against faiths and LGBTQ+ people, and harm to children, out.
    for key in ("faiths", "lgbt", "children", "suicide"):
        assert content.DEFAULT.limits[key] == OFF
        assert content.PRESETS_BY_KEY["spicy"].limits[key] <= MILD


def test_categories_fit_discord():
    for category in content.CATEGORIES:
        assert re.fullmatch(r"[a-z]{1,32}", category.key)
        assert len(f"How much {category.name.lower()} to allow") <= 100
        assert len(category.about) < 900


# What ktdi left out of its hand-picked tips (its tests/test_malleus.py), less "confess", which here is as often
# the sacrament. A tame server must see none of it.
GRIM = re.compile(r"tortur|\brack\b|torment|strappado|\bburn|\bflames?\b|\bstake\b|execut|put to death|\bkill|\bslay|"
                  r"\bslain|\bhang|gallows|\bnaked|\bshav|prison|\bchains?\b|secular arm|\bsentenc|punish|"
                  r"\bchild|\binfant|\bbab(y|ies)|midwi|unbaptized|\babort|\brape|put to the question", re.I)


def test_a_tame_server_sees_nothing_grim():
    tame = content.PRESETS_BY_KEY["tame"].limits
    leaks = [p.text for p in malleus.PASSAGES if content.allowed(p.tags, tame) and GRIM.search(p.text)]
    assert leaks == []


def test_every_preset_leaves_plenty():
    for preset in content.PRESETS:
        assert len(malleus.matching(preset.limits)) >= 900, preset.key
