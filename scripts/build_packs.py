#!/usr/bin/env python3
import fnmatch, shutil, subprocess, sys, zipfile
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
CACHE = BUILD / "cache"
DIST = ROOT / "dist"
SKIP_PREFIXES = ("build/", "dist/", ".git/", ".github/")

MAGICK = shutil.which("magick") or shutil.which("convert")  # IM7 or IM6
if not MAGICK:
    sys.exit("ImageMagick not found")


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


def main():
    cfg = yaml.safe_load((ROOT / "packs.yml").read_text())
    defaults = cfg.get("defaults", {})

    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)

    for pack_name, pack in cfg["packs"].items():
        s = {**defaults, **pack}
        w, h, r = int(s["width"]), int(s["height"]), int(s["outline"])

        files = collect(s.get("include", []), s.get("exclude", []))
        if not files:
            sys.exit(f"Pack '{pack_name}' matched no files")

        cache_dir = CACHE / f"{w}x{h}_r{r}"
        pack_dir = DIST / pack_name
        pack_dir.mkdir()
        used = {}  # file name -> source rel path

        for rel, src in files.items():
            if src.name in used:
                sys.exit(f"Pack '{pack_name}': name collision for '{src.name}':\n"
                         f"  {used[src.name]}\n  {rel}\n"
                         f"Rename one of them or narrow the include/exclude.")
            used[src.name] = rel

            cached = cache_dir / rel
            if not cached.exists():
                cached.parent.mkdir(parents=True, exist_ok=True)
                print(f"processing {rel} ({w}x{h}, outline {r})")
                process(src, cached, w, h, r)

            shutil.copy(cached, pack_dir / src.name)

        with zipfile.ZipFile(DIST / f"{pack_name}.zip", "w",
                             zipfile.ZIP_DEFLATED) as z:
            for p in sorted(pack_dir.iterdir()):
                z.write(p, p.name)
        print(f"pack '{pack_name}': {len(files)} images")


if __name__ == "__main__":
    main()
