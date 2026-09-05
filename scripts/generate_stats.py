#!/usr/bin/env python3
"""
Gera dois cartões SVG (estatísticas + linguagens mais usadas) a partir de
dados 100% públicos do GitHub, sem precisar de token pessoal.
Pensado para rodar em GitHub Actions e ser commitado no próprio repositório,
eliminando a dependência da instância pública do github-readme-stats.
"""
import os
import re
import sys
import html
import urllib.request
import json

USERNAME = os.environ.get("GH_USERNAME", "erickystn")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Paleta roxa usada no README
BG = "#0d0221"
TITLE = "#c77dff"
ICON = "#9d4edd"
TEXT = "#e0aaff"
BORDER = "#3c096c"

LANG_COLORS = {
    "Java": "#ED8B00", "JavaScript": "#F7DF1E", "TypeScript": "#3178C6",
    "Python": "#3776AB", "PHP": "#777BB4", "HTML": "#E34F26", "CSS": "#1572B6",
    "Kotlin": "#7F52FF", "Dockerfile": "#2496ED", "Shell": "#89e051",
    "C#": "#178600", "C++": "#f34b7d", "Vue": "#41b883", "Ruby": "#701516",
}
DEFAULT_LANG_COLOR = "#c77dff"


def api_get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": USERNAME,
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def get_all_repos(username):
    repos, page = [], 1
    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=owner"
        batch = api_get(url)
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def get_total_contributions(username):
    """Raspa a página pública do calendário de contribuições (mesma técnica
    usada pelo github-readme-streak-stats) — funciona sem token e já inclui
    contribuições privadas anonimizadas."""
    req = urllib.request.Request(
        f"https://github.com/users/{username}/contributions",
        headers={"User-Agent": username},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode()
    m = re.search(r'([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year', body)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def get_language_totals(repos):
    totals = {}
    for r in repos:
        if r.get("fork"):
            continue
        try:
            langs = api_get(r["languages_url"])
        except Exception:
            continue
        for lang, byte_count in langs.items():
            totals[lang] = totals.get(lang, 0) + byte_count
    return totals


def esc(text):
    return html.escape(str(text))


def _icon_star(cx, cy):
    return f'<path transform="translate({cx-7},{cy-7})" d="M7 0 L9 5 L14 5 L10 8 L11.5 13 L7 10 L2.5 13 L4 8 L0 5 L5 5 Z" fill="{ICON}" />'


def _icon_repo(cx, cy):
    return f'<rect x="{cx-6}" y="{cy-6}" width="12" height="12" rx="2" fill="none" stroke="{ICON}" stroke-width="1.6" />'


def _icon_followers(cx, cy):
    return (f'<circle cx="{cx-3}" cy="{cy-3}" r="3.4" fill="none" stroke="{ICON}" stroke-width="1.4" />'
            f'<circle cx="{cx+4}" cy="{cy-2}" r="2.6" fill="none" stroke="{ICON}" stroke-width="1.4" />')


def _icon_chart(cx, cy):
    bars = [(-6, 3), (-1, 6), (4, 9)]
    els = "".join(
        f'<rect x="{cx+dx}" y="{cy+6-h}" width="3.5" height="{h}" fill="{ICON}" />'
        for dx, h in bars
    )
    return els


def render_stats_card(stats, out_path):
    rows = [
        (_icon_star, "Total Stars", stats["stars"]),
        (_icon_repo, "Repositórios Públicos", stats["public_repos"]),
        (_icon_followers, "Seguidores", stats["followers"]),
        (_icon_chart, "Contribuições (12 meses)", stats["contributions"]),
    ]
    row_h = 34
    height = 70 + row_h * len(rows)
    width = 420

    body = []
    for i, (icon_fn, label, value) in enumerate(rows):
        y = 70 + i * row_h
        body.append(f'''
    {icon_fn(35, y - 5)}
    <text x="55" y="{y}" font-size="14" fill="{TEXT}" font-family="Segoe UI, Ubuntu, sans-serif">{esc(label)}:</text>
    <text x="{width - 30}" y="{y}" font-size="14" fill="{TEXT}" font-family="Segoe UI, Ubuntu, sans-serif" text-anchor="end" font-weight="700">{esc(value)}</text>''')

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" rx="12" width="{width - 1}" height="{height - 1}" fill="{BG}" stroke="{BORDER}" />
  <text x="30" y="38" font-size="19" font-weight="700" fill="{TITLE}" font-family="Segoe UI, Ubuntu, sans-serif">Estatísticas do GitHub</text>
  {"".join(body)}
</svg>'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg


def render_langs_card(lang_totals, out_path, top_n=6):
    total = sum(lang_totals.values()) or 1
    top = sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]

    width = 420
    bar_y = 66
    bar_h = 10
    row_h = 26
    height = bar_y + bar_h + 20 + row_h * len(top)

    # barra de progresso segmentada
    segments = []
    x_cursor = 30
    bar_w_total = width - 60
    for lang, byte_count in top:
        pct = byte_count / total
        seg_w = max(pct * bar_w_total, 2)
        color = LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)
        segments.append(f'<rect x="{x_cursor:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}" />')
        x_cursor += seg_w

    legend = []
    for i, (lang, byte_count) in enumerate(top):
        pct = 100 * byte_count / total
        color = LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)
        y = bar_y + bar_h + 30 + i * row_h
        legend.append(f'''
    <circle cx="36" cy="{y - 5}" r="6" fill="{color}" />
    <text x="50" y="{y}" font-size="13" fill="{TEXT}" font-family="Segoe UI, Ubuntu, sans-serif">{esc(lang)}</text>
    <text x="{width - 30}" y="{y}" font-size="13" fill="{TEXT}" font-family="Segoe UI, Ubuntu, sans-serif" text-anchor="end">{pct:.1f}%</text>''')

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" rx="12" width="{width - 1}" height="{height - 1}" fill="{BG}" stroke="{BORDER}" />
  <text x="30" y="38" font-size="19" font-weight="700" fill="{TITLE}" font-family="Segoe UI, Ubuntu, sans-serif">Linguagens mais utilizadas</text>
  <rect x="30" y="{bar_y}" width="{bar_w_total}" height="{bar_h}" rx="5" fill="#231942" />
  {"".join(segments)}
  {"".join(legend)}
</svg>'''
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)

    profile = api_get(f"https://api.github.com/users/{USERNAME}")
    repos = get_all_repos(USERNAME)
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    contributions = get_total_contributions(USERNAME)

    stats = {
        "stars": stars,
        "public_repos": profile.get("public_repos", len(repos)),
        "followers": profile.get("followers", 0),
        "contributions": contributions if contributions is not None else "N/D",
    }
    render_stats_card(stats, os.path.join(out_dir, "stats-card.svg"))

    lang_totals = get_language_totals(repos)
    render_langs_card(lang_totals, os.path.join(out_dir, "langs-card.svg"))

    print("OK:", stats)
    print("Linguagens:", sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)[:6])


if __name__ == "__main__":
    main()
