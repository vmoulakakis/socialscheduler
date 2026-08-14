from __future__ import annotations

import argparse
import json
import re
import textwrap
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import urlparse


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:48] or "campaign"


def page_title(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": "socialscheduler/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type:
                return None
            data = response.read(700_000).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None

    og = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', data, re.I)
    if og:
        return unescape(re.sub(r"\s+", " ", og.group(1))).strip()[:140]
    title = re.search(r"<title[^>]*>(.*?)</title>", data, re.I | re.S)
    if title:
        return unescape(re.sub(r"\s+", " ", title.group(1))).strip()[:140]
    return None


def wrap_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [text]


def create_card(path: Path, brand: str, angle: str, domain: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required for auto-card asset generation") from exc

    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), (246, 247, 249))
    draw = ImageDraw.Draw(image)

    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]

    def font(candidates: list[str], size: int):
        for candidate in candidates:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size=size)
        return ImageFont.load_default()

    f_brand = font(bold_candidates, 54)
    f_title = font(bold_candidates, 78)
    f_domain = font(regular_candidates, 34)
    f_cta = font(bold_candidates, 40)

    draw.rounded_rectangle((70, 70, width - 70, height - 70), radius=42, fill=(255, 255, 255), outline=(35, 38, 45), width=3)
    draw.text((120, 135), brand, font=f_brand, fill=(28, 31, 38))

    y = 310
    for line in wrap_lines(angle, 24)[:6]:
        draw.text((120, y), line, font=f_title, fill=(22, 24, 30))
        y += 98

    draw.text((120, height - 270), domain, font=f_domain, fill=(90, 96, 108))
    draw.rounded_rectangle((120, height - 190, width - 120, height - 105), radius=22, fill=(28, 31, 38))
    draw.text((160, height - 170), "Δες περισσότερα →", font=f_cta, fill=(255, 255, 255))

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def platform_copy(brand: str, angle: str, title: str | None, url: str) -> dict[str, str]:
    subject = title if title and title.casefold() != brand.casefold() else brand
    return {
        "instagram": f"{angle} ✨\n\n{subject}\n\nΔες περισσότερα: {url}",
        "facebook": f"{angle}. Αν θέλεις να δεις τις λεπτομέρειες για {subject}, άνοιξε το link και έλεγξε τι ταιριάζει στη δική σου περίπτωση:\n{url}",
        "tiktok": f"{angle} 👀\n{subject}\n{url}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/update one unique backlog campaign from a normalized tracking request")
    parser.add_argument("--request", required=True)
    parser.add_argument("--backlog", default="config/backlog.json")
    parser.add_argument("--assets", default="assets")
    args = parser.parse_args()

    request_path = Path(args.request)
    request = load_json(request_path, None)
    if not request:
        raise ValueError("Tracking request not found")

    issue_number = int(request["issue_number"])
    brand = request["brand"]
    angle = request["angle"]
    url = request["tracking_url"]
    platforms = request["platforms"]
    campaign_id = f"tracking-{issue_number}-{slugify(brand)}-{slugify(angle)[:24]}"
    title = page_title(url)
    domain = urlparse(url).netloc
    copies = platform_copy(brand, angle, title, url)

    asset_mode = request["asset_mode"]
    asset_filename: str | None = None
    hold_services: dict[str, bool] = {}
    if asset_mode == "auto-card":
        asset_filename = f"{campaign_id}.png"
        create_card(Path(args.assets) / asset_filename, brand, angle, domain)
    elif asset_mode == "existing-file":
        asset_filename = request.get("asset_reference")
        if not asset_filename or not (Path(args.assets) / asset_filename).exists():
            raise ValueError(f"Existing asset not found: {asset_filename}")
    else:
        hold_services = {service: True for service in platforms}

    entry = {
        "id": campaign_id,
        "brand": brand,
        "topic": angle.upper()[:90],
        "idea_title": f"TRACKING | {brand} | #{issue_number} | {angle}"[:180],
        "target_at": request["target_at"],
        "services": platforms,
        "asset_filename": asset_filename,
        "alt_text": f"{brand} social creative: {angle}",
        "format": {service: "post" for service in platforms},
        "platform_text": {service: copies[service] for service in platforms},
        "tracking_source_id": request["tracking_source_id"],
        "tracking_url": url,
        "tracking_mode": "opaque",
        "intake_request_id": request["request_id"],
        "intake_issue": request["issue_url"],
        "asset_origin": asset_mode,
        "requires_verification": request.get("claim_sensitivity") == "current-claim-sensitive",
    }
    if hold_services:
        entry["hold_services"] = hold_services

    backlog_path = Path(args.backlog)
    backlog = load_json(backlog_path, [])
    replaced = False
    for index, current in enumerate(backlog):
        if current.get("id") == campaign_id:
            backlog[index] = entry
            replaced = True
            break
    if not replaced:
        backlog.append(entry)
    backlog.sort(key=lambda item: (item.get("target_at", "9999"), item.get("brand", ""), item.get("id", "")))
    dump_json(backlog_path, backlog)

    request["status"] = "campaign_ready" if not hold_services else "waiting_for_asset"
    request["campaign_id"] = campaign_id
    request["asset_filename"] = asset_filename
    dump_json(request_path, request)

    print(json.dumps({
        "campaign_id": campaign_id,
        "asset_filename": asset_filename,
        "status": request["status"],
        "tracking_url_preserved": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
