#!/usr/bin/env python3
"""AION 2 guide discovery and Discord publishing. No paid APIs.
Default MODE=check: inspect sources without posting or changing history.
MODE=publish: seed existing links on first run; post only later discoveries.
"""
import os, re, json, sys, logging, asyncio
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
LOG=logging.getLogger("guides")
STATE=Path("guides_state.json")
SOURCES=[
 ("Daeva Guides","https://daevaguides.com/en/guides/","daevaguides.com"),
 ("Aion Builds","https://aionbuilds.com/en/guides","aionbuilds.com"),
]
CATEGORIES=[
 ("class-builds",["class","build","gladiator","templar","assassin","ranger","sorcerer","spiritmaster","cleric","chanter","stigma"]),
 ("dungeons-bosses",["dungeon","boss","expedition","raid"]),
 ("pvp-abyss",["pvp","abyss","siege","rift","arena"]),
 ("gear-progression",["gear","equipment","progression","enhancement","daevanion","enchant"]),
 ("crafting-farming",["craft","farming","gather","profession","material"]),
 ("maps-exploration",["map","exploration","location"]),
]
DESCRIPTIONS={
 "class-builds":"Ghid despre clase și build-uri AION 2.",
 "dungeons-bosses":"Ghid pentru dungeon-uri sau boss-uri AION 2.",
 "pvp-abyss":"Ghid despre PvP și Abyss în AION 2.",
 "gear-progression":"Ghid despre echipament și progresie în AION 2.",
 "crafting-farming":"Ghid despre crafting și farming în AION 2.",
 "maps-exploration":"Ghid despre explorare în AION 2.",
 "guides-library":"Ghid general AION 2.",
}
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; ROMANIA-Guides/1.0; personal Discord guide index)"}
def canonical(url):
    url=urldefrag(url)[0]
    p=urlparse(url)
    return p._replace(query="",fragment="",path=p.path.rstrip("/") or "/").geturl()
def discover(name,url,domain):
    response=requests.get(url,headers=HEADERS,timeout=25)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    found={}
    for a in soup.select("a[href]"):
        href=canonical(urljoin(response.url,a["href"]))
        p=urlparse(href)
        title=" ".join(a.get_text(" ",strip=True).split())
        if p.scheme not in ("http","https") or p.netloc.lower().removeprefix("www.")!=domain:
            continue
        if not title or len(title)<9 or len(title)>160:
            continue
        # Require explicit article/guide URL patterns, not category/navigation links.
        path=p.path.lower()
        if name=="Daeva Guides":
            acceptable=("/en/guides/" in path and path.rstrip("/")!="/en/guides" and path.count("/")>=4)
        else:
            acceptable=("/en/guides/" in path and path.rstrip("/")!="/en/guides" and path.count("/")>=4)
        if not acceptable or re.search(r"pre.launch|coming soon",title,re.I):
            continue
        if re.search(r"pre.launch|coming.soon|outdated",title+" "+href,re.I):
            continue
        found[href]={"title":title,"source":name,"url":href}
    return found
def channel_for(item):
    hay=(item["title"]+" "+urlparse(item["url"]).path.replace("-"," ")).lower()
    for channel,terms in CATEGORIES:
        if any(re.search(r"\b"+re.escape(term)+r"\b",hay) for term in terms):
            return channel
    return "guides-library"
def load_state():
    if STATE.exists():
        data=json.loads(STATE.read_text(encoding="utf-8"))
        if not isinstance(data,dict) or not isinstance(data.get("seen"),dict):
            raise ValueError("Invalid guides_state.json")
        return data
    return {"seen":{},"initialized":False}
async def publish(items,token,guild_id):
    import discord
    intents=discord.Intents.default()
    client=discord.Client(intents=intents)
    posted=[]
    @client.event
    async def on_ready():
        try:
            guild=client.get_guild(int(guild_id))
            if not guild: raise RuntimeError("Discord guild not found")
            for item in items:
                channel_name=channel_for(item)
                channel=discord.utils.get(guild.text_channels,name=channel_name)
                if channel is None: raise RuntimeError(f"Missing channel #{channel_name}")
                embed=discord.Embed(title=item["title"][:256],url=item["url"],
                    description=DESCRIPTIONS[channel_name],color=0x334472)
                embed.add_field(name="Sursă",value=item["source"])
                embed.set_footer(text="Link extern • Verificați compatibilitatea cu versiunea EU")
                await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
                posted.append(item["url"])
                LOG.info("Published %s to #%s",item["url"],channel_name)
        finally:
            await client.close()
    await client.start(token)
    return posted
def main():
    mode=os.getenv("GUIDES_MODE","check").lower()
    if mode not in ("check","publish"): raise ValueError("GUIDES_MODE must be check or publish")
    found={}
    failures=[]
    for name,url,domain in SOURCES:
        try:
            items=discover(name,url,domain)
            LOG.info("%s: %d candidate guides",name,len(items))
            if not items: failures.append(f"{name}: no matching article links")
            found.update(items)
        except Exception as e:
            failures.append(f"{name}: {e}")
    for failure in failures: LOG.warning(failure)
    if not found:
        raise RuntimeError("No source yielded guide links; no state changed")
    if mode=="check":
        for item in list(found.values())[:12]:
            LOG.info("EXAMPLE [%s] %s -> %s",channel_for(item),item["title"],item["url"])
        LOG.info("CHECK ONLY: no Discord messages and no state changes")
        return
    # Never seed from a partially broken scrape: avoids treating old articles as new later.
    if failures:
        raise RuntimeError("Source errors in publish mode; no Discord messages/state changes")
    state=load_state()
    now=datetime.now(timezone.utc).isoformat()
    if not state["initialized"]:
        state["seen"]={url:now for url in found}
        state["initialized"]=True
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        LOG.info("First run: indexed %d existing guides without posting",len(found))
        return
    new=[item for url,item in found.items() if url not in state["seen"]]
    LOG.info("New candidates: %d",len(new))
    # Fail closed if the source suddenly expands; prevents accidental mass posting.
    if len(new)>5:
        raise RuntimeError("More than 5 new links; manual inspection needed; no posts")
    if new:
        token=os.environ["DISCORD_BOT_TOKEN"]
        guild_id=os.environ["DISCORD_GUILD_ID"]
        posted=asyncio.run(publish(new,token,guild_id))
        for url in posted: state["seen"][url]=now
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":
    main()
