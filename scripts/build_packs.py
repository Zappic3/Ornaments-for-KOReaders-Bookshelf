#!/usr/bin/env python3
import fnmatch, hashlib, html, json, os, re, shutil, subprocess, sys, zipfile
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
# `identify` is `magick identify` in IM7 and a separate binary in IM6
IDENTIFY = ([MAGICK, "identify"] if Path(MAGICK).stem == "magick"
            else [shutil.which("identify") or "identify"])

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


def build_site(releases, packs, has_builder=False):
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
                f'<figure><a href="../img/{st}/{h}.png">'
                f'<img loading="lazy" src="../img/{st}/t/{h}.png" alt="{esc(label)}"></a>'
                f'<figcaption>{esc(label)}</figcaption></figure>'
                for label, h, st in p["images"])
            sizes, outs = p["sizes"], p["outlines"]
            size_txt = (f'{sizes[0][0]}&times;{sizes[0][1]}px' if len(sizes) == 1
                        else "mixed sizes")
            out_txt = (f'outline {outs[0]}px' if len(outs) == 1
                       else "outlines " + "/".join(map(str, outs)) + " px")
            desc = f'<p>{esc(p["description"])}</p>' if p["description"] else ""
            sections.append(
                f'<section id="{esc(p["name"])}"><div class="head">'
                f'<h2>{esc(p["name"])}</h2>'
                f'<span class="mut">{len(p["images"])} images &middot; {size_txt} &middot; '
                f'{out_txt}</span>'
                f'<a class="btn" href="{esc(dl)}">Download .zip</a></div>{desc}'
                f'<div class="grid">{figs}</div></section>')

        body = (f'<p><a href="../">&larr; All releases</a></p><h1>{esc(title)}</h1>'
                f'<p class="mut">{esc(rel.get("notes", ""))}</p>'
                f'<p><a href="https://github.com/{REPO}/releases/tag/{esc(tag)}">Release page on GitHub</a></p>'
                f'<ul class="nav">{nav}</ul>{"".join(sections)}')
        (SITE / tag).mkdir(exist_ok=True)
        (SITE / tag / "index.html").write_text(page(title, body, 1))

    link = ('<p><a href="builder/">Build your own pack from the parts &rarr;</a></p>'
            if has_builder else "")
    index = f'<h1>Ornament packs</h1>{link}<ul class="cards">{"".join(cards)}</ul>'
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
    # build-time only, never written to ornaments.json: centre the piece
    "center": lambda v: v in ("wall", "books", "off"),
}


def _int(lo, hi):
    return lambda v: (isinstance(v, int) and not isinstance(v, bool)
                      and lo <= v <= hi)


# build-time image processing, only allowed in rules (not in defaults.ornament)
PROCESS_FIELDS = {
    "width":   _int(1, 4000),
    "height":  _int(1, 4000),
    "outline": _int(0, 100),
}


def normalize(where, fields, process=False):
    fields = dict(fields or {})
    # YAML 1.1 turns an unquoted `off` into False
    for k in ("mirror", "night", "center"):
        if fields.get(k) is False:
            fields[k] = "off"
    for k, v in fields.items():
        check = ORNAMENT_FIELDS.get(k)
        if check is None and process:
            check = PROCESS_FIELDS.get(k)
        if check is None:
            if k in PROCESS_FIELDS:
                sys.exit(f"{where}: '{k}' is only allowed in ornament rules "
                         f"(global rules and presets; it changes how the image is processed)")
            sys.exit(f"{where}: unknown ornament field '{k}'")
        if not check(v):
            sys.exit(f"{where}: invalid value for '{k}': {v!r}")
    return fields


def load_rules(where, rules, process=True):
    out = []
    for i, rule in enumerate(rules or []):
        rule = dict(rule)
        if "match" not in rule:
            sys.exit(f"{where}[{i}]: missing 'match'")
        pattern = str(rule.pop("match"))
        out.append((pattern, normalize(f"{where}[{i}] ({pattern})", rule,
                                       process=process)))
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


# ---- centring: turn `center` into a lift value -------------------------
# Same formulas as Bookshelf's Orn.sizeFor / SpineShelf.ornamentY, worked out
# for a reference shelf (the `shelf:` section of packs.yml). Lift is measured
# in stand heights, so the result hardly depends on the reference shelf.

