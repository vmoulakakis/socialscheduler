#!/usr/bin/env python3
"""Generate deterministic zero-cost social posters from the safe public asset snapshot."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import qrcode

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rpfadpdnnxequgvdcfoq.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "sb_publishable_NkMSCtURWbZcA8MCY1H5sA_W_G10WYD")
LIMIT = max(1, min(int(os.getenv("ASSET_LIMIT", "30")), 80))
OUT = Path(os.getenv("ASSET_DIR", "assets/generated"))
OUT.mkdir(parents=True, exist_ok=True)

BOLD_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
REG_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]


def font(size: int, bold: bool = False):
    for p in BOLD_CANDIDATES if bold else REG_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def fetch_rows():
    select = "content_item_id,brand_name,brand_slug,title,core_copy,cta,tracking_url,hashtags,created_at,opportunity_score,expected_media_url"
    url = f"{SUPABASE_URL}/rest/v1/socialscheduler_public_asset_feed?select={urllib.parse.quote(select, safe=',')}&order=opportunity_score.desc,created_at.desc&limit={LIMIT}"
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_ANON_KEY, "authorization": f"Bearer {SUPABASE_ANON_KEY}", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def palette(key: str):
    palettes = [
        ((9, 23, 39), (26, 61, 88), (108, 227, 245)),
        ((22, 20, 42), (49, 43, 91), (180, 163, 255)),
        ((15, 34, 31), (29, 73, 57), (94, 226, 169)),
        ((35, 24, 18), (80, 58, 32), (245, 199, 108)),
    ]
    return palettes[int(hashlib.sha256(key.encode()).hexdigest()[:4], 16) % len(palettes)]


def gradient(size, a, b):
    w, h = size
    im = Image.new("RGB", size, a)
    px = im.load()
    for y in range(h):
        t = y / max(1, h - 1)
        row = tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))
        for x in range(w):
            px[x, y] = row
    return im


def wrap(draw, text: str, fnt, max_width: int, max_lines: int):
    words = (text or "").replace("\n", " ").split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words:
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines


def hashtags(value):
    vals = value if isinstance(value, list) else value.replace(",", " ").split() if isinstance(value, str) else []
    out = []
    for x in vals:
        x = str(x).strip()
        if not x:
            continue
        if not x.startswith("#"):
            x = "#" + x.lstrip("#")
        if x not in out:
            out.append(x)
    return out[:5]


def make_poster(row):
    cid = str(row["content_item_id"])
    dest = OUT / f"{cid}.png"
    if dest.exists() and dest.stat().st_size > 20_000:
        return {"content_item_id": cid, "path": str(dest), "status": "exists", "url": row.get("expected_media_url")}

    a, b, accent = palette(cid + str(row.get("brand_slug") or ""))
    im = gradient((1080, 1080), a, b)
    d = ImageDraw.Draw(im)
    d.ellipse((780, -170, 1220, 270), fill=tuple(min(255, c + 12) for c in b))
    d.ellipse((-210, 760, 250, 1220), fill=tuple(max(0, c - 4) for c in b))

    brand_f, title_f, body_f, cta_f, small_f, tag_f = font(30, True), font(64, True), font(31), font(31, True), font(22), font(22, True)
    brand = str(row.get("brand_name") or "Aurevia AI").strip()[:60]
    title = str(row.get("title") or "").strip()
    body = str(row.get("core_copy") or "").strip()
    cta = str(row.get("cta") or "Δες περισσότερα").strip()[:90]
    tracking = str(row.get("tracking_url") or "").strip()
    tags = hashtags(row.get("hashtags"))

    badge_w = 70 + min(560, 28 * max(6, len(brand)))
    badge_fill = tuple(min(255, int(c * 0.75 + 28)) for c in b)
    d.rounded_rectangle((70, 62, badge_w, 116), radius=24, fill=badge_fill, outline=accent, width=2)
    d.text((92, 73), brand.upper(), font=brand_f, fill=(245, 249, 252))

    y = 175
    for line in wrap(d, title, title_f, 820, 3):
        d.text((70, y), line, font=title_f, fill=(255, 255, 255)); y += 78
    y += 16
    hook = body.split("\n")[0][:180]
    for line in wrap(d, hook, body_f, 660, 3):
        d.text((72, y), line, font=body_f, fill=(217, 231, 241)); y += 45

    y = min(620, max(y + 30, 540))
    d.rounded_rectangle((70, y, 560, y + 68), radius=28, fill=accent)
    d.text((98, y + 16), cta, font=cta_f, fill=(8, 18, 28))

    # Decoder-verified full-poster QR: exact tracking URL, integer modules, no resampling.
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=3)
    qr.add_data(tracking); qr.make(fit=True)
    qr_im = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_w, qr_h = qr_im.size
    qr_x, qr_y = 600, 610
    im.paste(qr_im, (qr_x, qr_y))
    d.text((70, 830), "SCAN → TRACKED LINK", font=small_f, fill=accent)
    d.text((70, 868), "QR = ακριβές tracking URL", font=small_f, fill=(201, 218, 231))
    if tags:
        d.text((70, 970), "  ".join(tags[:4]), font=tag_f, fill=(228, 239, 247))
    if row.get("opportunity_score") is not None:
        d.text((850, 62), f"OPP {float(row['opportunity_score']):.1f}", font=small_f, fill=(232, 244, 250))

    im.save(dest, "PNG", optimize=True)
    return {"content_item_id": cid, "path": str(dest), "status": "generated", "url": row.get("expected_media_url"), "tracking_url": tracking, "hashtags": tags, "qr_modules": qr.modules_count, "qr_pixel_size": [qr_w, qr_h]}


def main():
    rows = fetch_rows(); manifest = []
    for row in rows:
        try:
            manifest.append(make_poster(row))
        except Exception as exc:
            manifest.append({"content_item_id": str(row.get("content_item_id")), "status": "error", "error": str(exc)[:500]})
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": "socialscheduler_public_asset_feed", "count": len(manifest), "items": manifest}
    (OUT / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "generated": sum(1 for x in manifest if x.get("status") == "generated"), "errors": sum(1 for x in manifest if x.get("status") == "error")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
