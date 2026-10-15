#!/usr/bin/env python3
"""Synchronize AION 2 class emoji nicknames using Discord REST API.

Required: DISCORD_BOT_TOKEN, DISCORD_GUILD_ID.
Enable Server Members Intent in Discord Developer Portal.
The bot needs Manage Nicknames and a role higher than target members' top roles.
"""
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger("aion2-class-nicknames")
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = os.environ["DISCORD_GUILD_ID"]
BASE = "https://discord.com/api/v10"
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
PREFIX = re.compile(r"^(?:" + "|".join(re.escape(e) for e in CLASSES.values()) + r")\s+")


def api(method, path, payload=None):
    url = BASE + path
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    for attempt in range(5):
        request = urllib.request.Request(
            url, data=body, method=method,
            headers={"Authorization": "Bot " + TOKEN,
                     "User-Agent": "ROMANIA-Manager-NicknameSync/1.0",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
                return json.loads(data) if data else None
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                try:
                    delay = float(json.loads(exc.read()).get("retry_after", 2))
                except (ValueError, TypeError):
                    delay = 2
                time.sleep(min(max(delay, 1), 60))
                continue
            raise RuntimeError(f"Discord API {method} {path}: HTTP {exc.code}") from exc
    raise RuntimeError("Discord API rate limit retries exhausted")


def members():
    after = "0"
    while True:
        query = urllib.parse.urlencode({"limit": 1000, "after": after})
        page = api("GET", f"/guilds/{GUILD_ID}/members?{query}")
        if not page:
            break
        yield from page
        if len(page) < 1000:
            break
        after = page[-1]["user"]["id"]


def main():
    roles = api("GET", f"/guilds/{GUILD_ID}/roles")
    role_by_name = {r["name"]: r["id"] for r in roles}
    class_by_role = {}
    for name, emoji in CLASSES.items():
        # Support both manually created roles and earlier bot role naming.
        found = [role_by_name[n] for n in (name, "AION | " + name) if n in role_by_name]
        for role_id in found:
            class_by_role[role_id] = (name, emoji)
        if not found:
            LOG.warning("Missing Discord class role: %s", name)

    guild = api("GET", f"/guilds/{GUILD_ID}")
    owner_id = guild["owner_id"]
    me = api("GET", "/users/@me")
    own_id = me["id"]
    changed = skipped = failed = checked = 0
    for member in members():
        checked += 1
        user = member["user"]
        if user["id"] == own_id or user["id"] == owner_id or user.get("bot"):
            continue
        selected = [class_by_role[r] for r in member.get("roles", []) if r in class_by_role]
        if len(selected) != 1:
            if len(selected) > 1:
                LOG.warning("Member %s has multiple class roles; skipping", user["id"])
            skipped += 1
            continue
        name, emoji = selected[0]
        original = member.get("nick") or user.get("global_name") or user["username"]
        clean = PREFIX.sub("", original).strip()
        desired = (emoji + " " + clean)[:32].rstrip()
        if member.get("nick") == desired:
            continue
        try:
            api("PATCH", f"/guilds/{GUILD_ID}/members/{user['id']}",
                {"nick": desired})
            changed += 1
            LOG.info("Updated nickname for member %s: class %s", user["id"], name)
        except RuntimeError as exc:
            failed += 1
            LOG.warning("Cannot update member %s: %s", user["id"], exc)
    LOG.info("Checked=%s changed=%s skipped=%s failed=%s", checked, changed, skipped, failed)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