def center_geom(shelf):
    row_h, gap, dp = shelf["row_height"], shelf["row_gap"], shelf["dp_scale"]
    b = max(int(row_h * 0.02), int(4 * dp))
    b = min(b, int(9 * dp))
    fh = max(1, int(b * 1.4))
    inset = int(b * 0.8)
    stand = max(1, row_h - fh - inset)
    edge = min(int(stand * 0.2), int(stand / 1.5 * 0.208))
    surf = max(1, int(edge * 1.06))
    hair = int(2 * dp)
    return {"row_h": row_h, "gap": gap, "fh": fh, "stand": stand, "surf": surf,
            "meet": max(0, gap - hair) + hair}


def center_size(g, scale, anchor, lift, aspect, t, b):
    h = int(g["stand"] * 0.8 * scale)
    if anchor == "top":  # a hanging piece must fit between the two shelves
        room0 = max(1, (g["row_h"] - g["fh"] - g["surf"]) + g["gap"] - g["fh"])
        room = max(1, room0 - max(0, -lift) * g["stand"])
        frac = (b - t) or 1
        if h * frac > room:
            h = int(room / frac)
    w = int(h * aspect)
    cap = max(1, int(g["stand"] * scale))
    if w > cap:
        w = cap
        h = int(w / aspect)
    return max(1, w), max(1, h)


def center_lift(g, mode, scale, anchor, aspect, t, b):
    """-> (lift, reachable). t and b: top and bottom of the visible drawing
    as fractions of the image height."""
    if mode == "wall":   # between the shelf above and the plank
        target = (-g["meet"] + (g["row_h"] - g["fh"] - g["surf"])) / 2
    else:                # the middle of the space the books stand in
        target = g["stand"] / 2
    lift, reachable = 0.0, True
    for _ in range(8):
        _, h = center_size(g, scale, anchor, lift, aspect, t, b)
        if anchor == "top":  # can only be lowered from the shelf above
            m = -(target - (b - t) * h / 2 + g["meet"])
            if m > 0:
                reachable = False
            off = min(0, m)
        else:
            off = g["stand"] - h + (t + b) / 2 * h - target
        lift = off / g["stand"]
    return lift, reachable


_box_cache = {}


def content_box(path):
    """-> (aspect, top, bottom) of a processed image: width/height, and the
    visible drawing's top and bottom as fractions of the height."""
    key = str(path)
    if key not in _box_cache:
        out = subprocess.run(IDENTIFY + ["-format", "%w %h %@", key],
                             capture_output=True, text=True, check=True).stdout.split()
        w, h = int(out[0]), int(out[1])
        m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", out[2])
        bh, by = (int(m.group(2)), int(m.group(4))) if m else (h, 0)
        _box_cache[key] = (w / h, max(0, by) / h, min(h, by + bh) / h)
    return _box_cache[key]


def apply_center(where, entry, path, geom):
    mode = entry.pop("center", None)
    if mode in (None, "off"):
        return
    aspect, t, b = content_box(path)
    scale, anchor = entry.get("scale", 1), entry.get("anchor", "bottom")
    base, ok = center_lift(geom, mode, scale, anchor, aspect, t, b)
    lift = round(base + entry.get("lift", 0), 3)
    if not ok:
        print(f"::warning::{where}: cannot fully centre ({mode}, anchor {anchor}, "
              f"scale {scale}); calculated lift {base:.2f}", flush=True)
    if not -1 <= lift <= 1.5:
        sys.exit(f"{where}: centred lift {lift} is outside -1..1.5 "
                 f"(centre {base:.2f} + lift offset {entry.get('lift', 0)})")
    entry["lift"] = lift


def resolve_process(pack_name, defaults, pack, name, rel, global_rules, pack_rules, used):
    """Processing settings for one image. Later layers win:
    defaults -> global rules -> the pack's own keys -> the pack's rules."""
    st = {k: defaults[k] for k in PROCESS_FIELDS if k in defaults}

    def apply(rules, set_id):
        for i, (pattern, fields) in enumerate(rules):
            if rule_matches(pattern, name, rel):
                used.add((set_id, i))
                st.update({k: v for k, v in fields.items() if k in PROCESS_FIELDS})

    apply(global_rules, "global")
    st.update({k: pack[k] for k in PROCESS_FIELDS if k in pack})
    apply(pack_rules, pack_name)
    for k in PROCESS_FIELDS:
        if k not in st:
            sys.exit(f"{pack_name}: '{k}' is not set (add it to defaults)")
    w, h, r = int(st["width"]), int(st["height"]), int(st["outline"])
    if w <= 2 * r or h <= 2 * r:
        sys.exit(f"{pack_name}, {name}: outline {r} is too large for {w}x{h}")
    return w, h, r


