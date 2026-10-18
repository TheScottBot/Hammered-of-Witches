"""The slash commands: /hammered, /accuse, /setup and /help.

/setup is only shown to people with Manage Server (Discord's default_permissions; a server can change who sees it
under Server Settings → Integrations). Its replies are only visible to whoever ran it.

A server's filters apply in all its channels, unless a channel has its own (/setup here): a channel only overrides
the categories it sets, and follows the server for the rest. Threads follow their parent channel. Hidden passages
are hidden in every channel.
"""

import logging
import re

import discord
from discord import app_commands

from hammered import content, db, malleus

log = logging.getLogger("hammered")
NO_PINGS = discord.AllowedMentions.none()
# /accuse wants evidence: passages about witches themselves, not the inquisitors' paperwork.
EVIDENCE = re.compile(r"\bwitch(es)?\b", re.I)


def where(interaction: discord.Interaction) -> int:
    """Whose recent passages to avoid repeating: the server's, or (in DMs) the person's."""
    return interaction.guild_id if interaction.guild_id is not None else -interaction.user.id


def channel_of(interaction: discord.Interaction) -> int | None:
    """The channel whose filters apply: a thread follows its parent channel's."""
    if isinstance(interaction.channel, discord.Thread):
        return interaction.channel.parent_id
    return interaction.channel_id


def limits_here(interaction: discord.Interaction) -> dict[str, int]:
    return db.limits(interaction.guild_id, channel_of(interaction))


def nothing_found(about: str, limits: dict[str, int]) -> str:
    if about and malleus.matching(content.every(content.FULL), about=about):
        return (f"The Malleus does have something on **{discord.utils.escape_markdown(about)}**, but not that the "
                f"filters here allow. (`/setup here show` has them.)")
    if about:
        return f"The Malleus has nothing on **{discord.utils.escape_markdown(about)}**. Try another word."
    return "Nothing in the Malleus gets past the filters here. (`/setup here show` has them.)"


@app_commands.command(name="hammered",
                      description="Witch-finding advice from the Hammer of Witches (Malleus Maleficarum, 1486).")
@app_commands.describe(about="Only advice that mentions this, e.g. milk, hail, ointment, cats, members")
async def hammered_command(interaction: discord.Interaction, about: str = ""):
    """A random passage of the Malleus Maleficarum, the inquisitors' witch-hunting manual of 1486, linked to its
    page in the 1928 translation. Give `about:` for passages that mention something (all the words you give)."""
    limits = limits_here(interaction)
    passage = malleus.pick(where(interaction), limits, db.hidden(interaction.guild_id), about.strip())
    if passage is None:
        await interaction.response.send_message(nothing_found(about.strip(), limits), ephemeral=True)
        return
    await interaction.response.send_message(embed=malleus.embed(passage, limits))


@app_commands.command(name="accuse", description="Present the Malleus's evidence that someone is a witch.")
@app_commands.describe(suspect="Who stands accused")
async def accuse(interaction: discord.Interaction, suspect: discord.User):
    """Accuse someone of witchcraft, with a passage of the Malleus as the evidence against them. (They're named,
    not pinged.)"""
    limits = limits_here(interaction)
    passage = malleus.pick(where(interaction), limits, db.hidden(interaction.guild_id), must=EVIDENCE)
    if passage is None:
        await interaction.response.send_message(nothing_found("", limits), ephemeral=True)
        return
    if suspect.id == interaction.client.user.id:
        title = "🔨 The Hammer will not be accused"
    elif suspect.id == interaction.user.id:
        title = f"🧹 {suspect.display_name} has confessed"
    else:
        title = f"🔥 {suspect.display_name} stands accused"
    embed = malleus.embed(passage, limits, title=title)
    await interaction.response.send_message(f"{interaction.user.mention} accuses {suspect.mention} of witchcraft.",
                                            embed=embed, allowed_mentions=NO_PINGS)


# --- /setup ---

LEVEL_CHOICES = [
    app_commands.Choice(name="off: strip it all out", value=content.OFF),
    app_commands.Choice(name="mild: passing mentions only", value=content.MILD),
    app_commands.Choice(name="full: as the inquisitors wrote it", value=content.FULL),
]
LEVEL_LABELS = {content.OFF: "🚫 off", content.MILD: "🟡 mild", content.FULL: "🔥 full"}
PRESET_CHOICES = [app_commands.Choice(name=p.name, value=p.key) for p in content.PRESETS]
LOOSER_TIP = ("\n-# This channel now allows more than the rest of the server. Worth saying so in its topic, so "
              "people know what they're in for, or can mute it.")

setup = app_commands.Group(name="setup", description="Choose what the Malleus may say in this server.",
                           guild_only=True, default_permissions=discord.Permissions(manage_guild=True))
here = app_commands.Group(name="here", description="Give this channel filters of its own, over the server's.",
                          parent=setup)


