from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
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

    @property
    def fingerprint(self) -> str:
        seed = "|".join([self.campaign_id, self.service, self.channel_id, normalize_text(self.text)])
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


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
        if explicit_url:
            return explicit_url
        if not filename:
            return None
        repo = os.getenv("ASSET_REPOSITORY", self.settings.get("asset_repo", "")).strip()
        ref = os.getenv("ASSET_REF", self.settings.get("asset_ref", "main")).strip() or "main"
        if not repo:
            return None
        quoted = urllib.parse.quote(filename)
        return f"https://raw.githubusercontent.com/{repo}/{ref}/assets/{quoted}"

    @staticmethod
    def _url_works(url: str) -> bool:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "socialscheduler/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                return 200 <= response.status < 400
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            return False

    def expand(self) -> list[Execution]:
        out: list[Execution] = []
        for item in self.backlog:
            target_at = parse_when(item["target_at"], self.settings["timezone"])
            for service in item.get("services", []):
                channel = self.channels.get(service)
                if not channel:
                    continue
                text = item.get("platform_text", {}).get(service) or item.get("text") or ""
                if not text.strip():
                    continue
                out.append(Execution(
                    campaign_id=item["id"],
                    brand=item["brand"],
                    topic=item["topic"],
                    service=service,
                    channel_id=channel["id"],
                    target_at=target_at,
                    text=text,
                    asset_filename=item.get("asset_filename"),
                    media_url=self._asset_url(item.get("asset_filename"), item.get("media_url")),
                    format=item.get("format", {}).get(service, "post"),
                    idea_title=item.get("idea_title") or f"{item['brand']} | {item['topic']}",
                    idea_id=item.get("idea_id"),
                    requires_verification=bool(item.get("requires_verification", False)),
                    hold=bool(item.get("hold_services", {}).get(service, False)),
                ))
        return out

    def _post_key(self, post: dict[str, Any]) -> tuple[str, str]:
        return (post.get("channelId", ""), text_hash(post.get("text", "")))

    def _execution_key(self, execution: Execution) -> tuple[str, str]:
        return (execution.channel_id, text_hash(execution.text))

    def _idea_exists(self, ideas: list[dict[str, Any]], execution: Execution) -> bool:
        title = normalize_text(execution.idea_title)
        return any(normalize_text((idea.get("content") or {}).get("title", "")) == title for idea in ideas)

    def ensure_ideas(self, executions: list[Execution], ideas: list[dict[str, Any]]) -> None:
        existing_count = len(ideas)
        seen_campaigns: set[str] = set()
        for ex in sorted(executions, key=lambda x: x.target_at):
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
            asset_url = ex.media_url
            if asset_url and self._url_works(asset_url):
                content["media"] = [{"url": asset_url, "type": "image", "alt": source.get("alt_text", ex.topic)}]
            if self.mode == "live":
                created = self.client.create_idea(self.settings["organization_id"], content)
                ideas.append(created)
            self.actions.append({"type": "create_idea", "campaign": ex.campaign_id, "title": ex.idea_title})
            existing_count += 1

    def _future_target(self, ex: Execution, now: datetime) -> datetime | None:
        if ex.target_at > now + timedelta(minutes=2):
            return ex.target_at
        policy = self.settings.get("late_item_policy", "defer")
        if policy == "skip":
            return None
        if policy == "defer":
            days = int(self.settings.get("late_item_defer_days", 3))
            candidate = now + timedelta(days=days)
            return candidate.replace(hour=ex.target_at.hour, minute=ex.target_at.minute, second=0, microsecond=0)
        return None

    def _fair_order(self, executions: list[Execution]) -> list[Execution]:
        per_brand: dict[str, list[Execution]] = {}
        for ex in sorted(executions, key=lambda x: (x.target_at, x.brand, x.service)):
            per_brand.setdefault(ex.brand, []).append(ex)
        ordered: list[Execution] = []
        while any(per_brand.values()):
            heads = [(items[0].target_at, brand) for brand, items in per_brand.items() if items]
            for _, brand in sorted(heads):
                if per_brand[brand]:
                    ordered.append(per_brand[brand].pop(0))
        return ordered

    def _post_input(self, ex: Execution, due_at: datetime) -> dict[str, Any]:
        input_data: dict[str, Any] = {
            "channelId": ex.channel_id,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": iso_seconds(due_at),
            "text": ex.text,
            "source": f"socialscheduler:{ex.campaign_id}:{ex.service}",
        }
        if ex.media_url and self._url_works(ex.media_url):
            input_data["assets"] = [{"image": {"url": ex.media_url}}]
        else:
            input_data["assets"] = []
        if ex.idea_id:
            input_data["ideaId"] = ex.idea_id
        if ex.service == "instagram":
            input_data["metadata"] = {"instagram": {"type": ex.format, "shouldShareToFeed": ex.format == "reel"}}
        elif ex.service == "facebook":
            input_data["metadata"] = {"facebook": {"type": ex.format}}
        return input_data

    def reconcile_and_fill(self, executions: list[Execution], posts: list[dict[str, Any]]) -> None:
        now = self.now()
        consumed = {self._post_key(p) for p in posts if p.get("status") in CONSUMED_STATUSES}
        consumed_ideas = {(p.get("channelId"), p.get("ideaId")) for p in posts if p.get("status") in CONSUMED_STATUSES and p.get("ideaId")}
        active = [p for p in posts if p.get("status") in ACTIVE_QUEUE_STATUSES]
        slots = max(0, int(self.settings["queue_limit"]) - len(active))
        if slots == 0:
            self.actions.append({"type": "queue_full", "active": len(active), "limit": self.settings["queue_limit"]})
            return

        candidates: list[Execution] = []
        for ex in executions:
            if ex.hold:
                self.actions.append({"type": "hold", "campaign": ex.campaign_id, "service": ex.service})
                continue
            if ex.requires_verification:
                self.actions.append({"type": "blocked", "campaign": ex.campaign_id, "service": ex.service, "reason": "fresh_verification_required"})
                continue
            if self._execution_key(ex) in consumed:
                continue
            if ex.idea_id and (ex.channel_id, ex.idea_id) in consumed_ideas:
                continue
            target = self._future_target(ex, now)
            if not target:
                self.actions.append({"type": "skip_late", "campaign": ex.campaign_id, "service": ex.service})
                continue
            if ex.service in MEDIA_REQUIRED:
                if not ex.media_url or not self._url_works(ex.media_url):
                    self.actions.append({"type": "blocked", "campaign": ex.campaign_id, "service": ex.service, "reason": "media_unavailable"})
                    continue
            candidates.append(ex)

        creates = 0
        for ex in self._fair_order(candidates):
            if creates >= slots or creates >= int(self.settings.get("max_creates_per_run", 10)):
                break
            due_at = self._future_target(ex, now)
            if due_at is None:
                continue
            input_data = self._post_input(ex, due_at)
            if input_data["mode"] != "customScheduled":
                raise RuntimeError("Safety invariant violated: only customScheduled is allowed")
            if due_at <= now:
                raise RuntimeError("Safety invariant violated: dueAt must be in the future")
            if self.mode == "live":
                created = self.client.create_post(input_data)
                self.actions.append({"type": "scheduled", "campaign": ex.campaign_id, "service": ex.service, "dueAt": created.get("dueAt"), "postId": created.get("id")})
            else:
                self.actions.append({"type": "would_schedule", "campaign": ex.campaign_id, "service": ex.service, "dueAt": iso_seconds(due_at)})
            creates += 1

    def run(self) -> dict[str, Any]:
        org_id = self.settings["organization_id"]
        account = self.client.account()
        org_ids = {org["id"] for org in account.get("organizations", [])}
        if org_id not in org_ids:
            raise BufferAPIError(f"Configured organization {org_id} is not accessible")

        live_channels = {c["id"]: c for c in self.client.channels(org_id)}
        missing = [meta["id"] for meta in self.channels.values() if meta["id"] not in live_channels]
        if missing:
            raise BufferAPIError(f"Configured Buffer channels are missing/disconnected: {missing}")

        posts = self.client.posts(org_id, STATUS_READ_SET)
        ideas = self.client.ideas(org_id)
        executions = self.expand()
        self.ensure_ideas(executions, ideas)
        self.reconcile_and_fill(executions, posts)

        summary = {
            "mode": self.mode,
            "organization": org_id,
            "timezone": self.settings["timezone"],
            "posts_seen": len(posts),
            "ideas_seen": len(ideas),
            "active_queue": sum(1 for p in posts if p.get("status") in ACTIVE_QUEUE_STATUSES),
            "queue_limit": self.settings["queue_limit"],
            "actions": self.actions,
        }
        return summary