def build_ornaments(files, base, rule_sets, used, images, geom):
    """Layer base -> global rules -> pack rules; later layers win per field.

    files maps file name -> path relative to the repo root; images maps file
    name -> the processed image (used for `center`). rule_sets is a list of
    (set id, rules, only) where `only` limits the rules to a set of file names.
    """
    result = {}
    for name, rel in files.items():
        entry = dict(base)
        for set_id, rules, only in rule_sets:
            if only is not None and name not in only:
                continue
            for i, (pattern, fields) in enumerate(rules):
                if rule_matches(pattern, name, rel):
                    used.add((set_id, i))
                    entry.update({k: v for k, v in fields.items()
                                  if k not in PROCESS_FIELDS})
        apply_center(name, entry, images[name], geom)
        if entry:
            result[name] = entry
    return result


# ------------------------------------------------------------------ main

def process_image(label, defaults, pack, name, rel, src, global_rules, pack_rules, used_rules):
    """Resolve the settings for one image and process it (cached).
    -> (processed path, (w, h, outline), settings folder name)"""
    w, h, r = resolve_process(label, defaults, pack, name, rel,
                              global_rules, pack_rules, used_rules)
    cache_dir = CACHE / f"{w}x{h}_r{r}"
    cached = cache_dir / rel
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        print(f"processing {rel} ({w}x{h}, outline {r})", flush=True)
        process(src, cached, w, h, r)
    return cached, (w, h, r), cache_dir.name