def preset_name(limits: dict[str, int]) -> str:
    preset = content.preset_for(limits)
    return preset.name if preset else "custom"


def allowed_line(limits: dict[str, int], guild_id: int) -> str:
    allowed = len(malleus.matching(limits, db.hidden(guild_id)))
    return f"**Preset:** {preset_name(limits)}\n**Passages allowed:** {allowed:,} of {len(malleus.PASSAGES):,}"


def settings_embed(guild: discord.Guild) -> discord.Embed:
    limits = db.limits(guild.id)
    embed = discord.Embed(title=f"⚙️ The Malleus in {guild.name}", color=malleus.COLOR,
                          description=allowed_line(limits, guild.id))
    for category in content.CATEGORIES:
        embed.add_field(name=f"{category.emoji} {category.name}",
                        value=f"{LEVEL_LABELS[limits[category.key]]} · `/setup {category.key}`", inline=True)
    own = db.channels(guild.id)
    if own:
        lines = [f"<#{channel_id}>: {preset_name(db.limits(guild.id, channel_id))}" for channel_id in own]
        if len(lines) > 15:
            lines = lines[:15] + [f"…and {len(lines) - 15} more"]
        embed.add_field(name="Channels with filters of their own", value="\n".join(lines), inline=False)
    hidden = len(db.hidden(guild.id))
    embed.set_footer(text=f"{hidden} passage{'s' if hidden != 1 else ''} hidden by hand. /setup preset changes "
                          "everything at once, /setup here one channel.")
    return embed


def looser(interaction: discord.Interaction) -> bool:
    """Whether this channel allows more than its server anywhere."""
    server = db.limits(interaction.guild_id)
    return any(level > server[key] for key, level in limits_here(interaction).items())


def channel_embed(interaction: discord.Interaction) -> discord.Embed:
    channel_id = channel_of(interaction)
    own, limits = db.channel_levels(channel_id), limits_here(interaction)
    embed = discord.Embed(title="⚙️ The Malleus in this channel", color=malleus.COLOR,
                          description=f"<#{channel_id}>\n{allowed_line(limits, interaction.guild_id)}")
    for category in content.CATEGORIES:
        source = f"set here · `/setup here {category.key}`" if category.key in own else "the server's"
        embed.add_field(name=f"{category.emoji} {category.name}",
                        value=f"{LEVEL_LABELS[limits[category.key]]} · {source}", inline=True)
    embed.set_footer(text="What isn't set here follows the server's filters. "
                          "/setup here reset to follow them for everything again.")
    return embed


@setup.command(name="show", description="Show this server's filters.")
async def setup_show(interaction: discord.Interaction):
    await interaction.response.send_message(embed=settings_embed(interaction.guild), ephemeral=True)


@here.command(name="show", description="Show this channel's filters.")
async def here_show(interaction: discord.Interaction):
    await interaction.response.send_message(embed=channel_embed(interaction), ephemeral=True)


@setup.command(name="preset", description="Set every filter at once: tame, tasteful, spicy or unabridged.")
@app_commands.describe(preset="How much of the book this server sees")
@app_commands.choices(preset=PRESET_CHOICES)
async def setup_preset(interaction: discord.Interaction, preset: app_commands.Choice[str]):
    chosen = content.PRESETS_BY_KEY[preset.value]
    db.set_limits(interaction.guild_id, chosen.limits)
    log.info("[%s] preset set to %s", interaction.guild_id, chosen.key)
    await interaction.response.send_message(f"**{chosen.name}**: {chosen.about}", embed=settings_embed(interaction.guild),
                                            ephemeral=True)


@here.command(name="preset", description="Set every filter for this channel at once.")
@app_commands.describe(preset="How much of the book this channel sees")
@app_commands.choices(preset=PRESET_CHOICES)
async def here_preset(interaction: discord.Interaction, preset: app_commands.Choice[str]):
    chosen = content.PRESETS_BY_KEY[preset.value]
    db.set_channel_limits(interaction.guild_id, channel_of(interaction), chosen.limits)
    log.info("[%s] channel %s preset set to %s", interaction.guild_id, channel_of(interaction), chosen.key)
    tip = LOOSER_TIP if looser(interaction) else ""
    await interaction.response.send_message(f"This channel is now **{chosen.name}**: {chosen.about}{tip}",
                                            embed=channel_embed(interaction), ephemeral=True)


