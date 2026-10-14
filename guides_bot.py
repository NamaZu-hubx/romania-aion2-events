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
]  # Aion Builds excluded while articles are marked Pre-Launch Data
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
    LOG.info("DIAGNOSTIC HTTP=%s final_url=%s html_bytes=%d page_title=%r", response.status_code, response.url, len(response.content), soup.title.get_text(" ",strip=True)[:150] if soup.title else "(none)")
    links=soup.select("a[href]")
    LOG.info("DIAGNOSTIC total_anchor_links=%d",len(links))
    for a in links[:30]:
        LOG.info("DIAGNOSTIC LINK text=%r href=%r",a.get_text(" ",strip=True)[:100],a.get("href","")[:220])
    LOG.info("DIAGNOSTIC guide_href_matches=%d",sum("/guides/" in a.get("href","") for a in links))
    found={}
    # Daeva Guides links point to /en/guides/<slug>/ or /index.html.
    # Accept real guide slugs, but exclude legal pages and navigation.
    excluded={"privacy", "terms", "imprint", "contact", "legal", "cookie", "cookies", "about", "index"}
    for a in soup.select("a[href]"):
        href=canonical(urljoin(url.rstrip("/") + "/", a["href"]))
        p=urlparse(href)
        if p.scheme not in ("http","https") or p.netloc.lower().removeprefix("www.")!=domain:
            continue
        path=p.path.lower().strip("/")
        parts=path.split("/")
        if len(parts)<3 or parts[:2]!=["en","guides"]:
            continue
        slug=parts[2]
        if slug in excluded or slug.startswith(("privacy-","terms-","imprint-","contact-")):
            continue
        if len(parts)>4 or (len(parts)==4 and parts[3]!="index.html"):
            LOG.info("FILTER REJECT path=%r",path)
            continue
        # Cards include title + long description + reading time in anchor text.
        # Use the heading instead of rejecting the entire anchor as too long.
        heading=a.find(["h2", "h3", "h4"])
        if heading:
            title=" ".join(heading.get_text(" ", strip=True).split())
        else:
            raw=" ".join(a.get_text(" ",strip=True).split())
            title=raw.split("Open the guide", 1)[0].strip()
        if not title or len(title)<9 or len(title)>180:
            LOG.info("FILTER REJECT title-length=%d slug=%r text=%r",len(title),slug,title[:110])
            continue
        LOG.info("FILTER ACCEPT slug=%r title=%r",slug,title[:110])
        # Prefer the most descriptive anchor if the same URL is repeated.
        if href not in found or len(title)>len(found[href]["title"]):
            found[href]={"title":title,"source":name,"url":href}
    LOG.info("FILTER RESULT: %d valid guide URLs", len(found))
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
        raise RuntimeError("No valid guide links found; no state changed")
    if mode=="check":
        for item in list(found.values())[:20]:
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
