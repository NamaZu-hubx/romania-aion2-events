"""Publish one safe, original English guide preview in a Discord thread.
Run via GitHub Actions manual dispatch only. Does not modify guides_state.json.
"""
import os
import asyncio
import discord

TITLE = 'AION 2 — Leveling 1–45: Quick Start Guide (Preview)'
SOURCE = 'https://daevaguides.com/en/guides/leveling-1-45/index.html'
SECTIONS = [
    ('Getting started', 'Follow the main story and learn your class fundamentals early. Check newly unlocked skills and systems as you level. Keep your gear usable, but avoid spending scarce upgrade materials on equipment you will replace quickly.'),
    ('Leveling efficiently', 'Prioritize quests and activities that move your character forward. If you hit a level or power requirement, review available side activities and upgrades rather than repeatedly grinding low-value enemies.'),
    ('Combat habits', 'Practice your core skill rotation, defensive abilities, positioning, and resource management. Learn when to interrupt, dodge, or disengage; efficient combat reduces downtime.'),
    ('Preparing for level 45', 'Review your equipment, unlocked systems, daily and weekly activities, and dungeon requirements. Set goals for the next upgrade instead of spending resources without a plan.'),
    ('Important note', 'This is an original quick-start overview, not a verbatim reproduction of Daeva Guides. Exact quest priorities, level unlocks, and mechanics should be checked against the current EU game version.'),
]

async def main():
    token = os.environ['DISCORD_BOT_TOKEN']
    guild_id = int(os.environ['DISCORD_GUILD_ID'])
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    @client.event
    async def on_ready():
        try:
            guild = client.get_guild(guild_id)
            if not guild:
                raise RuntimeError('Guild not found. Check DISCORD_GUILD_ID.')
            channel = discord.utils.get(guild.text_channels, name='guides-library')
            if not channel:
                raise RuntimeError('Missing #guides-library channel')
            embed = discord.Embed(title=TITLE, description='A practical English quick-start overview. Open the thread below to read the chapters directly in Discord.', color=0x334472)
            embed.add_field(name='Read more', value=f'[Original reference]({SOURCE})', inline=False)
            embed.set_footer(text='ROMANIA | AION 2 • Preview • No pings')
            msg = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            thread = await msg.create_thread(name='Leveling 1–45 | Guide chapters', auto_archive_duration=1440)
            for index, (heading, body) in enumerate(SECTIONS, 1):
                await thread.send(f'**Chapter {index} — {heading}**\n\n{body}', allowed_mentions=discord.AllowedMentions.none())
            print(f'TEST POSTED channel=#{channel.name} thread_id={thread.id} chapters={len(SECTIONS)}')
        finally:
            await client.close()
    await client.start(token)

if __name__ == '__main__':
    asyncio.run(main())