def main():
    cfg = yaml.safe_load((ROOT / "packs.yml").read_text(encoding="utf-8"))
    defaults = cfg.get("defaults", {})
    releases = cfg.get("releases", {})

    base = normalize("defaults.ornament", defaults.get("ornament"))
    global_rules = load_rules("ornaments", cfg.get("ornaments"))
    all_rules = {"global": global_rules}
    used_rules = set()

    shelf = {"row_height": 420, "row_gap": 40, "dp_scale": 1.9,
             **(cfg.get("shelf") or {})}
    for k, v in shelf.items():
        if k not in ("row_height", "row_gap", "dp_scale"):
            sys.exit(f"shelf: unknown key '{k}'")
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            sys.exit(f"shelf.{k}: must be a positive number")
    geom = center_geom(shelf)

    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(SITE, ignore_errors=True)
    DIST.mkdir(parents=True)
    SITE.mkdir(parents=True)

    # `packs:` is the old name for `presets:`
    presets = dict(cfg.get("packs") or {})
    for k, v in (cfg.get("presets") or {}).items():
        if k in presets:
            sys.exit(f"'{k}' is defined in both 'packs' and 'presets'")
        presets[k] = v

    # ---- parts: building blocks, processed with and without outline -------
    parts, claimed = {}, {}  # claimed: release -> {file name: (part, rel)}
    site_parts = {tag: [] for tag in releases}
    for pname, part in (cfg.get("parts") or {}).items():
        tag = part.get("release")
        if tag not in releases:
            sys.exit(f"Part '{pname}': missing or unknown release '{tag}'")
        files = collect(part.get("include", []), part.get("exclude", []))
        if not files:
            sys.exit(f"Part '{pname}' matched no files")

        names = {}  # file name -> rel
        for rel, src in files.items():
            other = claimed.setdefault(tag, {}).get(src.name)
            if other and other[1] != rel:
                sys.exit(f"Part '{pname}': file name '{src.name}' is also used by "
                         f"part '{other[0]}':\n  {other[1]}\n  {rel}\n"
                         f"Parts of one release can be mixed, so names must be unique.")
            claimed[tag][src.name] = (pname, rel)
            names[src.name] = rel

        rules = load_rules(f"parts.{pname}.ornaments", part.get("ornaments"), process=False)
        all_rules[f"part:{pname}"] = rules
        parts[pname] = {"tag": tag, "files": files, "names": names, "rules": rules}

        elems = {n: {"name": n, "label": Path(n).stem, "variants": {}} for n in names}
        for vname, key in (("default", {}), ("plain", {"outline": 0})):
            processed, meta = {}, {}
            for n, rel in names.items():
                cached, (w, h, r), sdir = process_image(
                    pname, defaults, key, n, rel, files[rel], global_rules, [], used_rules)
                processed[n] = cached
                meta[n] = (w, h, r, sdir, publish_to_site(cached, rel, sdir))
            orn = build_ornaments(names, base,
                                  [("global", global_rules, None),
                                   (f"part:{pname}", rules, None)],
                                  used_rules, processed, geom)
            for n, (w, h, r, sdir, hsh) in meta.items():
                if vname == "plain" and sdir == elems[n]["variants"]["default"]["settings"]:
                    continue  # same image with and without outline (e.g. posters)
                elems[n]["variants"][vname] = {
                    "img": f"img/{sdir}/{hsh}.png", "thumb": f"img/{sdir}/t/{hsh}.png",
                    "width": w, "height": h, "outline": r, "settings": sdir,
                    "ornament": orn.get(n, {})}
        for e in elems.values():
            for v in e["variants"].values():
                del v["settings"]
        site_parts[tag].append({
            "name": pname, "title": part.get("title", pname),
            "description": part.get("description", ""),
            "outline_toggle": any("plain" in e["variants"] for e in elems.values()),
            "elements": sorted(elems.values(), key=lambda e: e["name"])})
        print(f"part '{pname}': {len(names)} images", flush=True)

    # ---- presets: ready-made zips attached to releases --------------------
    zips = {tag: [] for tag in releases}
    packs_info = []

    for pack_name, pack in presets.items():
        s = {**defaults, **pack}
        tag = s.get("release")
        if tag not in releases:
            sys.exit(f"Pack '{pack_name}': missing or unknown release '{tag}'")

        files, part_sets = {}, []
        for pn in pack.get("parts") or []:
            if pn not in parts:
                sys.exit(f"Pack '{pack_name}': unknown part '{pn}'")
            if parts[pn]["tag"] != tag:
                sys.exit(f"Pack '{pack_name}': part '{pn}' belongs to release "
                         f"'{parts[pn]['tag']}', not '{tag}'")
            files.update(parts[pn]["files"])
            part_sets.append((f"part:{pn}", parts[pn]["rules"], set(parts[pn]["names"])))
        files.update(collect(s.get("include", []), []))
        excludes = s.get("exclude", [])
        files = {rel: src for rel, src in sorted(files.items())
                 if not any(fnmatch.fnmatch(rel, x) for x in excludes)}
        if not files:
            sys.exit(f"Pack '{pack_name}' matched no files")

        pack_rules = load_rules(f"packs.{pack_name}.ornaments", pack.get("ornaments"))
        all_rules[pack_name] = pack_rules
        pack_dir = DIST / pack_name
        pack_dir.mkdir()
        used = {}  # file name -> source rel path
        processed = {}  # file name -> processed image
        images = []
        settings = set()  # (w, h, outline) used in this pack

        for rel, src in files.items():
            if src.name in used:
                sys.exit(f"Pack '{pack_name}': name collision for '{src.name}':\n"
                         f"  {used[src.name]}\n  {rel}\n"
                         f"Rename one of them or narrow the include/exclude.")
            used[src.name] = rel

            cached, (w, h, r), sdir = process_image(
                pack_name, defaults, pack, src.name, rel, src,
                global_rules, pack_rules, used_rules)
            settings.add((w, h, r))
            shutil.copy(cached, pack_dir / src.name)
            processed[src.name] = cached
            images.append((src.stem, publish_to_site(cached, rel, sdir), sdir))

        # ornaments.json for this pack
        orn = build_ornaments(used, base,
                              [("global", global_rules, None)] + part_sets
                              + [(pack_name, pack_rules, None)],
                              used_rules, processed, geom)
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
            "name": pack_name, "tag": tag, "images": images,
            "sizes": sorted({(w, h) for w, h, _ in settings}),
            "outlines": sorted({r for _, _, r in settings}),
            "description": s.get("description", ""),
        })
        print(f"pack '{pack_name}': {len(files)} images", flush=True)

    # warn about ornament rules that never matched anything (typo check)
    for set_id, rules in all_rules.items():
        for i, (pattern, _) in enumerate(rules):
            if (set_id, i) not in used_rules:
                print(f"::warning::ornament rule '{pattern}' ({set_id}) matched no file",
                      flush=True)

    has_builder = any(site_parts.values())
    build_site(releases, packs_info, has_builder)

    # data and page for the mix-and-match builder
    if has_builder:
        (SITE / "builder").mkdir()
        shutil.copy(ROOT / "scripts" / "builder.html", SITE / "builder" / "index.html")
        data = {"repo": REPO, "releases": {
            tag: {"title": rel.get("title", tag), "notes": rel.get("notes", ""),
                  "parts": site_parts[tag]}
            for tag, rel in releases.items() if site_parts[tag]}}
        (SITE / "packs.json").write_text(
            json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

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