def category_command(category: content.Category, channel: bool = False) -> app_commands.Command:
    where_text = " in this channel" if channel else ""

    @app_commands.command(name=category.key,
                          description=f"How much {category.name.lower()} to allow{where_text}"[:100])
    @app_commands.describe(level="off strips it all out; mild allows passing mentions; full allows anything")
    @app_commands.choices(level=LEVEL_CHOICES)
    async def command(interaction: discord.Interaction, level: app_commands.Choice[int]):
        if channel:
            db.set_channel_limits(interaction.guild_id, channel_of(interaction), {category.key: level.value})
            log.info("[%s] channel %s %s set to %s", interaction.guild_id, channel_of(interaction), category.key,
                     level.value)
            embed, tip = channel_embed(interaction), LOOSER_TIP if looser(interaction) else ""
        else:
            db.set_level(interaction.guild_id, category.key, level.value)
            log.info("[%s] %s set to %s", interaction.guild_id, category.key, level.value)
            embed, tip = settings_embed(interaction.guild), ""
        await interaction.response.send_message(
            f"{category.emoji} **{category.name}** is now {LEVEL_LABELS[level.value]}{where_text}. "
            f"{category.about}{tip}", embed=embed, ephemeral=True)
    command.__doc__ = category.about
    return command


for _category in content.CATEGORIES:
    setup.add_command(category_command(_category))
    here.add_command(category_command(_category, channel=True))


@setup.command(name="hide", description="Never show one passage in this server again (its # is in the footer).")
@app_commands.describe(passage="The passage's id, from the footer: #a1b2c3")
async def setup_hide(interaction: discord.Interaction, passage: str):
    passage_id = passage.strip().lstrip("#").lower()
    if passage_id not in malleus.BY_ID:
        await interaction.response.send_message(f"There's no passage `#{passage_id}`. The id is at the end of a "
                                                "passage's footer.", ephemeral=True)
        return
    newly = db.hide(interaction.guild_id, passage_id)
    log.info("[%s] passage %s hidden", interaction.guild_id, passage_id)
    await interaction.response.send_message(f"Passage `#{passage_id}` {'is now' if newly else 'was already'} hidden "
                                            f"in this server. `/setup unhide` brings it back.", ephemeral=True)


@setup.command(name="unhide", description="Show a passage you hid again.")
@app_commands.describe(passage="The passage's id: #a1b2c3")
async def setup_unhide(interaction: discord.Interaction, passage: str):
    passage_id = passage.strip().lstrip("#").lower()
    if db.unhide(interaction.guild_id, passage_id):
        await interaction.response.send_message(f"Passage `#{passage_id}` can be shown here again.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Passage `#{passage_id}` wasn't hidden.", ephemeral=True)


@setup.command(name="reset", description="Back to the default (tasteful) filters in every channel, nothing hidden.")
async def setup_reset(interaction: discord.Interaction):
    db.forget(interaction.guild_id)
    log.info("[%s] filters reset", interaction.guild_id)
    await interaction.response.send_message("Back to the defaults, in every channel.",
                                            embed=settings_embed(interaction.guild), ephemeral=True)


@here.command(name="reset", description="Make this channel follow the server's filters again.")
async def here_reset(interaction: discord.Interaction):
    had = db.forget_channel(channel_of(interaction))
    log.info("[%s] channel %s reset", interaction.guild_id, channel_of(interaction))
    message = ("This channel follows the server's filters again." if had
               else "This channel had no filters of its own: it already follows the server's.")
    await interaction.response.send_message(message, embed=channel_embed(interaction), ephemeral=True)


# --- /help ---

@app_commands.command(name="help", description="What Hammered of Witches does, and how to set it up.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔨 Hammered of Witches", color=malleus.COLOR,
        description="Witch-finding advice from the *Malleus Maleficarum* (1486), the inquisitors' manual for "
                    "finding, trying and punishing witches, in Montague Summers' 1928 translation. It's history, "
                    "and dark comedy, not advice anyone should take. Every passage links to its page in the "
                    "scanned book.")
    embed.add_field(name="Commands", inline=False, value=(
        "`/hammered [about]`: a random passage, or one that mentions something\n"
        "`/accuse @someone`: the Malleus's evidence that they're a witch\n"
        "`/setup ...`: choose what this server sees (Manage Server)"))
    embed.add_field(name="Filters", inline=False, value=(
        "The book is full of misogyny, torture and worse. Each server chooses, per category, **off** (none of "
        "it), **mild** (passing mentions) or **full**:\n"
        + "\n".join(f"{c.emoji} `{c.key}`: {c.name}" for c in content.CATEGORIES)
        + "\n\nOr `/setup preset`: "
        + ", ".join(f"**{p.name.split(' ', 1)[1]}**" for p in content.PRESETS)
        + ". New servers start on Tasteful. A passage that slips through can be hidden with `/setup hide`."))
    embed.add_field(name="One channel, different rules", inline=False, value=(
        "`/setup here ...` does the same for just the channel you're in: `/setup here preset` or "
        "`/setup here gore level:full`. Say, a channel for the grim stuff that people can mute, while the rest "
        "of the server stays tame. A channel follows the server for anything it doesn't set; "
        "`/setup here reset` undoes it."))
    embed.set_footer(text="Tagging is done by keyword, so it errs on the strict side, but isn't perfect.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


COMMANDS = [hammered_command, accuse, setup, help_command]
