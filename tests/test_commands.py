"""The slash commands (hammered/commands.py), run against fake interactions, and their registration."""

import re

import discord
import pytest

from hammered import commands, content, db, malleus
from hammered.bot import HammeredBot
from tests.fakes import Guild, Interaction, User, run


def choice(value, name="x"):
    return discord.app_commands.Choice(name=name, value=value)


def subcommand(name):
    return commands.setup.get_command(name)


def test_hammered_posts_a_passage():
    interaction = Interaction()
    run(commands.hammered_command.callback(interaction))
    embed = interaction.last.embed
    assert embed.title == "🧹 Witch-finding advice" and not interaction.last.ephemeral
    passage = malleus.BY_ID[embed.footer.text.rsplit("#", 1)[1]]
    assert content.allowed(passage.tags, content.DEFAULT.limits)


def test_hammered_about():
    interaction = Interaction()
    run(commands.hammered_command.callback(interaction, about="hail"))
    assert "hail" in interaction.last.embed.description.lower()


def test_hammered_says_why_theres_nothing():
    db.set_limits(111, content.every(content.OFF))
    interaction = Interaction()
    run(commands.hammered_command.callback(interaction, about="copulate"))
    assert interaction.last.ephemeral and "not that this server's filters allow" in interaction.last.content
    run(commands.hammered_command.callback(interaction, about="zzyzx"))
    assert "has nothing on **zzyzx**" in interaction.last.content


def test_hammered_in_a_dm_uses_the_default():
    interaction = Interaction(guild=None)
    run(commands.hammered_command.callback(interaction))
    assert interaction.last.embed is not None


def test_setup_a_category_changes_what_the_server_sees():
    interaction = Interaction()
    run(subcommand("gore").callback(interaction, level=choice(content.OFF)))
    assert db.limits(111)["gore"] == content.OFF and db.limits(222)["gore"] == content.MILD  # Only this server
    assert interaction.last.ephemeral and "is now 🚫 off" in interaction.last.content
    for _ in range(30):
        run(commands.hammered_command.callback(interaction))
        passage = malleus.BY_ID[interaction.last.embed.footer.text.rsplit("#", 1)[1]]
        assert "gore" not in passage.tags


def test_setup_lgbt_friendly():
    run(subcommand("lgbt").callback(Interaction(), level=choice(content.OFF)))
    assert not any("lgbt" in p.tags for p in malleus.matching(db.limits(111)))


def test_setup_preset_and_show():
    interaction = Interaction()
    run(subcommand("preset").callback(interaction, preset=choice("unabridged")))
    assert db.limits(111) == content.every(content.FULL)
    assert "**Preset:** 🔥 Unabridged" in interaction.last.embed.description
    run(subcommand("misogyny").callback(interaction, level=choice(content.MILD)))
    assert "**Preset:** custom" in interaction.last.embed.description
    run(subcommand("reset").callback(interaction))
    assert db.limits(111) == content.DEFAULT.limits
    run(subcommand("show").callback(interaction))
    assert "**Preset:** ⚖️ Tasteful" in interaction.last.embed.description


def test_setup_hide_and_unhide():
    passage = malleus.matching(content.DEFAULT.limits)[0]
    interaction = Interaction()
    run(subcommand("hide").callback(interaction, passage=f"#{passage.id.upper()}"))
    assert "is now hidden" in interaction.last.content and passage.id in db.hidden(111)
    run(subcommand("hide").callback(interaction, passage=passage.id))
    assert "was already hidden" in interaction.last.content
    run(subcommand("hide").callback(interaction, passage="nope"))
    assert "There's no passage `#nope`" in interaction.last.content
    run(subcommand("unhide").callback(interaction, passage=passage.id))
    assert passage.id not in db.hidden(111)
    run(subcommand("unhide").callback(interaction, passage=passage.id))
    assert "wasn't hidden" in interaction.last.content


@pytest.mark.parametrize("suspect, title", [
    (User(2, "agnes"), "🔥 agnes stands accused"),
    (User(1, "scott"), "🧹 scott has confessed"),
    (User(999, "Hammered of Witches"), "🔨 The Hammer will not be accused"),
])
def test_accuse(suspect, title):
    interaction = Interaction()
    run(commands.accuse.callback(interaction, suspect=suspect))
    assert interaction.last.embed.title == title
    assert interaction.last.allowed_mentions == commands.NO_PINGS
    assert re.search(r"\bwitch", interaction.last.embed.description, re.I)


def test_help():
    interaction = Interaction()
    run(commands.help_command.callback(interaction))
    embed = interaction.last.embed
    assert all(f"`{c.key}`" in embed.fields[1].value for c in content.CATEGORIES)
    assert len(embed) <= 6000 and all(len(f.value) <= 1024 for f in embed.fields)


def test_the_commands_register_within_discords_limits():
    bot = HammeredBot()
    names = {command.name for command in bot.tree.get_commands()}
    assert names == {"hammered", "accuse", "setup", "help"}
    for command in bot.tree.get_commands():
        payload = command.to_dict(bot.tree)
        stack = [payload]
        while stack:
            item = stack.pop()
            assert re.fullmatch(r"[-_a-z0-9]{1,32}", item["name"]), item["name"]
            assert 1 <= len(item["description"]) <= 100, item["description"]
            assert len(item.get("options", [])) <= 25 and len(item.get("choices", [])) <= 25
            assert all(len(c["name"]) <= 100 for c in item.get("choices", []))
            stack.extend(item.get("options", []))
    setup = commands.setup.to_dict(bot.tree)
    assert int(setup["default_member_permissions"]) == discord.Permissions(manage_guild=True).value
    assert {o["name"] for o in setup["options"]} >= set(content.BY_KEY) | {"show", "preset", "hide", "reset"}


def test_settings_embed_fits():
    embed = commands.settings_embed(Guild())
    assert len(embed.fields) == len(content.CATEGORIES) and len(embed) <= 6000


def test_leaving_a_server_forgets_it():
    db.set_level(111, "gore", content.FULL)
    db.hide(111, "abc123")
    run(HammeredBot().on_guild_remove(Guild(111)))
    assert db.limits(111) == content.DEFAULT.limits and db.hidden(111) == set()
