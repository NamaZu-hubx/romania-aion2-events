"""Actualizare unica a panoului AION 2; potrivit pentru GitHub Actions."""
import asyncio
import logging
import os
from datetime import datetime, timezone

import discord
from dotenv import load_dotenv
from events_bot import fetch_source, make_embed

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
LOG = logging.getLogger('romania-events-once')

class OnceBot(discord.Client):
    async def on_ready(self):
        if getattr(self, '_started', False):
            return
        self._started = True
        try:
            guild_id = os.getenv('DISCORD_GUILD_ID', '').strip()
            guild = self.get_guild(int(guild_id)) if guild_id else (self.guilds[0] if len(self.guilds) == 1 else None)
            if guild is None:
                raise RuntimeError('Serverul nu a fost gasit; verifica DISCORD_GUILD_ID')
            channel = discord.utils.get(guild.text_channels, name='event-timers')
            if channel is None:
                raise RuntimeError('Canalul event-timers nu a fost gasit')
            rows = await asyncio.to_thread(fetch_source)
            embed = make_embed(rows, datetime.now(timezone.utc))
            panel = None
            async for msg in channel.history(limit=100):
                if msg.author.id == self.user.id and any(e.title == embed.title for e in msg.embeds):
                    panel = msg
                    break
            if panel:
                await panel.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                LOG.info('Panoul existent a fost actualizat')
            else:
                await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                LOG.info('Panou creat')
        except Exception:
            LOG.exception('Actualizarea a esuat')
            self.failed = True
        finally:
            await self.close()

async def main():
    token = os.getenv('DISCORD_BOT_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Lipseste DISCORD_BOT_TOKEN')
    bot = OnceBot(intents=discord.Intents.default())
    bot.failed = False
    await bot.start(token)
    if bot.failed:
        raise SystemExit(1)

if __name__ == '__main__':
    asyncio.run(main())
