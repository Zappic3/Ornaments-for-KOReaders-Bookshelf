#!/usr/bin/env python3
import fnmatch, hashlib, html, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
CACHE = BUILD / "cache"
DIST = ROOT / "dist"
SITE = ROOT / "site"
SKIP_PREFIXES = ("build/", "dist/", "site/", ".git/", ".github/")

REPO = os.environ.get("GITHUB_REPOSITORY", "OWNER/REPO")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")

MAGICK = shutil.which("magick") or shutil.which("convert")  # IM7 or IM6
if not MAGICK:
    sys.exit("ImageMagick not found")

CSS = """
:root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--card:#f1f1f4;--mut:#6b6b75;--acc:#0a6cff}
@media(prefers-color-scheme:dark){:root{--bg:#16171a;--fg:#e8e8ea;--card:#232429;--mut:#9a9aa4;--acc:#6aa5ff}}
body{margin:0;font:16px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--acc)}
h1{margin:.2em 0}
.mut{color:var(--mut)}
.cards,.nav{list-style:none;padding:0;display:grid;gap:12px}
.cards{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.cards a{display:flex;flex-direction:column;gap:4px;background:var(--card);padding:16px;border-radius:10px;text-decoration:none;color:inherit}
.cards a:hover{outline:2px solid var(--acc)}
.nav{grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:4px 16px}
section{margin-top:40px}
.head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px}
.btn{margin-left:auto;background:var(--acc);color:#fff;padding:6px 14px;border-radius:8px;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin-top:12px}
figure{margin:0;background:var(--card);border-radius:8px;padding:6px}
figure img{display:block;width:100%;height:auto;border-radius:4px;
  background:repeating-conic-gradient(#8884 0% 25%,transparent 0% 50%) 0 0/16px 16px}
figcaption{font-size:12px;margin-top:4px;word-break:break-word}
"""


def esc(s):
    return html.escape(str(s))


def page(title, body, depth):
    css = "../" * depth + "style.css"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><link rel="stylesheet" href="{css}">'
            f'</head><body><main>{body}</main></body></html>')


def build_site(releases, packs):
    SITE.mkdir(exist_ok=True)
    (SITE / "style.css").write_text(CSS)
    cards = []

    for tag, rel in releases.items():
        rp = [p for p in packs if p["tag"] == tag]
        if not rp:
            continue
        title = rel.get("title", tag)
        cards.append(f'<li><a href="{esc(tag)}/"><strong>{esc(title)}</strong>'
                     f'<span class="mut">{len(rp)} packs</span></a></li>')

        nav = "".join(f'<li><a href="#{esc(p["name"])}">{esc(p["name"])}</a> '
                      f'<span class="mut">({len(p["images"])})</span></li>' for p in rp)
        sections = []
        for p in rp:
            dl = f"https://github.com/{REPO}/releases/download/{tag}/{p['name']}.zip"
            figs = "".join(
                f'<figure><a href="../img/{p["settings"]}/{h}.png">'
                f'<img loading="lazy" src="../img/{p["settings"]}/t/{h}.png" alt="{esc(label)}"></a>'
                f'<figcaption>{esc(label)}</figcaption></figure>'
                for label, h in p["images"])
            desc = f'<p>{esc(p["description"])}</p>' if p["description"] else ""
            sections.append(
                f'<section id="{esc(p["name"])}"><div class="head">'
                f'<h2>{esc(p["name"])}</h2>'
                f'<span class="mut">{len(p["images"])} images &middot; {p["w"]}&times;{p["h"]}px &middot; '
                f'outline {p["r"]}px</span>'
                f'<a class="btn" href="{esc(dl)}">Download .zip</a></div>{desc}'
                f'<div class="grid">{figs}</div></section>')

        body = (f'<p><a href="../">&larr; All releases</a></p><h1>{esc(title)}</h1>'
                f'<p class="mut">{esc(rel.get("notes", ""))}</p>'
                f'<p><a href="https://github.com/{REPO}/releases/tag/{esc(tag)}">Release page on GitHub</a></p>'
                f'<ul class="nav">{nav}</ul>{"".join(sections)}')
        (SITE / tag).mkdir(exist_ok=True)
        (SITE / tag / "index.html").write_text(page(title, body, 1))

    index = f'<h1>Ornament packs</h1><ul class="cards">{"".join(cards)}</ul>'
    (SITE / "index.html").write_text(page("Ornament packs", index, 0))


