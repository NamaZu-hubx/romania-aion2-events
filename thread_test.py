"""One-time AION 2 guide preview. Run using existing GitHub Actions test workflow."""
import asyncio
import os
import discord

SOURCE = 'https://daevaguides.com/en/guides/leveling-1-45/index.html'
CHAPTERS = [
 ('01 | The fastest route', 'Prioritize gold main-story quests. Use green regional quests when your story progress is blocked by Ascension requirements. Avoid standing in one area to grind ordinary mobs. The guide estimates around 3–4 hours for experienced players and 5–6 hours for first-time players following the story; your pace may differ.'),
 ('02 | Ascension checkpoints', 'The main progression gates are around levels 22 and 32. When the Ascension Gauge blocks your story, complete nearby green quests first. Sealed Dungeons and Strongholds are additional activities that can contribute progress. Once the gauge is full, complete the Ascension quest to unlock the next stage.'),
 ('03 | Levels 1–22', 'Learn movement, combat, and loot settings while following the main story. Daevanion progression becomes relevant early on. At around level 20, Krao Cave is an early group-dungeon milestone. Save scarce dungeon-chest resources for more valuable rewards later, as the source recommends.'),
 ('04 | Levels 22–45', 'Stigma skills become available around level 22. Continue the main story, handle the second Ascension gate, and unlock additional dungeons as you progress. The guide identifies Fire Temple as a later leveling milestone. At level 45, finish the remaining story quests rather than stopping immediately.'),
 ('05 | Avoid common mistakes', 'Avoid investing expensive upgrades or Manastones into temporary leveling gear. Do not sell valuable gold-quality items without checking whether you will need them later. Prioritize permanent character progression and useful activities along your route. Check the original guide for caveats and version-specific details.'),
]

class Bot(discord.Client):
    async def on_ready(self):
        try:
            guild_id = int(os.environ['DISCORD_GUILD_ID'])
            guild = self.get_guild(guild_id)
            if guild is None:
                raise RuntimeError('Discord guild not found')
            channel = discord.utils.get(guild.text_channels, name='guides-library')
            if channel is None:
                raise RuntimeError('#guides-library not found')
            embed = discord.Embed(
                title='AION 2 — Leveling 1–45 | Practical Guide',
                description=('A concise English guide based on Daeva Guides, organized into five chapters. '
                             'Open the thread to read everything directly in Discord.\n\n'
                             f'[Read the original source]({SOURCE})'),
                color=0xD6AC59,
            )
            embed.set_footer(text='ROMANIA | AION 2 • Original summary • No pings')
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            thread = await message.create_thread(name='Leveling 1–45 | Guide chapters')
            for title, body in CHAPTERS:
                await thread.send(f'**{title}**\n\n{body}', allowed_mentions=discord.AllowedMentions.none())
                await asyncio.sleep(1)
            await thread.send(f'**Source and updates:** {SOURCE}\nInformation may change with patches. Check the source for the latest details.', allowed_mentions=discord.AllowedMentions.none())
            print(f'SUCCESS: created guide message {message.id} and thread {thread.id} with {len(CHAPTERS)} chapters')
        finally:
            await self.close()

if __name__ == '__main__':
    token = os.environ['DISCORD_BOT_TOKEN']
    intents = discord.Intents.default()
    Bot(intents=intents).run(token)
