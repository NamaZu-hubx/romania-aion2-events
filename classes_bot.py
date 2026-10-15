#!/usr/bin/env python3
"""ROMANIA Manager: self-service AION 2 class roles and emoji nicknames.

Run as a persistent Discord bot process (not a scheduled GitHub Action).
Environment: DISCORD_BOT_TOKEN, DISCORD_GUILD_ID.
Permissions: Manage Roles, Manage Nicknames.
Developer Portal: enable Server Members Intent.
"""
import os
import re
import logging
import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger("romania-classes")
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])
GUILD = discord.Object(id=GUILD_ID)
CLASSES = {
    "Gladiator": "⚔️",
    "Templar": "🛡️",
    "Ranger": "🏹",
    "Sorcerer": "🔥",
    "Assassin": "🥷",
    "Spiritmaster": "🔮",
    "Cleric": "💚",
    "Chanter": "🪄",
}
ROLE_PREFIX = "AION | "
# Remove only the class emoji managed by this bot; preserve rank-free player names.
EMOJI_PREFIX = re.compile(r"^(?:" + "|".join(re.escape(x) for x in CLASSES.values()) + r")\s+")
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


def class_roles(guild):
    return {name: discord.utils.get(guild.roles, name=ROLE_PREFIX + name)
            for name in CLASSES}


def clean_name(member):
    current = member.nick or member.name
    return EMOJI_PREFIX.sub("", current).strip()


async def update_nickname(member):
    roles = class_roles(member.guild)
    selected = [name for name, role in roles.items() if role and role in member.roles]
    if not selected:
        # Never modify members who have not selected a class.
        return
    name = clean_name(member)
    prefix = CLASSES[selected[0]] + " "
    # Discord nickname limit is 32 characters.
    desired = prefix + name[:32 - len(prefix)]
    if member.nick != desired:
        await member.edit(nick=desired, reason="ROMANIA Manager: AION 2 class emoji")


@bot.event
async def on_ready():
    if not getattr(bot, "_synced", False):
        await bot.tree.sync(guild=GUILD)
        bot._synced = True
    LOG.info("ROMANIA Manager class module ready as %s", bot.user)


@bot.tree.command(name="setup_clase", description="Creează rolurile celor 8 clase AION 2", guild=GUILD)
@app_commands.default_permissions(manage_roles=True)
async def setup_clase(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("Ai nevoie de Manage Roles.", ephemeral=True)
        return
    guild = interaction.guild
    existing = class_roles(guild)
    created = []
    try:
        for name in CLASSES:
            if existing[name] is None:
                await guild.create_role(name=ROLE_PREFIX + name,
                                        permissions=discord.Permissions.none(),
                                        mentionable=False,
                                        hoist=False,
                                        reason="ROMANIA Manager: AION 2 class selection")
                created.append(name)
    except discord.Forbidden:
        await interaction.response.send_message(
            "Nu pot crea roluri. Verifică Manage Roles și poziția botului.", ephemeral=True)
        return
    await interaction.response.send_message(
        "Rolurile claselor sunt pregătite. " +
        ("Create: " + ", ".join(created) if created else "Existau deja."),
        ephemeral=True)


@app_commands.choices(clasa=[
    app_commands.Choice(name=name, value=name) for name in CLASSES
])
@bot.tree.command(name="clasa", description="Alege clasa personajului tău AION 2", guild=GUILD)
async def clasa(interaction: discord.Interaction, clasa: app_commands.Choice[str]):
    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message("Comanda funcționează doar pe server.", ephemeral=True)
        return
    roles = class_roles(member.guild)
    target = roles[clasa.value]
    if target is None:
        await interaction.response.send_message(
            "Un administrator trebuie să ruleze /setup_clase mai întâi.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        remove = [role for role in roles.values()
                  if role and role != target and role in member.roles]
        if remove:
            await member.remove_roles(*remove, reason="AION 2 class changed")
        if target not in member.roles:
            await member.add_roles(target, reason="AION 2 class selected")
        await update_nickname(member)
    except discord.Forbidden:
        await interaction.followup.send(
            "Nu am permisiuni suficiente. Botul trebuie să fie deasupra rolurilor "
            "de clasă și să aibă Manage Roles + Manage Nicknames.", ephemeral=True)
        return
    await interaction.followup.send(
        f"Clasa selectată: {CLASSES[clasa.value]} **{clasa.value}**. "
        "Emoji-ul a fost aplicat nickname-ului.", ephemeral=True)


@bot.event
async def on_member_update(before, after):
    if before.roles == after.roles:
        return
    roles = class_roles(after.guild)
    relevant = {r.id for r in roles.values() if r}
    if ({r.id for r in before.roles} ^ {r.id for r in after.roles}) & relevant:
        try:
            await update_nickname(after)
        except discord.Forbidden:
            LOG.warning("Cannot update nickname for member %s", after.id)


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
