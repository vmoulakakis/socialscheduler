#!/usr/bin/env python3
"""Render platform-specific affiliate posters with exact, scannable QR links."""
from __future__ import annotations

import argparse
import io
import json
import textwrap
import urllib.request
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


SIZES = {
    "facebook": (1200, 1500),
    "instagram": (1080, 1350),
    "tiktok": (1080, 1920),
    "linkedin": (1200, 1500),
}

HOOKS = {
    "facebook": "Φεύγεις διακοπές;\nΤα φυτά σου όχι.",
    "instagram": "Πότισμα χωρίς\nκαθημερινό άγχος",
    "tiktok": "POV: οργανώνεις το\nπότισμα πριν φύγεις",
    "linkedin": "Μικρή αυτοματοποίηση.\nΛιγότερο καθημερινό άγχος.",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


def _download_image(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "SocialScheduler/2.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        if not (response.headers.get("Content-Type") or "").lower().startswith("image/"):
            raise ValueError("product image URL did not return an image")
        return Image.open(io.BytesIO(response.read(8_000_000))).convert("RGB")


def _fit_product(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    canvas = Image.new("RGB", size, "white")
    fitted = ImageOps.contain(source, (int(w * 0.84), int(h * 0.54)), Image.Resampling.LANCZOS)
    x = (w - fitted.width) // 2
    y = int(h * 0.24) + max(0, (int(h * 0.50) - fitted.height) // 2)
    canvas.paste(fitted, (x, y))
    return canvas


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        current = ""
        for word in paragraph.split():
            trial = f"{current} {word}".strip()
            if draw.textbbox((0, 0), trial, font=font)[2] <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines[:max_lines]


def platform_caption(platform: str, product: str, merchant: str, short_url: str) -> str:
    disclosure = "Διαφήμιση / affiliate link: μπορεί να λάβω προμήθεια χωρίς επιπλέον κόστος για εσένα."
    captions = {
        "facebook": (
            "Φεύγεις και σκέφτεσαι ποιος θα ποτίζει; 🌿 Η ζαρντινιέρα με αυτόματο πότισμα είναι μια πρακτική επιλογή "
            f"για να οργανώσεις καλύτερα το μπαλκόνι σου. Δες διαστάσεις, διαθεσιμότητα και όρους στο {merchant}.\n\n"
            f"Αγορά / λεπτομέρειες: {short_url}\n{disclosure}\n\n#ΑυτόματοΠότισμα #Μπαλκόνι #Κήπος #ΈξυπνοΣπίτι"
        ),
        "instagram": (
            "Πριν φύγεις, οργάνωσε το πότισμα. 🌱\n"
            f"{product}\n\nΣκάναρε το QR στην εικόνα για διαθεσιμότητα και λεπτομέρειες.\n"
            f"{disclosure}\n\n#ΑυτόματοΠότισμα #Μπαλκόνι #PlantCare #GardenIdeas #HomeHack #Greece"
        ),
        "tiktok": (
            "POV: οργανώνεις το πότισμα πριν τις διακοπές 🌿💧\n"
            "Scan → έλεγχος διαστάσεων → απόφαση.\n"
            f"{short_url}\n{disclosure}\n\n#PlantTok #ΑυτόματοΠότισμα #Μπαλκόνι #HomeHack"
        ),
        "linkedin": (
            "Μια μικρή αυτοματοποίηση μπορεί να αφαιρέσει μία επαναλαμβανόμενη δουλειά από την καθημερινότητα. "
            f"Η συγκεκριμένη λύση αυτόματου ποτίσματος από {merchant} αξίζει έλεγχο για διαστάσεις, χώρο και πραγματική ανάγκη — όχι παρορμητική αγορά.\n\n"
            f"Λεπτομέρειες: {short_url}\n{disclosure}\n\n#SmartHome #Productivity #AffiliateMarketing"
        ),
    }
    return captions[platform]


def render(platform: str, source: Image.Image, product: str, merchant: str, short_url: str, dest: Path) -> None:
    w, h = SIZES[platform]
    image = _fit_product(source, (w, h))
    image = ImageEnhance.Contrast(image).enhance(1.03)
    draw = ImageDraw.Draw(image, "RGBA")

    header_h = int(h * 0.25)
    footer_y = int(h * 0.73)
    draw.rectangle((0, 0, w, header_h), fill=(8, 30, 27, 246))
    draw.rectangle((0, footer_y, w, h), fill=(8, 30, 27, 248))
    draw.rounded_rectangle((56, 42, 420, 96), radius=24, fill=(174, 239, 117, 255))
    draw.text((84, 55), "SMART AFFILIATE PICK", font=_font(22, True), fill=(8, 30, 27, 255))

    title_font = _font(56 if platform != "tiktok" else 62, True)
    y = 120
    for line in _wrap(draw, HOOKS[platform], title_font, w - 112, 3):
        draw.text((56, y), line, font=title_font, fill="white")
        y += int(title_font.size * 1.14)

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(short_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_target = 300 if platform != "tiktok" else 340
    qr_img = qr_img.resize((qr_target, qr_target), Image.Resampling.NEAREST)
    qr_x, qr_y = w - qr_target - 60, footer_y + 66
    image.paste(qr_img, (qr_x, qr_y))

    draw = ImageDraw.Draw(image, "RGBA")
    body_font, small_font, cta_font = _font(30), _font(22), _font(34, True)
    body_width = w - qr_target - 160
    body_y = footer_y + 70
    for line in _wrap(draw, product, body_font, body_width, 4):
        draw.text((58, body_y), line, font=body_font, fill=(236, 247, 242, 255))
        body_y += 42
    draw.text((58, body_y + 18), merchant, font=small_font, fill=(174, 239, 117, 255))
    draw.text((58, h - 135), "ΣΚΑΝΑΡΕ & ΔΕΣ ΤΟ ΠΡΟΪΟΝ", font=cta_font, fill="white")
    draw.text((58, h - 82), "Διαφήμιση • affiliate link • έλεγξε τιμή & διαθεσιμότητα", font=small_font, fill=(193, 211, 204, 255))

    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True, help="JSON campaign input")
    parser.add_argument("--out", default="assets/affiliate")
    args = parser.parse_args()

    campaign = json.loads(Path(args.campaign).read_text(encoding="utf-8"))
    source = _download_image(campaign["image_url"])
    out = Path(args.out) / campaign["campaign_key"]
    manifest = {"campaign": campaign["campaign_key"], "items": []}
    for platform in SIZES:
        short_url = f'{campaign["short_base"]}/{campaign["seed_key"]}?p={platform}&c={campaign["campaign_key"]}'
        dest = out / f"{platform}.png"
        render(platform, source, campaign["product_name"], campaign["merchant_name"], short_url, dest)
        manifest["items"].append({
            "platform": platform,
            "path": str(dest),
            "short_url": short_url,
            "caption": platform_caption(platform, campaign["product_name"], campaign["merchant_name"], short_url),
            "size": list(SIZES[platform]),
        })
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"campaign": campaign["campaign_key"], "rendered": len(manifest["items"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
