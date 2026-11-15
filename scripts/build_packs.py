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


# ---------------------------------------------------------------- HTML site

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


# ------------------------------------------------------- image processing

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


# ------------------------------------------------------ ornaments.json

def _num(lo, hi):
    return lambda v: (isinstance(v, (int, float)) and not isinstance(v, bool)
                      and lo <= v <= hi)


ORNAMENT_FIELDS = {
    "scale":  _num(0.05, 4),
    "lift":   _num(-1, 1.5),
    "pad":    _num(-1, 2),
    "trim":   _num(0, 0.5),
    "anchor": lambda v: v in ("bottom", "top"),
    "night":  lambda v: v in ("invert", "off"),
    "mirror": lambda v: v in ("off", "always", "alternate"),
    "tap":    lambda v: v == "zoom" or isinstance(v, dict),
    "info":   lambda v: isinstance(v, str) and len(v) <= 4000,
}


def normalize(where, fields):
    fields = dict(fields or {})
    # YAML 1.1 turns an unquoted `off` into False
    for k in ("mirror", "night"):
        if fields.get(k) is False:
            fields[k] = "off"
    for k, v in fields.items():
        check = ORNAMENT_FIELDS.get(k)
        if check is None:
            sys.exit(f"{where}: unknown ornament field '{k}'")
        if not check(v):
            sys.exit(f"{where}: invalid value for '{k}': {v!r}")
    return fields


def load_rules(where, rules):
    out = []
    for i, rule in enumerate(rules or []):
        rule = dict(rule)
        if "match" not in rule:
            sys.exit(f"{where}[{i}]: missing 'match'")
        pattern = str(rule.pop("match"))
        out.append((pattern, normalize(f"{where}[{i}] ({pattern})", rule)))
    return out


def rule_matches(pattern, name, rel):
    """A pattern without '/' is matched against the file name, a pattern
    with '/' against the path relative to the repo root.

    File name mode: exact name (with or without .png), else a glob.
    Path mode: exact path (with or without .png), a folder (everything
    below it), else a glob where '*' also matches '/'.
    """
    if "/" not in pattern:
        return (pattern in (name, Path(name).stem)
                or fnmatch.fnmatchcase(name, pattern))
    folder = pattern.rstrip("/") + "/"
    return (pattern in (rel, Path(rel).with_suffix("").as_posix())
            or rel.startswith(folder)
            or fnmatch.fnmatchcase(rel, pattern))


def build_ornaments(files, base, rule_sets, used):
    """Layer base -> global rules -> pack rules; later layers win per field.

    files maps file name -> path relative to the repo root.
    """
    result = {}
    for name, rel in files.items():
        entry = dict(base)
        for set_id, rules in rule_sets:
            for i, (pattern, fields) in enumerate(rules):
                if rule_matches(pattern, name, rel):
                    used.add((set_id, i))
                    entry.update(fields)
        if entry:
            result[name] = entry
    return result


# ------------------------------------------------------------------ main

def main():
    cfg = yaml.safe_load((ROOT / "packs.yml").read_text(encoding="utf-8"))
    defaults = cfg.get("defaults", {})
    releases = cfg.get("releases", {})

    base = normalize("defaults.ornament", defaults.get("ornament"))
    global_rules = load_rules("ornaments", cfg.get("ornaments"))
    all_rules = {"global": global_rules}
    used_rules = set()

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
        used = {}  # file name -> source rel path
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

        # ornaments.json for this pack
        pack_rules = load_rules(f"packs.{pack_name}.ornaments", pack.get("ornaments"))
        all_rules[pack_name] = pack_rules
        orn = build_ornaments(used, base,
                              [("global", global_rules), (pack_name, pack_rules)],
                              used_rules)
        if orn:
            (pack_dir / "ornaments.json").write_text(
                json.dumps(orn, indent=2, ensure_ascii=False), encoding="utf-8")

        # zip, optionally wrapped in a folder so it can be extracted
        # straight into Bookshelf's ornaments/ directory
        prefix = f"{s['folder']}/" if s.get("folder") else ""
        zip_path = DIST / f"{pack_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(pack_dir.iterdir()):
                z.write(p, prefix + p.name)

        zips[tag].append(zip_path.relative_to(ROOT).as_posix())
        packs_info.append({
            "name": pack_name, "tag": tag, "w": w, "h": h, "r": r,
            "settings": cache_dir.name, "images": images,
            "description": s.get("description", ""),
        })
        print(f"pack '{pack_name}': {len(files)} images", flush=True)

    # warn about ornament rules that never matched anything (typo check)
    for set_id, rules in all_rules.items():
        for i, (pattern, _) in enumerate(rules):
            if (set_id, i) not in used_rules:
                print(f"::warning::ornament rule '{pattern}' ({set_id}) matched no file",
                      flush=True)

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
