from pathlib import Path
import re
import base64
import hashlib
import requests
from bs4 import BeautifulSoup

# Tier badge images (tier1.svg - tier6.svg) are sourced from DACON.io platform

PROFILE_URL = "https://dacon.io/myprofile/529712/competition"
OUT = Path("badges/dacon.svg")
HEADERS = {"User-Agent": "Mozilla/5.0"}

DEFAULT_TEXT_COLOR = "#6b4b3a"

def get_tier_color(tier_num: int | None) -> str:
    """
    Get text color based on tier number to match badge colours.
    tier1 = Beginner, tier2 = Bronze, tier3 = Silver,
    tier4 = Gold, tier5 = Challenger, tier6 = Champion
    """
    if tier_num is None:
        return DEFAULT_TEXT_COLOR
    
    tier_colors = {
        1: "#B0B0B0",  # Beginner - medium gray (darker than line for readability)
        2: "#966B40",  # Bronze - brown/bronze (midpoint of #B7775C and #753C24)
        3: "#747474",  # Silver - gray (midpoint of #A5A5A5 and #444444)
        4: "#B8942F",  # Gold - gold (midpoint of #F1C24A and #362805)
        5: "#7657C5",  # Challenger - purple (midpoint of #967BFF and #5634DD)
        6: "#7F7F7F",  # Champion - gray (midpoint of #C3C3C3 and #5F5F5F)
    }
    return tier_colors.get(tier_num, DEFAULT_TEXT_COLOR)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def pick_text(soup: BeautifulSoup, css: str) -> str | None:
    el = soup.select_one(css)
    if not el:
        return None
    return clean(el.get_text(" ", strip=True))


def escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def parse_int(num_str: str) -> int | None:
    try:
        return int(num_str.replace(",", ""))
    except Exception:
        return None


def strip_count_suffix(v: str) -> str:
    return re.sub(r"\s*회\s*$", "", (v or "").strip())


def extract_total_count(soup: BeautifulSoup) -> str | None:
    el = (
        soup.select_one("#web-child .now_rank p.default_color")
        or soup.select_one("#mobile-child .now_rank p.default_color")
    )
    if not el:
        return None
    m = re.search(r"of\s*([\d,]+)", el.get_text(" ", strip=True), flags=re.IGNORECASE)
    return m.group(1) if m else None


def extract_logo_url_with_fallbacks(soup: BeautifulSoup) -> str | None:
    img = (
        soup.select_one('img[alt="DACON"]')
        or soup.select_one('img[src*="logo"]')
        or soup.select_one('img[src*="main-logo"]')
    )
    if not img:
        return None
    src = img.get("src")
    if not src:
        return None
    return "https://dacon.io" + src if src.startswith("/") else src


