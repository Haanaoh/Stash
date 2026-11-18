"""Affiche les vues quotidiennes d'une page Wikipedia, par type de visiteur (statistiques Wikimedia).

Utilisation :
    python scripts/wikipedia_pageviews.py                      # page « Wikipédia », 10 derniers jours
    python scripts/wikipedia_pageviews.py "Paris" --days 30 --project en.wikipedia

Wikimedia classe chaque vue selon le visiteur :
    user      : une personne avec un navigateur
    automated : un programme non déclaré, repéré à son comportement (beaucoup de requêtes, etc.)
    spider    : un robot qui se déclare comme tel (User-Agent)
Les chiffres d'un jour sont publiés le lendemain.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "WikipediaReloadScript/1.0 (script de test personnel)"
API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/all-access/{agent}/{article}/daily/{start}/{end}"
AGENTS = ("user", "automated", "spider")


def views(project: str, article: str, agent: str, start: str, end: str) -> dict[str, int]:
    url = API.format(project=project, agent=agent, start=start, end=end,
                     article=urllib.parse.quote(article.replace(" ", "_"), safe=""))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response)
            return {item["timestamp"][:8]: item["views"] for item in data.get("items", [])}
        except urllib.error.HTTPError as error:
            if error.code == 404:  # aucune vue de ce type sur la période
                return {}
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))  # trop de requêtes : on attend avant de réessayer
    return {}


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("article", nargs="?", default="Wikipédia", help="titre de la page")
    args.add_argument("--project", default="fr.wikipedia", help="wiki (fr.wikipedia, en.wikipedia…)")
    args.add_argument("--days", type=int, default=10, help="nombre de jours affichés")
    opts = args.parse_args()

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=opts.days)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    columns = {}
    for agent in AGENTS:
        columns[agent] = views(opts.project, opts.article, agent, start, end)
        time.sleep(2)  # l'API limite le nombre de requêtes

    print(f"Vues de « {opts.article} » ({opts.project})\n")
    print(f"{'Jour':<12}" + "".join(f"{agent:>11}" for agent in AGENTS))
    for day in sorted(set().union(*columns.values())):
        label = f"{day[6:]}/{day[4:6]}/{day[:4]}"
        print(f"{label:<12}" + "".join(f"{columns[agent].get(day, 0):>11}" for agent in AGENTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
