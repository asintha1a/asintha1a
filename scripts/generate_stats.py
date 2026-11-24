import os
from datetime import date, datetime, timedelta, timezone
from html import escape

import requests
from reliability import TIMEOUT, retry_network, publish_svgs


def fetch_github_data(token, username):
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required; existing assets will be preserved")
    today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0)
    from_date = (today - timedelta(days=364)).replace(hour=0, minute=0, second=0, microsecond=0)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!, $after: String) {
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
        repositories(first: 100, after: $after, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
          pageInfo { hasNextPage endCursor }
          nodes {
            name
            languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
              pageInfo { hasNextPage }
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
    variables = {"login": username, "from": from_date.isoformat(), "to": today.isoformat(), "after": None}
    repositories = []
    while True:
        def fetch():
            with requests.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": variables},
                headers={"Authorization": f"bearer {token}", "User-Agent": "GitHub-Profile-Generator"},
                timeout=TIMEOUT,
            ) as response:
                response.raise_for_status()
                result = response.json()
            if result.get("errors"):
                # Do not replace live statistics with invented fallback values.
                raise RuntimeError("GitHub GraphQL returned errors; existing assets will be preserved")
            if not result.get("data", {}).get("user"):
                raise ValueError("GitHub returned no user data")
            return result["data"]
        data = retry_network(fetch)
        connection = data["user"]["repositories"]
        if any(repo["languages"]["pageInfo"]["hasNextPage"] for repo in connection["nodes"]):
            raise ValueError("Repository language results truncated; refusing incomplete statistics")
        repositories.extend(connection["nodes"])
        if not connection["pageInfo"]["hasNextPage"]:
            break
        cursor = connection["pageInfo"]["endCursor"]
        if not cursor or cursor == variables["after"]:
            raise ValueError("Invalid repository pagination cursor")
        variables["after"] = cursor
    data["user"]["repositories"]["nodes"] = repositories
    return data


def contribution_days(data):
    return sorted((day for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                   for day in week["contributionDays"]), key=lambda day: day["date"])


def streaks(data):
    days = contribution_days(data)
    longest = running = 0
    previous = None
    for day in days:
        current_date = date.fromisoformat(day["date"])
        running = (running + 1 if previous == current_date - timedelta(days=1) else 1) if day["contributionCount"] else 0
        longest = max(longest, running)
        previous = current_date
    # A day still in progress should not break yesterday's active streak.
    if days and days[-1]["date"] == datetime.now(timezone.utc).date().isoformat() and not days[-1]["contributionCount"]:
        days = days[:-1]
    current = 0
    expected = datetime.now(timezone.utc).date()
    if days and date.fromisoformat(days[-1]["date"]) == expected - timedelta(days=1):
        expected -= timedelta(days=1)
    for day in reversed(days):
        if date.fromisoformat(day["date"]) != expected or not day["contributionCount"]:
            break
        current += 1
        expected -= timedelta(days=1)
    return current, longest

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

def generate_streak_svg(data):
    current, longest = streaks(data)
    current_unit = "Day" if current == 1 else "Days"
    longest_unit = "Day" if longest == 1 else "Days"
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.label { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 13px; fill: #8b949e; }',
        '.value { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 24px; font-weight: 600; fill: #58a6ff; }',
        '</style>',
        '<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        '<text x="30" y="45" class="label">Current Streak</text>',
        f'<text x="30" y="85" class="value">{current} {current_unit}</text>',
        '<text x="330" y="45" class="label">Longest Streak</text>',
        f'<text x="330" y="85" class="value">{longest} {longest_unit}</text>',
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
        svg.append(f'<text x="{curr_x + 18}" y="{legend_y}" class="lang-text">{escape(name)} ({pct:.1f}%)</text>')
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
    ]
    # Fit the real contribution calendar into the existing card dimensions.
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    # Match the existing dark background and blue chart identity.
    palette = {"#ebedf0": "#161b22", "#9be9a8": "#0d2944",
               "#40c463": "#1f4f7a", "#30a14e": "#388bfd", "#216e39": "#58a6ff"}
    for x, week in enumerate(weeks):
        for day in week["contributionDays"]:
            y = (date.fromisoformat(day["date"]).weekday() + 1) % 7
            color = "#161b22" if not day["contributionCount"] else palette.get(day["color"], "#58a6ff")
            svg.append(f'<rect x="{30 + x * 10}" y="{44 + y * 7}" width="8" height="5" rx="1" fill="{color}"><title>{day["date"]}: {day["contributionCount"]} contributions</title></rect>')
    svg.append('</svg>')
    with open("year.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

def main():
    username = os.environ.get("GH_LOGIN", "asintha1a")
    data = fetch_github_data(os.environ.get("GITHUB_TOKEN"), username)
    def render():
        generate_stats_svg(data)
        generate_streak_svg(data)
        generate_langs_svg(data)
        generate_year_svg(data)
    publish_svgs(render, ["stats.svg", "streak.svg", "langs.svg", "year.svg"])
    print("All stats graphics generated successfully!")


if __name__ == "__main__":
    main()
