#!/usr/bin/env python3
"""Create the eight AION 2 class channels once, without duplicates."""
import asyncio
import os
import discord

CATEGORY_NAME = "AION 2 GUIDES"
CLASSES = (
    "gladiator", "templar", "assassin", "ranger",
    "sorcerer", "spiritmaster", "cleric", "chanter",
)

class ChannelCreator(discord.Client):
    async def on_ready(self):
        try:
            guild = self.get_guild(int(os.environ["DISCORD_GUILD_ID"]))
            if guild is None:
                raise RuntimeError("Discord server not found; check DISCORD_GUILD_ID")
            category = next(
    (
        c for c in guild.categories
        if "AION 2 GUIDES" in c.name.upper()
    ),
    None
)
            if category is None:
                raise RuntimeError(f"Category '{CATEGORY_NAME}' not found. No channels created.")
            for name in CLASSES:
                existing = discord.utils.get(guild.text_channels, name=name)
                if existing:
                    if existing.category_id != category.id:
                        print(f"SKIP #{name}: already exists in another category (not moved)")
                    else:
                        print(f"SKIP #{name}: already exists")
                    continue
                await guild.create_text_channel(
                    name=name,
                    category=category,
                    topic=f"AION 2 {name.title()} guides: skills, PvE/PvP builds, gear and rotations.",
                    reason="Create dedicated AION 2 class guide channels",
                )
                print(f"CREATED #{name} in {CATEGORY_NAME}")
                await asyncio.sleep(1)
            print("DONE: class channels checked")
        finally:
            await self.close()

if __name__ == "__main__":
    print("START: create_class_channels.py", flush=True)

    client = ChannelCreator(intents=discord.Intents.default())

    print("Connecting to Discord...", flush=True)
    client.run(os.environ["DISCORD_BOT_TOKEN"])
