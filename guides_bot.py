#!/usr/bin/env python3
"""AION 2 guide discovery and Discord publishing. No paid APIs.
Default MODE=check: inspect sources without posting or changing history.
MODE=publish: seed existing links on first run; post only later discoveries.
"""
import os, re, json, sys, logging, asyncio, hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup, NavigableString, Tag

logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
LOG=logging.getLogger("guides")
STATE=Path("guides_state.json")
SOURCES=[
 ("Daeva Guides","https://daevaguides.com/en/guides/","daevaguides.com"),
 ("Aion2t","https://aion2t.com/guides","aion2t.com"),
]  # Aion Builds excluded while articles are marked Pre-Launch Data
CATEGORIES=[
 ("class-builds",["class","build","gladiator","templar","assassin","ranger","sorcerer","spiritmaster","cleric","chanter","stigma"]),
 ("dungeons-bosses",["dungeon","boss","expedition","raid","fire temple","krao cave"]),
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
    if domain == "aion2t.com":
        return discover_aion2t(name,url,domain)
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
def discover_aion2t(name,url,domain):
    response=requests.get(url,headers=HEADERS,timeout=25)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    found={}
    for a in soup.select("a[href]"):
        href=canonical(urljoin(url,a["href"]))
        p=urlparse(href)
        if p.netloc.lower().removeprefix("www.")!=domain: continue
        parts=p.path.strip("/").split("/")
        if len(parts)!=2 or parts[0]!="guides" or parts[1] in ("", "index"): continue
        heading=a.find(["h2","h3","h4"])
        title=" ".join((heading or a).get_text(" ",strip=True).split())
        if not (8<=len(title)<=180):
            title=parts[1].replace("-"," ").title()
        found[href]={"title":title,"source":name,"url":href}
    LOG.info("AION2T DISCOVERY: %d guides",len(found))
    return found

def discover_class_pages():
    url="https://daevaguides.com/en/"
    response=requests.get(url,headers=HEADERS,timeout=25)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    found={}
    names=("gladiator","templar","assassin","ranger","sorcerer","spiritmaster","cleric","chanter")
    for a in soup.select("a[href]"):
        href=canonical(urljoin(url,a["href"]))
        p=urlparse(href)
        if p.netloc.lower().removeprefix("www.")!="daevaguides.com":continue
        path=p.path.lower().strip("/").split("/")
        matches=[c for c in names if c in path]
        if len(matches)!=1:continue
        cls=matches[0]
        if href not in found:
            found[href]={"title":cls.title()+" — Full Class Guide","source":"Daeva Guides","url":href,"class_channel":cls}
    LOG.info("DAEVA CLASS PAGES: %d found",len(found))
    return found

def channel_for(item):
    hay=(item["title"]+" "+urlparse(item["url"]).path.replace("-"," ")).lower()
    for channel,terms in CATEGORIES:
        if any(re.search(r"\b"+re.escape(term)+r"\b",hay) for term in terms):
            return channel
    return "guides-library"

# v7: Full-text republication is intended only for sources where you hold permission.
# Discord limits messages to 2,000 characters. Split by paragraphs and preserve order.
def extract_article(item):
    response=requests.get(item["url"],headers=HEADERS,timeout=35)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    for tag in soup.select("script,style,nav,footer,header,aside,form,iframe,noscript,svg"):
        tag.decompose()
    candidates=[]
    for selector in ("article", "main article", "main", "[itemprop='articleBody']", ".prose", ".article-content", ".post-content"):
        for node in soup.select(selector):
            score=len(node.get_text(" ",strip=True))
            if score>250: candidates.append((score,node))
        if candidates: break
    if not candidates:
        raise RuntimeError(f"Article body not located for {item['url']}; refusing to publish navigation")
    root=max(candidates,key=lambda x:x[0])[1]
    # Remove page chrome embedded within the article container.
    for node in root.select("nav,aside,.breadcrumb,.breadcrumbs,.related,.share,.social,.toc,.table-of-contents"):
        node.decompose()
    blocks=[]
    for node in root.find_all(["h1","h2","h3","h4","p","li","pre","blockquote","table","img"],recursive=True):
        if node.find_parent(["p","li","pre","blockquote","table"]):
            continue
        if node.name=="img":
            src=node.get("src") or node.get("data-src")
            if src:
                blocks.append("Image: "+urljoin(item["url"],src))
            continue
        if node.name=="table":
            rows=[]
            for tr in node.select("tr"):
                vals=[" ".join(c.stripped_strings) for c in tr.find_all(["th","td"],recursive=False)]
                if vals: rows.append(" | ".join(vals))
            if rows: blocks.append("\n".join(rows))
            continue
        value=" ".join(node.stripped_strings)
        if not value: continue
        if node.name.startswith("h"):
            value="**"+value.replace("*", "")+"**"
        elif node.name=="li":
            value="• "+value
        elif node.name=="blockquote":
            value="> "+value
        blocks.append(value)
    body="\n\n".join(blocks).strip()
    if len(body)<350:
        raise RuntimeError(f"Article extraction too short ({len(body)} chars) for {item['url']}")
    return body

def chunks(body, limit=1850):
    result=[]
    current=""
    for paragraph in body.split("\n\n"):
        paragraph=paragraph.strip()
        if not paragraph: continue
        while len(paragraph)>limit:
            cut=paragraph.rfind(" ",0,limit)
            if cut<limit//2: cut=limit
            head,paragraph=paragraph[:cut],paragraph[cut:].lstrip()
            if current: result.append(current);current=""
            result.append(head)
        if len(current)+len(paragraph)+2>limit:
            if current:result.append(current)
            current=paragraph
        else:
            current=(current+"\n\n"+paragraph).strip()
    if current: result.append(current)
    return result

def read_state():
    if not STATE.exists(): return {"version":7,"guides":{}}
    old=json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(old,dict):raise ValueError("Bad state JSON")
    # Old `seen` is only an index of URLs, not proof that full guides were posted.
    return {"version":7,"guides":old.get("guides",{})}

def save_state(state):
    tmp=STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(STATE)

def channel_for_full(item):
    if item.get("class_channel"): return item["class_channel"]
    if item["source"]=="Aion2t":
        return "dungeons-bosses" if any(w in item["title"].lower() for w in ("dungeon","temple","cave","sanctuary","boss","den","canyon","citadel","island","draupnir","hall","cradle","research","nightmare","mirror")) else "guides-library"
    slug=urlparse(item["url"]).path.lower()
    if any(x in slug for x in ("field-boss", "fire-temple", "krao-cave", "dungeon")):
        return "dungeons-bosses"
    if "stigma" in slug: return "class-builds"
    return channel_for(item)

async def sync_discord(items,state,token,guild_id):
    import discord
    client=discord.Client(intents=discord.Intents.default())
    allowed=discord.AllowedMentions.none()
    @client.event
    async def on_ready():
        try:
            guild=client.get_guild(int(guild_id))
            if not guild: raise RuntimeError("Discord guild not found")
            for index,(item,body,digest) in enumerate(items,1):
                url=item["url"]
                saved=state["guides"].get(url,{})
                if saved.get("hash")==digest and saved.get("complete"):
                    LOG.info("Unchanged: %s",url);continue
                channel_name=saved.get("channel") or channel_for_full(item)
                channel=discord.utils.get(guild.text_channels,name=channel_name)
                if channel is None:raise RuntimeError(f"Missing channel #{channel_name}")
                try:
                    if saved.get("message_id"):
                        message=await channel.fetch_message(int(saved["message_id"]))
                    else:
                        embed=discord.Embed(title=item["title"][:256],url=url,
                            description="Full guide in the thread below. Source: "+item["source"],color=0x334472)
                        message=await channel.send(embed=embed,allowed_mentions=allowed)
                        saved={"channel":channel_name,"message_id":message.id,"thread_id":None,"part_ids":[],"complete":False}
                        state["guides"][url]=saved;save_state(state)
                    if saved.get("thread_id"):
                        thread=client.get_channel(int(saved["thread_id"])) or await client.fetch_channel(int(saved["thread_id"]))
                    else:
                        thread=await message.create_thread(name=item["title"][:100],auto_archive_duration=1440)
                        saved["thread_id"]=thread.id;save_state(state)
                    parts=chunks(body)
                    if len(parts)>150:raise RuntimeError(f"Guide too long ({len(parts)} messages): {url}")
                    # Edits are in place, not duplicate threads. Save after every part so a retry resumes.
                    ids=saved.setdefault("part_ids",[])
                    for n,part in enumerate(parts):
                        payload=f"**Part {n+1}/{len(parts)}**\n{part}"
                        if n<len(ids):
                            old=await thread.fetch_message(int(ids[n]))
                            if old.content!=payload:await old.edit(content=payload,allowed_mentions=allowed)
                        else:
                            new=await thread.send(payload,allowed_mentions=allowed)
                            ids.append(new.id);save_state(state)
                        await asyncio.sleep(0.35)
                    for extra in ids[len(parts):]:
                        old=await thread.fetch_message(int(extra));await old.delete()
                    saved["part_ids"]=ids[:len(parts)]
                    saved["hash"]=digest
                    saved["complete"]=True
                    saved["title"]=item["title"]
                    saved["updated_at"]=datetime.now(timezone.utc).isoformat()
                    save_state(state)
                    LOG.info("Synced %d/%d: %s (%d parts) -> #%s",index,len(items),url,len(parts),channel_name)
                except Exception:
                    save_state(state)
                    LOG.exception("Could not sync %s",url)
                    raise
        finally:
            await client.close()
    await client.start(token)

def main():
    mode=os.getenv("GUIDES_MODE","check").lower()
    if mode not in ("check","publish"):raise ValueError("GUIDES_MODE must be check or publish")
    found={}
    for name,url,domain in SOURCES:
        items=discover(name,url,domain)
        if not items:raise RuntimeError(f"No guide links found for {name}; refusing empty scrape")
        found.update(items)
    class_items=discover_class_pages()
    found.update(class_items)
    state=read_state()
    prepared=[]
    failures=[]
    for item in found.values():
        try:
            body=extract_article(item)
            digest=hashlib.sha256(body.encode("utf-8")).hexdigest()
            if state["guides"].get(item["url"],{}).get("hash")==digest and state["guides"][item["url"]].get("complete"):
                continue
            prepared.append((item,body,digest))
            LOG.info("READY [%s] %s: %d chars, %d messages",channel_for_full(item),item["title"],len(body),len(chunks(body)))
        except Exception as e:
            failures.append((item["url"],str(e)))
    if failures:
        for url,error in failures:LOG.error("Extraction failed %s: %s",url,error)
        raise RuntimeError("Extraction failed; no publishing (avoids incomplete import)")
    LOG.info("Discovered %d guides; %d need publishing/updating",len(found),len(prepared))
    if mode=="check":
        LOG.info("CHECK ONLY: no Discord messages or state changes")
        return
    if prepared:
        asyncio.run(sync_discord(prepared,state,os.environ["DISCORD_BOT_TOKEN"],os.environ["DISCORD_GUILD_ID"]))
    save_state(state)

if __name__=="__main__":
    main()
