from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .buffer_client import BufferClient, BufferAPIError

STATUS_READ_SET = ["draft", "needs_approval", "scheduled", "sending", "sent", "error"]
ACTIVE_QUEUE_STATUSES = {"scheduled", "sending"}
CONSUMED_STATUSES = {"scheduled", "sending", "sent"}
MEDIA_REQUIRED = {"instagram", "tiktok"}


def load_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:20]


def parse_when(value: str, timezone: str) -> datetime:
    dt = datetime.fromisoformat(value)
    tz = ZoneInfo(timezone)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def iso_seconds(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


@dataclass(frozen=True)
class Execution:
    campaign_id: str
    brand: str
    topic: str
    service: str
    channel_id: str
    target_at: datetime
    text: str
    asset_filename: str | None
    media_url: str | None
    format: str
    idea_title: str
    idea_id: str | None = None
    requires_verification: bool = False
    hold: bool = False


class SocialScheduler:
    def __init__(self, client: BufferClient, settings: dict[str, Any], channels: dict[str, Any], backlog: list[dict[str, Any]], mode: str = "live"):
        self.client = client
        self.settings = settings
        self.channels = channels
        self.backlog = backlog
        self.mode = mode
        self.tz = ZoneInfo(settings["timezone"])
        self.actions: list[dict[str, Any]] = []

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def _asset_url(self, filename: str | None, explicit_url: str | None) -> str | None:
        if explicit_url: return explicit_url
        if not filename: return None
        repo = os.getenv("ASSET_REPOSITORY", self.settings.get("asset_repo", "")).strip()
        ref = os.getenv("ASSET_REF", self.settings.get("asset_ref", "main")).strip() or "main"
        return f"https://raw.githubusercontent.com/{repo}/{ref}/assets/{urllib.parse.quote(filename)}" if repo else None

    @staticmethod
    def _url_works(url: str) -> bool:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "socialscheduler/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as response: return 200 <= response.status < 400
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError): return False

    def expand(self) -> list[Execution]:
        out=[]
        for item in self.backlog:
            target_at=parse_when(item["target_at"],self.settings["timezone"])
            for service in item.get("services",[]):
                channel=self.channels.get(service); text=item.get("platform_text",{}).get(service) or item.get("text") or ""
                if not channel or not text.strip(): continue
                out.append(Execution(item["id"],item["brand"],item["topic"],service,channel["id"],target_at,text,item.get("asset_filename"),self._asset_url(item.get("asset_filename"),item.get("media_url")),item.get("format",{}).get(service,"post"),item.get("idea_title") or f"{item['brand']} | {item['topic']}",item.get("idea_id"),bool(item.get("requires_verification",False)),bool(item.get("hold_services",{}).get(service,False))))
        return out

    def _post_key(self,p): return (p.get("channelId",""),text_hash(p.get("text","")))
    def _execution_key(self,e): return (e.channel_id,text_hash(e.text))

    def _idea_exists(self, ideas: list[dict[str, Any]], execution: Execution) -> bool:
        title = normalize_text(execution.idea_title)
        return any(
            normalize_text((idea.get("content") or {}).get("title", "")) == title
            for idea in ideas
        )

    def ensure_ideas(self, executions: list[Execution], ideas: list[dict[str, Any]]) -> None:
        """Create missing legacy Buffer ideas without exceeding the configured cap."""
        existing_count = len(ideas)
        seen_campaigns: set[str] = set()
        for ex in sorted(executions, key=lambda item: item.target_at):
            if ex.campaign_id in seen_campaigns:
                continue
            seen_campaigns.add(ex.campaign_id)
            if self._idea_exists(ideas, ex):
                continue
            if existing_count >= int(self.settings.get("idea_limit", 100)):
                self.actions.append({"type": "blocked", "campaign": ex.campaign_id, "reason": "idea_limit"})
                return

            source = next(item for item in self.backlog if item["id"] == ex.campaign_id)
            content: dict[str, Any] = {
                "title": ex.idea_title,
                "text": source.get("idea_text") or source.get("text") or ex.text,
                "date": iso_seconds(ex.target_at),
                "services": source.get("services", []),
            }
            if ex.media_url and self._url_works(ex.media_url):
                content["media"] = [{
                    "url": ex.media_url,
                    "type": "image",
                    "alt": source.get("alt_text", ex.topic),
                }]
            if self.mode == "live":
                created = self.client.create_idea(self.settings["organization_id"], content)
                ideas.append(created)
            self.actions.append({"type": "create_idea", "campaign": ex.campaign_id, "title": ex.idea_title})
            existing_count += 1

    @staticmethod
    def _fair_order(executions: list[Execution]) -> list[Execution]:
        """Round-robin brands while preserving chronological order within each brand."""
        per_brand: dict[str, list[Execution]] = {}
        for ex in sorted(executions, key=lambda item: (item.target_at, item.brand, item.service)):
            per_brand.setdefault(ex.brand, []).append(ex)

        ordered: list[Execution] = []
        while any(per_brand.values()):
            heads = sorted(
                (items[0].target_at, brand)
                for brand, items in per_brand.items()
                if items
            )
            for _, brand in heads:
                ordered.append(per_brand[brand].pop(0))
        return ordered

    def _future_target(self,ex,now):
        if ex.target_at > now+timedelta(minutes=2): return ex.target_at
        if self.settings.get("late_item_policy","defer") != "defer": return None
        candidate=now+timedelta(days=int(self.settings.get("late_item_defer_days",1)))
        return candidate.replace(hour=ex.target_at.hour,minute=ex.target_at.minute,second=0,microsecond=0)

    def _post_input(self,ex,due_at):
        d={"channelId":ex.channel_id,"schedulingType":"automatic","mode":"customScheduled","dueAt":iso_seconds(due_at),"text":ex.text,"source":f"socialscheduler:{ex.campaign_id}:{ex.service}","assets":[]}
        if ex.media_url and self._url_works(ex.media_url): d["assets"]=[{"image":{"url":ex.media_url}}]
        if ex.idea_id: d["ideaId"]=ex.idea_id
        if ex.service=="instagram": d["metadata"]={"instagram":{"type":ex.format,"shouldShareToFeed":ex.format=="reel"}}
        elif ex.service=="facebook": d["metadata"]={"facebook":{"type":ex.format}}
        return d

    def reconcile_and_fill(self,executions,posts):
        now=self.now(); horizon=now+timedelta(days=int(self.settings.get("future_horizon_days",7)))
        consumed={self._post_key(p) for p in posts if p.get("status") in CONSUMED_STATUSES}
        active=[p for p in posts if p.get("status") in ACTIVE_QUEUE_STATUSES]
        active_by_channel=Counter(p.get("channelId") for p in active)
        per_channel_limit=int(self.settings.get("queue_limit_per_channel",10))
        total_limit=int(self.settings.get("queue_limit",per_channel_limit*max(1,len(self.channels))))
        total_slots=max(0,total_limit-len(active)); creates=0; max_creates=int(self.settings.get("max_creates_per_run",30))
        candidates=[]
        for ex in executions:
            if ex.hold: self.actions.append({"type":"hold","campaign":ex.campaign_id,"service":ex.service}); continue
            if ex.requires_verification: self.actions.append({"type":"blocked","campaign":ex.campaign_id,"service":ex.service,"reason":"fresh_verification_required"}); continue
            if self._execution_key(ex) in consumed: continue
            due=self._future_target(ex,now)
            if not due or due>horizon: continue
            if ex.service in MEDIA_REQUIRED and (not ex.media_url or not self._url_works(ex.media_url)):
                self.actions.append({"type":"blocked","campaign":ex.campaign_id,"service":ex.service,"reason":"media_unavailable"}); continue
            candidates.append((due,ex))
        for due,ex in sorted(candidates,key=lambda x:(x[0],x[1].service,x[1].brand)):
            if creates>=total_slots or creates>=max_creates: break
            if active_by_channel[ex.channel_id]>=per_channel_limit:
                self.actions.append({"type":"channel_full","service":ex.service,"active":active_by_channel[ex.channel_id],"limit":per_channel_limit}); continue
            data=self._post_input(ex,due)
            if due<=now: continue
            if self.mode=="live":
                created=self.client.create_post(data); self.actions.append({"type":"scheduled","campaign":ex.campaign_id,"service":ex.service,"dueAt":created.get("dueAt"),"postId":created.get("id"),"publisher":"buffer"})
            else: self.actions.append({"type":"would_schedule","campaign":ex.campaign_id,"service":ex.service,"dueAt":iso_seconds(due),"publisher":"buffer"})
            active_by_channel[ex.channel_id]+=1; creates+=1
        if creates==0 and total_slots==0: self.actions.append({"type":"queue_full","active":len(active),"limit":total_limit})

    def run(self):
        org_id=self.settings["organization_id"]; account=self.client.account()
        if org_id not in {o["id"] for o in account.get("organizations",[])}: raise BufferAPIError(f"Configured organization {org_id} is not accessible")
        live={c["id"]:c for c in self.client.channels(org_id)}; missing=[m["id"] for m in self.channels.values() if m["id"] not in live]
        if missing: raise BufferAPIError(f"Configured Buffer channels are missing/disconnected: {missing}")
        posts=self.client.posts(org_id,STATUS_READ_SET); executions=self.expand(); self.reconcile_and_fill(executions,posts)
        return {"mode":self.mode,"organization":org_id,"timezone":self.settings["timezone"],"posts_seen":len(posts),"active_queue":sum(1 for p in posts if p.get("status") in ACTIVE_QUEUE_STATUSES),"queue_limit":self.settings["queue_limit"],"queue_limit_per_channel":self.settings.get("queue_limit_per_channel"),"actions":self.actions}