def fetch_svg_as_data_uri(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        b64 = base64.b64encode(r.content).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"
    except Exception:
        return None


def extract_tier_number(soup: BeautifulSoup) -> int | None:
    el = (
        soup.select_one("#web-child .rank_tier span.user_color")
        or soup.select_one("#mobile-child .rank_tier span.user_color")
    )
    if not el:
        return None
    for c in el.get("class", []):
        m = re.fullmatch(r"tier(\d+)_color", c)
        if m:
            return int(m.group(1))
    return None


def tier_text_to_number(tier_text: str) -> int | None:
    """
    Map competition level text to tier number.
    tier1 = Beginner, tier2 = Bronze, tier3 = Silver,
    tier4 = Gold, tier5 = Challenger, tier6 = Champion
    """
    tier_text_lower = tier_text.lower()
    if "beginner" in tier_text_lower:
        return 1
    elif "bronze" in tier_text_lower:
        return 2
    elif "silver" in tier_text_lower:
        return 3
    elif "gold" in tier_text_lower:
        return 4
    elif "challenger" in tier_text_lower:
        return 5
    elif "champion" in tier_text_lower:
        return 6
    return None


def normalise_percent_label(label: str) -> str:
    m = re.fullmatch(r"(\d+)%", label)
    if m:
        return f"Top {m.group(1)}%"
    return label


def extract_overview_tables(soup: BeautifulSoup):
    rows1 = soup.select("#web-child .content_box table:nth-of-type(1) tr")
    if not rows1:
        rows1 = soup.select("#mobile-child .content_box table:nth-of-type(1) tr")

    awards = {}
    for tr in rows1:
        tds = tr.select("td")
        if len(tds) == 2:
            raw_key = clean(tds[0].get_text(" ", strip=True))
            key = normalise_percent_label(raw_key)
            value = clean(tds[1].get_text(" ", strip=True))
            awards[key] = value

    rows2 = soup.select("#web-child .content_box table:nth-of-type(2) tr")
    if not rows2:
        rows2 = soup.select("#mobile-child .content_box table:nth-of-type(2) tr")

    participation = {}
    for tr in rows2:
        tds = tr.select("td")
        if len(tds) == 2:
            key = clean(tds[0].get_text(" ", strip=True))
            value = clean(tds[1].get_text(" ", strip=True))
            participation[key] = value

    return awards, participation


# Tier badge images (tier1.svg - tier6.svg) are sourced from DACON.io platform
def find_tier_svg_path(tier_num: int) -> Path | None:
    tier_path = Path("assets/dacon-tier") / f"tier{tier_num}.svg"
    if tier_path.exists():
        return tier_path
    candidates = sorted(Path("assets/dacon-tier").glob(f"tier{tier_num}*.svg"))
    return candidates[0] if candidates else None


def inline_svg_file(svg_path: Path, x: int, y: int, w: int, h: int) -> tuple[str, str]:
    raw = svg_path.read_text(encoding="utf-8", errors="ignore")

    # extract viewBox and inner content
    vb = None
    vb_m = re.search(r'viewBox\s*=\s*"([^"]+)"', raw, flags=re.IGNORECASE)
    if vb_m:
        vb = vb_m.group(1).strip()

    inner_m = re.search(r"<svg[^>]*>(.*)</svg>", raw, flags=re.DOTALL | re.IGNORECASE)
    inner = inner_m.group(1).strip() if inner_m else raw.strip()

    # Extract defs separately and make IDs unique
    # Generate unique suffix for this SVG file to avoid ID collisions
    unique_suffix = hashlib.md5(str(svg_path).encode()).hexdigest()[:8]
    
    defs_match = re.search(r"(<defs.*?</defs>)", raw, flags=re.DOTALL | re.IGNORECASE)
    defs_content = ""
    if defs_match:
        defs_raw = defs_match.group(1)
        # Replace all ID references in defs
        defs_content = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{m.group(1)}_{unique_suffix}"', defs_raw)
        defs_content = re.sub(r'url\(#([^)]+)\)', lambda m: f'url(#{m.group(1)}_{unique_suffix})', defs_content)
    
    # Remove defs from inner and update all references (url(#...), clip-path, filter, etc.)
    inner_no_defs = re.sub(r"<defs.*?</defs>", "", inner, flags=re.DOTALL | re.IGNORECASE).strip()
    if defs_content:
        # Update all url(#...) references in attributes (fill, stroke, clip-path, filter, etc.)
        inner_no_defs = re.sub(r'url\(#([^)]+)\)', lambda m: f'url(#{m.group(1)}_{unique_suffix})', inner_no_defs)

    if vb:
        vb_parts = vb.split()
        if len(vb_parts) >= 4:
            vb_w = float(vb_parts[2])
            vb_h = float(vb_parts[3])
            scale = min(w / vb_w, h / vb_h)
            actual_w = vb_w * scale
            actual_h = vb_h * scale
            offset_x = x + (w - actual_w) / 2
            offset_y = y + (h - actual_h) / 2
            
            svg_content = (
                f'<svg x="{offset_x}" y="{offset_y}" width="{actual_w}" height="{actual_h}" '
                f'viewBox="{escape_xml(vb)}" xmlns="http://www.w3.org/2000/svg" '
                f'preserveAspectRatio="xMidYMid meet">'
                f'{inner_no_defs}</svg>'
            )
            return (defs_content, svg_content)

    # fallback: group transform scale into the box (assume original ~52x52)
    scale_x = w / 52.0
    scale_y = h / 52.0
    svg_content = f'<g transform="translate({x},{y}) scale({scale_x},{scale_y})">{inner_no_defs}</g>'
    return (defs_content, svg_content)


def main():
    r = requests.get(PROFILE_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    tier_text = (
        pick_text(soup, "#web-child .rank_tier span.user_color")
        or pick_text(soup, "#mobile-child .rank_tier span.user_color")
        or "Competition"
    )
    current_rank = (
        pick_text(soup, "#web-child .now_rank p.user_color")
        or pick_text(soup, "#mobile-child .now_rank p.user_color")
        or "N/A"
    )
    total_count = extract_total_count(soup) or "N/A"
    best_rank = (
        pick_text(soup, "#web-child .best_rank p.user_color")
        or pick_text(soup, "#mobile-child .best_rank p.user_color")
        or "N/A"
    )

    tier_num = extract_tier_number(soup)
    # Fallback: try to get tier number from tier text if CSS extraction didn't work
    if tier_num is None:
        tier_num = tier_text_to_number(tier_text)

    cur_i = parse_int(current_rank)
    tot_i = parse_int(total_count)
    top_pct_text = "N/A"
    if cur_i and tot_i and tot_i > 0:
        top_pct_text = f"{(cur_i / tot_i) * 100:.2f}%"

    awards, participation = extract_overview_tables(soup)
    awards_line = (
        f"Awards: {strip_count_suffix(awards.get('수상','0회'))}  |  "
        f"Top 1%: {strip_count_suffix(awards.get('Top 1%','0회'))}  |  "
        f"Top 4%: {strip_count_suffix(awards.get('Top 4%','0회'))}  |  "
        f"Top 10%: {strip_count_suffix(awards.get('Top 10%','0회'))}"
    )
    part_line = (
        f"Solo: {strip_count_suffix(participation.get('개인','0회'))}  |  "
        f"Team: {strip_count_suffix(participation.get('단체','0회'))}  |  "
        f"Total: {strip_count_suffix(participation.get('전체','0회'))}"
    )

    logo_url = extract_logo_url_with_fallbacks(soup)
    logo_data_uri = fetch_svg_as_data_uri(logo_url) if logo_url else None

    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Layout - horizontal metrics centered vertically, logo top-left, prominent tier badge
    W, H = 850, 250
    PAD_X = 40
    PAD_Y = 30
    
    # Logo - adjusted for narrower width
    LOGO_X = PAD_X  # Moved left to fit narrower width
    LOGO_Y = PAD_Y
    LOGO_WIDTH = 170  # Logo width
    LOGO_HEIGHT = 48
    
    tier_text_approx_width = len(tier_text) * 10.8
    TIER_TEXT_BASE_X = PAD_X + 28.82
    TIER_TEXT_X = TIER_TEXT_BASE_X
    TIER_TEXT_CENTER_X = TIER_TEXT_X + (tier_text_approx_width / 2)
    TIER_TEXT_Y = 200
    TIER_TEXT_FONT_SIZE = 18
    TIER_TEXT_BOTTOM = TIER_TEXT_Y + (TIER_TEXT_FONT_SIZE * 0.2)
    
    TIER_ICON_SIZE = 100
    TIER_ICON_X = TIER_TEXT_CENTER_X - (TIER_ICON_SIZE / 2) - 15
    TIER_ICON_Y = TIER_TEXT_Y - TIER_ICON_SIZE - 15
    
    METRICS_CENTER_Y = H / 2
    X_CUR, X_TOP, X_BEST = 390, 560, 730
    Y_LABEL = METRICS_CENTER_Y - 50
    Y_VALUE = METRICS_CENTER_Y - 10
    Y_SUB = METRICS_CENTER_Y + 15
    
    AWARDS_X = (X_CUR + X_BEST) / 2
    SOLO_FONT_SIZE = 11
    SOLO_Y = TIER_TEXT_BOTTOM - (SOLO_FONT_SIZE * 0.2)
    AWARDS_Y = SOLO_Y - 18

    logo_part = (
        f'<image href="{logo_data_uri}" x="{LOGO_X}" y="{LOGO_Y}" width="{LOGO_WIDTH}" height="48" />'
        if logo_data_uri
        else f'<text x="{LOGO_X}" y="{LOGO_Y + 33}" font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial" font-size="30" font-weight="900" fill="#222">DACON</text>'
    )

    tier_icon_part = ""
    tier_icon_defs = ""
    tier_svg_path = find_tier_svg_path(tier_num) if tier_num else None
    if tier_svg_path and tier_svg_path.exists():
        tier_icon_defs, tier_icon_part = inline_svg_file(
            tier_svg_path, TIER_ICON_X, TIER_ICON_Y, w=TIER_ICON_SIZE, h=TIER_ICON_SIZE
        )

    # Get tier-specific color for text
    tier_color = get_tier_color(tier_num)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Dacon badge">
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000" flood-opacity="0.12"/>
    </filter>
    {tier_icon_defs}
  </defs>

  <rect x="16" y="16" width="{W-32}" height="{H-32}" rx="18" fill="#fff" filter="url(#shadow)"/>
  
  <!-- Logo top-left -->
  {logo_part}

  <!-- Metrics horizontal, vertically centered -->
  <text x="{X_CUR}" y="{Y_LABEL}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="11" font-weight="800" fill="{tier_color}" letter-spacing="0.5">
    Current rank
  </text>
  <text x="{X_CUR}" y="{Y_VALUE}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="38" font-weight="900" fill="{tier_color}">
    {escape_xml(current_rank)}
  </text>
  <text x="{X_CUR}" y="{Y_SUB}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="11" font-weight="600" fill="#666">
    of {escape_xml(total_count)}
  </text>

  <text x="{X_TOP}" y="{Y_LABEL}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="11" font-weight="800" fill="#666" letter-spacing="0.5">
    Top percentile
  </text>
  <text x="{X_TOP}" y="{Y_VALUE}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="38" font-weight="900" fill="#222">
    {escape_xml(top_pct_text)}
  </text>

  <text x="{X_BEST}" y="{Y_LABEL}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="11" font-weight="800" fill="{tier_color}" letter-spacing="0.5">
    Best rank
  </text>
  <text x="{X_BEST}" y="{Y_VALUE}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="38" font-weight="900" fill="{tier_color}">
    {escape_xml(best_rank)}
  </text>

  <!-- Tier badge - prominent, above Competition Bronze text, centered on text -->
  {tier_icon_part}

  <!-- Competition Rank text below logo -->
  <text x="{TIER_TEXT_X}" y="{TIER_TEXT_Y}"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="18" font-weight="900" fill="{tier_color}" letter-spacing="0.3">
    {escape_xml(tier_text)}
  </text>

  <!-- Awards and solo below Current rank -->
  <text x="{AWARDS_X}" y="{AWARDS_Y}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="11" font-weight="600" fill="#666" letter-spacing="0.2">
    {escape_xml(awards_line)}
  </text>

  <text x="{AWARDS_X}" y="{AWARDS_Y + 18}" text-anchor="middle"
        font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial"
        font-size="11" font-weight="600" fill="#666" letter-spacing="0.2">
    {escape_xml(part_line)}
  </text>
</svg>'''

    OUT.write_text(svg, encoding="utf-8")

    print("OK:", tier_text, current_rank, f"of {total_count}", f"Top {top_pct_text}", best_rank)
    print("tier_num:", tier_num)
    print("tier_svg:", str(tier_svg_path) if tier_svg_path else "(none)")
    print("Awards:", {k: strip_count_suffix(v) for k, v in awards.items()})
    print("Participation:", {k: strip_count_suffix(v) for k, v in participation.items()})
    print("Wrote:", OUT.resolve())
    
    return OUT


if __name__ == "__main__":
    main()
