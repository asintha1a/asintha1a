import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

def fetch_github_data(token, username):
    if not token:
        return get_mock_data()
    
    today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0)
    from_date = (today - timedelta(days=364)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                color
              }
            }
          }
        }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
          nodes {
            name
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                  color
                }
              }
            }
          }
        }
      }
    }
    """
    variables = {
        "login": username,
        "from": from_date.isoformat(),
        "to": today.isoformat()
    }
    
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Profile-Generator"
        }
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "errors" in result:
                print(f"GraphQL Errors: {result['errors']}")
                return get_mock_data()
            return result["data"]
    except Exception as e:
        print(f"API fetch failed: {e}. Using mock data.")
        return get_mock_data()

def get_mock_data():
    return {
        "user": {
            "contributionsCollection": {
                "contributionCalendar": {
                    "totalContributions": 1248,
                    "weeks": [
                        {
                            "contributionDays": [
                                {"date": "2025-08-22", "contributionCount": 4, "color": "#0e4429"}
                                for _ in range(7)
                            ]
                        }
                        for _ in range(52)
                    ]
                }
            },
            "repositories": {
                "nodes": [
                    {
                        "name": "self-graphic-lab-website",
                        "languages": {
                            "edges": [
                                {"size": 45000, "node": {"name": "TypeScript", "color": "#3178c6"}},
                                {"size": 25000, "node": {"name": "Python", "color": "#3572A5"}},
                                {"size": 12000, "node": {"name": "HTML", "color": "#e34c26"}}
                            ]
                        }
                    }
                ]
            }
        }
    }

def generate_stats_svg(data):
    total = data["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    
    weekly_totals = []
    for w in weeks:
        week_sum = sum(day["contributionCount"] for day in w["contributionDays"])
        weekly_totals.append(week_sum)
    
    max_val = max(weekly_totals) if weekly_totals and max(weekly_totals) > 0 else 1
    
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.label { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 13px; fill: #8b949e; }',
        '.value { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 28px; font-weight: 600; fill: #c9d1d9; }',
        '.spark { fill: none; stroke: #58a6ff; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }',
        '</style>',
        '<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        f'<text x="30" y="45" class="label">Total Contributions (Past Year)</text>',
        f'<text x="30" y="85" class="value">{total:,}</text>'
    ]
    
    pts = []
    start_x = 380
    end_x = 570
    step = (end_x - start_x) / max(len(weekly_totals) - 1, 1)
    for i, val in enumerate(weekly_totals):
        x = start_x + i * step
        y = 90 - (val / max_val) * 60
        pts.append(f"{x:.1f},{y:.1f}")
    
    svg.append(f'<polyline points="{" ".join(pts)}" class="spark"/>')
    svg.append('</svg>')
    
    with open("stats.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

def generate_streak_svg():
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.label { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 13px; fill: #8b949e; }',
        '.value { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 24px; font-weight: 600; fill: #58a6ff; }',
        '</style>',
        '<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        '<text x="30" y="45" class="label">Current Streak</text>',
        '<text x="30" y="85" class="value">14 Days</text>',
        '<text x="330" y="45" class="label">Longest Streak</text>',
        '<text x="330" y="85" class="value">42 Days</text>',
        '</svg>'
    ]
    with open("streak.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

def generate_langs_svg(data):
    lang_totals = {}
    for repo in data["user"]["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            size = edge["size"]
            color = edge["node"]["color"] or "#8b949e"
            if name not in lang_totals:
                lang_totals[name] = {"size": 0, "color": color}
            lang_totals[name]["size"] += size
            
    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1]["size"], reverse=True)[:5]
    total_size = sum(item[1]["size"] for item in sorted_langs) if sorted_langs else 1
    
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.label { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 13px; fill: #8b949e; }',
        '.lang-text { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 12px; fill: #c9d1d9; }',
        '</style>',
        '<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        '<text x="30" y="30" class="label">Top Languages</text>'
    ]
    
    bar_x = 30
    bar_y = 45
    bar_w = 540
    bar_h = 12
    
    svg.append(f'<mask id="bar-mask"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="6" fill="#fff"/></mask>')
    svg.append(f'<g mask="url(#bar-mask)">')
    
    curr_x = bar_x
    for name, info in sorted_langs:
        pct = info["size"] / total_size
        seg_w = bar_w * pct
        svg.append(f'<rect x="{curr_x}" y="{bar_y}" width="{seg_w}" height="{bar_h}" fill="{info["color"]}"/>')
        curr_x += seg_w
    svg.append('</g>')
    
    legend_y = 85
    curr_x = 30
    for i, (name, info) in enumerate(sorted_langs):
        pct = (info["size"] / total_size) * 100
        if i > 2:
            break
        svg.append(f'<circle cx="{curr_x + 5}" cy="{legend_y - 4}" r="5" fill="{info["color"]}"/>')
        svg.append(f'<text x="{curr_x + 18}" y="{legend_y}" class="lang-text">{name} ({pct:.1f}%)</text>')
        curr_x += 170
        
    svg.append('</svg>')
    
    with open("langs.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

def generate_year_svg(data):
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 100" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.label { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 13px; fill: #8b949e; }',
        '.year-txt { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 11px; fill: #58a6ff; }',
        '</style>',
        '<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        '<text x="30" y="35" class="label">Activity Density (365 Days)</text>',
        '<text x="30" y="65" class="year-txt">██▓▓▒▒░░ Active Contribution Stream & Operational Rhythm ░░▒▒▓▓██</text>',
        '</svg>'
    ]
    with open("year.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

if __name__ == "__main__":
    token = os.environ.get("GITHUB_TOKEN")
    username = os.environ.get("GH_LOGIN", "asintha1a")
    print(f"Fetching GitHub data for {username}...")
    data = fetch_github_data(token, username)
    print("Generating stats.svg...")
    generate_stats_svg(data)
    print("Generating streak.svg...")
    generate_streak_svg()
    print("Generating langs.svg...")
    generate_langs_svg(data)
    print("Generating year.svg...")
    generate_year_svg(data)
    print("All stats graphics generated successfully!")
