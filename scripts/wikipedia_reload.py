"""Ouvre une page Wikipedia, regarde son HTML, puis recharge la page.

Utilisation :
    python scripts/wikipedia_reload.py                          # page par défaut, 3 chargements
    python scripts/wikipedia_reload.py https://fr.wikipedia.org/wiki/Python_(langage) -n 5 -i 10
    python scripts/wikipedia_reload.py URL -n 0                 # recharge sans fin (Ctrl+C pour arrêter)
    python scripts/wikipedia_reload.py URL -n 0 -i 60 --duration 24   # toutes les minutes pendant 24 h

À chaque chargement, le script affiche ce qu'il trouve dans l'HTML (titre, taille, révision,
nombre de liens et d'images, sections) et signale si la page a changé depuis le chargement précédent.
Seule la bibliothèque standard de Python est utilisée.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

DEFAULT_URL = "https://fr.wikipedia.org/wiki/Wikip%C3%A9dia"
# Wikipedia refuse les requêtes sans User-Agent descriptif.
USER_AGENT = "WikipediaReloadScript/1.0 (script de test personnel)"
# Valeurs que Wikipedia change à chaque requête sans que la page change : on les ignore pour comparer.
VOLATILE = re.compile(r'"(wgRequestId|wgHostname|wgBackendResponseTime)":("[^"]*"|\d+)')


class PageInspector(HTMLParser):
    """Relève quelques éléments de l'HTML d'une page Wikipedia."""

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links = 0
        self.images = 0
        self.headings: list[str] = []
        self._in_title = False
        self._in_heading = False
        self._heading_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag == "a" and dict(attrs).get("href"):
            self.links += 1
        elif tag == "img":
            self.images += 1
        elif tag == "h2":
            self._in_heading = True
            self._heading_text = ""

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h2" and self._in_heading:
            self._in_heading = False
            text = " ".join(self._heading_text.split())
            if text:
                self.headings.append(text)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_heading:
            self._heading_text += data


def fetch(url: str) -> tuple[int, str]:
    # Cache-Control: no-cache pour obtenir une vraie version fraîche à chaque rechargement.
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, response.read().decode(charset, errors="replace")


def inspect(html: str) -> dict:
    parser = PageInspector()
    parser.feed(html)
    revision = re.search(r'"wgRevisionId":(\d+)', html)
    return {
        "title": parser.title.strip(),
        "size": len(html.encode("utf-8")),
        "revision": revision.group(1) if revision else "?",
        "links": parser.links,
        "images": parser.images,
        "headings": parser.headings,
        "hash": hashlib.sha256(VOLATILE.sub("", html).encode("utf-8")).hexdigest()[:12],
    }


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("url", nargs="?", default=DEFAULT_URL, help="page Wikipedia à ouvrir")
    args.add_argument("-n", "--times", type=int, default=3, help="nombre de chargements (0 = sans fin)")
    args.add_argument("-i", "--interval", type=float, default=5.0, help="secondes entre deux chargements")
    args.add_argument("--duration", type=float, metavar="HEURES", help="s'arrête au bout de ce nombre d'heures")
    args.add_argument("--save", metavar="FICHIER", help="enregistre l'HTML du dernier chargement")
    opts = args.parse_args()

    if "wikipedia.org" not in opts.url:
        print("Attention : l'adresse ne semble pas être une page Wikipedia.", file=sys.stderr)

    previous = None
    count = 0
    errors = 0
    deadline = time.monotonic() + opts.duration * 3600 if opts.duration else None
    try:
        while (opts.times == 0 or count < opts.times) and (deadline is None or time.monotonic() < deadline):
            count += 1
            label = "Chargement" if count == 1 else "Rechargement"
            print(f"\n[{time.strftime('%H:%M:%S')}] {label} n°{count} : {opts.url}")
            try:
                status, html = fetch(opts.url)
            except (urllib.error.URLError, TimeoutError) as error:
                errors += 1
                print(f"  Échec : {error}")
            else:
                info = inspect(html)
                print(f"  Statut HTTP : {status}")
                print(f"  Titre       : {info['title']}")
                print(f"  Taille      : {info['size']:,} octets".replace(",", " "))
                print(f"  Révision    : {info['revision']}")
                print(f"  Liens       : {info['links']}   Images : {info['images']}")
                sections = ", ".join(info["headings"][:8])
                if len(info["headings"]) > 8:
                    sections += ", …"
                print(f"  Sections    : {sections or '(aucune)'}")
                if previous is not None:
                    if info["revision"] != previous["revision"]:
                        print(f"  -> Nouvelle révision ({previous['revision']} -> {info['revision']})")
                    elif info["hash"] != previous["hash"]:
                        print("  -> Même révision, mais l'HTML a légèrement changé")
                    else:
                        print("  -> Page identique au chargement précédent")
                previous = info
                if opts.save:
                    with open(opts.save, "w", encoding="utf-8") as file:
                        file.write(html)
            if opts.times == 0 or count < opts.times:
                time.sleep(opts.interval)
    except KeyboardInterrupt:
        print("\nArrêté.")
    print(f"\nTerminé à {time.strftime('%H:%M:%S')} : {count} chargement(s), dont {errors} échec(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
