"""ROMANIA Manager: panou Discord bazat pe programul public Daeva Guides.
Nu foloseste API AI si nu modifica permisiunile serverului.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN', '').strip()
GUILD_ID = os.getenv('DISCORD_GUILD_ID', '').strip()
SOURCE = 'https://daevaguides.com/en/guides/timers/'
TZ = ZoneInfo('Europe/Bucharest')
UTC = timezone.utc
LOG = logging.getLogger('romania-events')

# Orele sunt EXTRASE si VALIDATE din tabelul UTC de pe pagina sursa.
# Pentru evenimente cu orar regional incert, afisam avertisment.
EVENTS = [
    ('⚔️ Spacetime Rift', 'Spacetime Rift', 'every3', False),
    ('🐉 Watcher Kaira', 'Watcher Kaira', 'every3', True),
    ('🏰 Artifact Siege', 'Artifact Siege', 'weekly', True),
    ('👹 Siege Bosses', 'Post-siege bosses', 'weekly', True),
    ('🔥 Guardian Lord Nahma', 'Guardian Lord Nahma', 'weekly', True),
    ('🎉 Shugo Festival', 'Shugo Festival', 'hourly', False),
    ('🌌 Dimensional Invasion', 'Dimensional Invasion', 'halfhour', False),
    ('🔄 Daily Reset', 'Daily reset', 'daily', False),
    ('📅 Weekly Reset', 'Weekly reset', 'weekly_reset', False),
]


def fetch_source():
    response = requests.get(SOURCE, timeout=20, headers={'User-Agent': 'ROMANIA-Discord-Event-Board/1.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    rows = []
    for tr in soup.select('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.select('th,td')]
        if len(cells) >= 2:
            rows.append(cells)
    if not rows:
        raise ValueError('Nu am gasit tabelul cu programul evenimentelor.')
    return rows


def extract_utc_cell(rows, key):
    for cells in rows:
        if key.casefold() in cells[0].casefold():
            # Daeva Guides: prima coloana = eveniment, a doua = UTC.
            return cells[1]
    return None


def parse_times(cell):
    return sorted({(int(h), int(m)) for h, m in re.findall(r'(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)', cell or '')})


def parse_weekdays(cell):
    names = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
             'friday': 4, 'saturday': 5, 'sunday': 6}
    return [num for name, num in names.items() if re.search(r'\b' + name + r'\b', cell or '', re.I)]


def next_utc(now, times, weekdays=None):
    candidates = []
    for days in range(9):
        day = (now + timedelta(days=days)).date()
        if weekdays is not None and day.weekday() not in weekdays:
            continue
        for hour, minute in times:
            dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)
            if dt > now:
                candidates.append(dt)
    return min(candidates) if candidates else None


def schedule(rows, now):
    results = []
    for label, key, kind, uncertain in EVENTS:
        cell = extract_utc_cell(rows, key)
        if cell is None:
            results.append((label, None, 'Orar indisponibil în sursă'))
            continue
        if kind == 'hourly':
            valid = 'every hour' in cell.lower() and ':00' in cell
            times, weekdays = [(h, 0) for h in range(24)], None
        elif kind == 'halfhour':
            valid = 'every hour' in cell.lower() and ':30' in cell
            times, weekdays = [(h, 30) for h in range(24)], None
        elif kind == 'daily':
            times, weekdays = parse_times(cell), None
            valid = bool(times) and '07:00' in cell
        elif kind == 'weekly_reset':
            times, weekdays = parse_times(cell), parse_weekdays(cell)
            valid = bool(times) and weekdays == [2] and '07:00' in cell
        elif kind == 'every3':
            times, weekdays = parse_times(cell), None
            valid = len(times) == 8 and all(times[i][0] % 3 == times[0][0] % 3 for i in range(8))
        else:
            times, weekdays = parse_times(cell), parse_weekdays(cell)
            valid = bool(times) and bool(weekdays)
        if not valid:
            results.append((label, None, 'Orar neinterpretabil / în curs de verificare'))
            continue
        start = next_utc(now, times, weekdays)
        results.append((label, start, 'Estimativ • sursele diferă' if uncertain else ''))
    return results


def make_embed(rows, checked_at):
    now = datetime.now(UTC)
    data = schedule(rows, now)
    embed = discord.Embed(title='📅 AION 2 | Programul evenimentelor',
                          description='🌍 Europe • Gauss • Elyos\n🕒 Orele sunt afișate pentru România.\n🔄 Același panou este actualizat automat.',
                          color=discord.Colour.blue())
    for title, subset in [('⚔️ Evenimente importante', data[:5]), ('🎮 Activități și resetări', data[5:])]:
        lines = []
        for name, start, note in subset:
            if start:
                local = start.astimezone(TZ)
                # Discord actualizeaza countdown-ul automat, fara editari la fiecare minut.
                value = f'{local:%a %d.%m, %H:%M} • <t:{int(start.timestamp())}:R>'
            else:
                value = '—'
            if note:
                value += f'\n   _{note}_'
            lines.append(f'**{name}**\n{value}')
        embed.add_field(name=title, value='\n\n'.join(lines), inline=False)
    embed.add_field(name='🎯 Arena of Tactics', value='Programul nu este confirmat în sursa selectată.', inline=False)
    embed.set_footer(text=f'Sursă: Daeva Guides • Verificat: {checked_at.astimezone(TZ):%d.%m.%Y %H:%M} RO • Orarul din joc are prioritate')
    return embed


class EventBot(discord.Client):
    async def on_ready(self):
        if getattr(self, '_started', False):
            return
        self._started = True
        LOG.info('Conectat ca %s', self.user)
        self.worker = asyncio.create_task(self.refresh_loop())

    async def refresh_loop(self):
        await self.wait_until_ready()
        guild = self.get_guild(int(GUILD_ID)) if GUILD_ID else (self.guilds[0] if len(self.guilds) == 1 else None)
        if guild is None:
            LOG.error('Serverul nu a fost gasit. Verifica DISCORD_GUILD_ID.')
            return
        channel = discord.utils.get(guild.text_channels, name='event-timers')
        if channel is None:
            LOG.error('Canalul #event-timers nu exista.')
            return
        while not self.is_closed():
            try:
                rows = await asyncio.to_thread(fetch_source)
                embed = make_embed(rows, datetime.now(UTC))
                # Gasim propriul panou dupa titlu, ca sa nu stergem alte mesaje.
                panel = None
                async for msg in channel.history(limit=100):
                    if msg.author.id == self.user.id and any(e.title == embed.title for e in msg.embeds):
                        panel = msg
                        break
                if panel:
                    await panel.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                else:
                    await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                LOG.info('Panou actualizat')
            except Exception:
                LOG.exception('Nu am putut actualiza programul. Panoul existent ramane neschimbat.')
            await asyncio.sleep(30 * 60)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if not TOKEN:
        raise SystemExit('Lipseste DISCORD_BOT_TOKEN in .env')
    intents = discord.Intents.default()
    bot = EventBot(intents=intents)
    bot.run(TOKEN)