def process(src: Path, dst: Path, w: int, h: int, r: int):
    iw, ih = w - 2 * r, h - 2 * r
    cmd = [
        MAGICK, str(src), "-trim", "+repage",
        "-filter", "Lanczos", "-resize", f"{iw}x{ih}",
        "-channel", "RGB", "-level", "3%,97%", "+channel",
        "-unsharp", "0x0.8",
    ]
    if r > 0:
        cmd += [
            "-bordercolor", "none", "-border", str(r + 2),
            "(", "+clone", "-channel", "A",
            "-morphology", "Dilate", f"Disk:{r}", "+channel",
            "-fill", "black", "-colorize", "100", ")",
            "+swap", "-composite", "-trim", "+repage",
        ]
    cmd += ["-background", "none", "-gravity", "south",
            "-extent", f"{w}x{h}", str(dst)]
    subprocess.run(cmd, check=True)


def collect(includes, excludes):
    """Return {relative_posix_path: absolute_path} for all matching PNGs."""
    found = {}
    for entry in includes:
        p = ROOT / entry
        candidates = p.rglob("*") if p.is_dir() else ROOT.glob(entry)
        for f in candidates:
            if not f.is_file() or f.suffix.lower() != ".png":
                continue
            rel = f.relative_to(ROOT).as_posix()
            if rel.startswith(SKIP_PREFIXES):
                continue
            if any(fnmatch.fnmatch(rel, x) for x in excludes):
                continue
            found[rel] = f
    return dict(sorted(found.items()))


def publish_to_site(cached: Path, rel: str, settings: str) -> str:
    """Copy image + thumbnail into the site once per (settings, file). Returns hash."""
    h = hashlib.sha1(rel.encode()).hexdigest()[:12]
    img_dir = SITE / "img" / settings
    full = img_dir / f"{h}.png"
    if not full.exists():
        (img_dir / "t").mkdir(parents=True, exist_ok=True)
        shutil.copy(cached, full)
        subprocess.run([MAGICK, str(cached), "-resize", "240x",
                        str(img_dir / "t" / f"{h}.png")], check=True)
    return h


def main():
    cfg = yaml.safe_load((ROOT / "packs.yml").read_text())
    defaults = cfg.get("defaults", {})
    releases = cfg.get("releases", {})

    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(SITE, ignore_errors=True)
    DIST.mkdir(parents=True)
    SITE.mkdir(parents=True)

    zips = {tag: [] for tag in releases}
    packs_info = []

    for pack_name, pack in cfg["packs"].items():
        s = {**defaults, **pack}
        tag = s.get("release")
        if tag not in releases:
            sys.exit(f"Pack '{pack_name}': missing or unknown release '{tag}'")

        w, h, r = int(s["width"]), int(s["height"]), int(s["outline"])

        files = collect(s.get("include", []), s.get("exclude", []))
        if not files:
            sys.exit(f"Pack '{pack_name}' matched no files")

        cache_dir = CACHE / f"{w}x{h}_r{r}"
        pack_dir = DIST / pack_name
        pack_dir.mkdir()
        used = {}
        images = []

        for rel, src in files.items():
            if src.name in used:
                sys.exit(f"Pack '{pack_name}': name collision for '{src.name}':\n"
                         f"  {used[src.name]}\n  {rel}\n"
                         f"Rename one of them or narrow the include/exclude.")
            used[src.name] = rel

            cached = cache_dir / rel
            if not cached.exists():
                cached.parent.mkdir(parents=True, exist_ok=True)
                print(f"processing {rel} ({w}x{h}, outline {r})", flush=True)
                process(src, cached, w, h, r)

            shutil.copy(cached, pack_dir / src.name)
            images.append((src.stem, publish_to_site(cached, rel, cache_dir.name)))

        zip_path = DIST / f"{pack_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(pack_dir.iterdir()):
                z.write(p, p.name)
        zips[tag].append(zip_path.relative_to(ROOT).as_posix())
        packs_info.append({
            "name": pack_name, "tag": tag, "w": w, "h": h, "r": r,
            "settings": cache_dir.name, "images": images,
            "description": s.get("description", ""),
        })
        print(f"pack '{pack_name}': {len(files)} images", flush=True)

    build_site(releases, packs_info)

    manifest = []
    for tag, rel in releases.items():
        if not zips[tag]:
            continue
        notes = rel.get("notes", "")
        if SITE_URL:
            notes += f"\n\n**[Preview all packs]({SITE_URL}/{tag}/)**"
        manifest.append({"tag": tag, "title": rel.get("title", tag),
                         "notes": notes.strip(), "files": zips[tag]})
    (DIST / "releases.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
