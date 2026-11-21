# `packs.yml` reference

`packs.yml` in the repo root defines which images go into which pack, how they are processed, and which release each pack is published under. The build script (`scripts/build_packs.py`) reads it on every run.

## Repository setup

| File | Purpose |
|---|---|
| `packs.yml` | This configuration. |
| `scripts/build_packs.py` | The build script. |
| `scripts/builder.html` | Template of the builder page, copied into the site by the build. |
| `.github/workflows/build-packs.yml` | Builds everything and publishes the releases and the site. |
| `.gitignore` | Should contain `build/`, `dist/` and `site/` (generated folders). |

One-time setup: **Settings → Pages → Build and deployment → Source: GitHub Actions**. Without it the deploy job fails.

The workflow runs on every push to `main` (except changes to Markdown files, `docs/` and `.gitignore`) and can be started by hand. Other branches and manual runs from other branches only build and don't touch the releases or the site, so you can test config changes safely. Packs that are renamed or removed are deleted from their release on the next run. Releases themselves are never deleted automatically.

## Overview

```yaml
defaults:      # values every pack inherits
releases:      # one GitHub release per topic
shelf:         # reference shelf used to calculate `center` (optional)
ornaments:     # global ornament rules (optional)
parts:         # building blocks: sets of images (optional)
presets:       # ready-made zips for the releases (`packs:` works as an alias)
```

Complete example:

```yaml
defaults:
  width: 400
  height: 600
  outline: 3
  ornament:
    tap: zoom
    anchor: bottom

releases:
  miku-pm2:
    title: "Hatsune Miku: Project Mirai 2"
    notes: "Ornament packs for Project Mirai 2."

ornaments:
  - match: "*Figurine*"
    info: "Hatsune Miku: Project Mirai 2\nFigurine"
  - match: "Hachune Miku Doll*"
    scale: 0.6

packs:
  miku-pm2-figures-front:
    release: miku-pm2
    description: "Frontal view only, with outline."
    folder: "Miku PM2 - Figures (Front)"
    include:
      - "Hatsune Miku: Project Mirai 2/Figurines/*Front*.png"

  miku-pm2-figures-rotated:
    release: miku-pm2
    include:
      - "Hatsune Miku: Project Mirai 2/Figurines/*45°*.png"
    ornaments:
      - match: "*"
        mirror: alternate
```

Always put paths in quotes. Folder names like `Hatsune Miku: Project Mirai 2` contain a colon and a space, which YAML would otherwise read as a key/value separator.

## `defaults`

Values that every pack inherits. A pack can override any of them.

| Key | Type | Description |
|---|---|---|
| `width` | integer | Width of the finished image in pixels. |
| `height` | integer | Height of the finished image in pixels. |
| `outline` | integer | Outline width in pixels. `0` disables the outline. Can be overridden per image with [processing fields](#processing-fields-per-image) in ornament rules. |
| `ornament` | mapping | Base ornament values written for every ornament in every pack (see [Ornament fields](#ornament-fields)). |

Any other pack key (for example `release` or `folder`) can also be set here if all packs should share it. `ornament` here is the only place for base ornament values. A pack's own `ornaments:` list is not inherited from `defaults`.

## `releases`

Each entry becomes one GitHub release and one subpage on the preview site. The key is the git tag, so it must be a simple slug: no spaces, no colons.

```yaml
releases:
  miku-pm2:
    title: "Hatsune Miku: Project Mirai 2"
    notes: "Text shown in the release description."
```

| Key | Description |
|---|---|
| `title` | Display name of the release and the preview page. Defaults to the key. |
| `notes` | Release description. A link to the preview page is appended automatically. |

Release titles and notes are overwritten on every run, so edit them here, not on GitHub. Releases are only created or updated on `main`.

## `parts`

Parts are the building blocks, for example "figures, front view", "figures, rotated view" and "posters". They don't produce a download by themselves. Presets are built from them, and the builder page lets visitors mix them. Every part is processed twice: as configured (with outline) and with outline 0. If both are identical, as for posters whose rule says `outline: 0`, only one variant exists and the builder shows no outline toggle for that part.

```yaml
parts:
  figures-front:
    release: miku-pm2
    title: "Figures (front view)"
    include: ["Hatsune Miku: Project Mirai 2/Figurines/*Front*.png"]
    ornaments:
      - match: "Miku Figurine*"
        info: "The original Miku figurine."
```

| Key | Required | Description |
|---|---|---|
| `release` | yes | Key from `releases` the part belongs to. |
| `include` | yes | Folders and/or globs, see [`include`](#include). |
| `exclude` | no | Glob patterns for files to leave out. |
| `title`, `description` | no | Shown on the builder page. |
| `ornaments` | no | Ornament rules for this part. They apply wherever the part is used: in presets and in the builder. They can't contain [processing fields](#processing-fields-per-image). |

- File names must be unique across all parts of one release, since parts of a release can be mixed. The build fails and shows both paths otherwise. Two parts may contain the very same file.
- Whether a part gets an outline is decided per image by the same layers as everywhere else. The outline-free variant forces `outline: 0` for every image.
- The builder data is written to `packs.json` on the preview site. Each element lists its images and its finished `ornaments.json` entry per variant. The entries come from `defaults.ornament`, the global rules and the part's rules. A preset's own rules are not included, because they only exist in that preset's zip.

## `presets`

Each entry becomes one `<name>.zip`, attached to its release. The name is the file name of the zip, so keep it simple (letters, digits, `-`). `packs:` is the older name for this section and takes the same keys.

```yaml
presets:
  miku-pm2-figures:
    release: miku-pm2
    parts: [figures-front, figures-rotated]

  miku-pm2-everything-flat:
    release: miku-pm2
    outline: 0
    parts: [figures-front, figures-rotated, posters]
    exclude: ["*Hachune*"]
```

A preset combines the images of its `parts` with anything in its own `include`. Its `exclude` patterns apply to both. Parts must belong to the preset's release. The part's ornament rules are applied to its images, followed by the preset's own `ornaments`.

| Key | Required | Description |
|---|---|---|
| `release` | yes | Key from `releases` this pack is attached to. |
| `parts` | no | List of part names. |
| `include` | no | Extra folders and/or globs (see below). At least one of `parts` and `include` is needed. |
| `exclude` | no | List of glob patterns for files to leave out. |
| `width`, `height`, `outline` | no | Override the defaults for this pack. |
| `description` | no | Text shown under the pack heading on the preview page. |
| `folder` | no | Wraps the zip contents in this folder (see below). |
| `ornaments` | no | Ornament rules for this pack only (see [Ornaments](#ornaments)). |

### `include`

Entries are paths relative to the repo root. Each entry is one of:

- **A folder**: includes all PNGs below it, recursively.
- **A glob**: for example `Folder/*Front*.png`. `*` and `?` work as usual.
- `"."`: everything in the repo.

Notes:

- A glob that matches nothing is not an error by itself, but a pack with no matching files at all fails the build.
- `[` and `]` are special in globs. A pattern like `*[Front].png` does **not** match `Name [Front].png`. Use `*Front*.png` instead, or match the brackets literally with `[[]` and `[]]`.
- Duplicate matches are removed.

### `exclude`

Glob patterns, tested against the full path relative to the repo root. `*` also matches `/`, so `*_rot45.png` excludes that suffix in any folder.

### Output

- Packs are always flat: every image ends up at the root of the zip, named like the source file.
- File names must be unique within a pack. Two files with the same name in different folders make the build fail and name both paths.
- Each image is processed once per combination of `width`, `height` and `outline`. Packs that share the same settings reuse the results.

### `folder`

By default the zip contains the files directly. Bookshelf needs a pack to be a subfolder of its `ornaments/` directory, so with

```yaml
folder: "Miku PM2 - Figures"
```

the zip contains that folder and users can extract it straight into `ornaments/`. The folder name is also the pack's name in the app, so make it readable. Avoid the reserved names `Plain`, `mine`, `none` and `own`. The pack contents stay flat either way.

## Ornaments

For every pack, the build writes an `ornaments.json` with one entry per image, keyed by file name. The entries are built from three layers, and later layers override earlier ones field by field:

1. `defaults.ornament`: base values for every image
2. top-level `ornaments:`: global rules, applied in every pack that contains a matching file
3. `packs.<name>.ornaments:`: rules for that pack only

Rules look like this:

```yaml
ornaments:
  - match: "Miku Figurine [Front].png"
    info: "The original Miku figurine."
    scale: 0.9
```

### `match`

`match` works in one of two modes, depending on whether the pattern contains a `/`:

| Pattern | Compared against | Examples |
|---|---|---|
| no `/` | the file name, with and without `.png` | `"Cheer Miku Figurine*"`, `"Miku Figurine [Front].png"` |
| contains `/` | the path relative to the repo root | `"Hatsune Miku: Project Mirai 2/"`, `"Hatsune Miku: Project Mirai 2/Figurines/*Front*.png"` |

- An exact name or path is checked first, so brackets and special characters work literally.
- A path ending in `/` (or naming a folder) matches everything below that folder. A top-level folder needs the trailing slash (`"Hatsune Miku: Project Mirai 2/"`), otherwise it is read as a file name.
- Otherwise the pattern is a glob (`*`, `?`). In path mode `*` also matches `/`.
- If several rules match one file, they apply in order and later ones win per field. Put broad rules (such as a whole folder) first and specific ones after them.
- The build prints a warning for rules that matched no file, which usually means a typo.

Example: a default for a whole topic, overridden for single figures.

```yaml
ornaments:
  - match: "Hatsune Miku: Project Mirai 2/"
    info: "Hatsune Miku: Project Mirai 2"

  - match: "Cheer Miku Figurine*"
    info: |-
      Cheer Miku Figurine
      "Cheer for your favorite team with Miku and her pom-poms!"

      Hatsune Miku: Project Mirai 2
```

### Ornament fields

| Field | Values | Meaning |
|---|---|---|
| `info` | text, max. 4000 characters | Text in the zoom panel below the file name. Use `\n` for line breaks, or a YAML block scalar (`info: \|`). |
| `tap` | `zoom` or a mapping `{action, plugin, internal, label}` | Action when the ornament is tapped. `zoom` shows it fullscreen with the info panel. |
| `scale` | 0.05 to 4 | Size relative to the default (1 = default). |
| `anchor` | `bottom` or `top` | `top` hangs the ornament from the shelf above. |
| `lift` | -1 to 1.5 | Height in shelf heights, positive is up. |
| `pad` | -1 to 2 | Space left and right in book heights. Negative moves it behind the books. |
| `trim` | 0 to 0.5 | Transparent side margin (glow, shadow) tucked behind the books, as a fraction of the image width. |
| `night` | `invert` or `off` | Show the ornament inverted in night mode. |
| `mirror` | `off`, `always` or `alternate` | Mirroring behavior. |
| `center` | `wall`, `books` or `off` | Build-time only: calculates `lift` so the drawing is vertically centered. See [Centering](#centering). Never written to `ornaments.json`. |

The build validates all fields and fails with a message pointing at the offending rule if a name is unknown or a value is out of range. Quote `"off"` in YAML, since an unquoted `off` is read as a boolean (the script converts it back, but quoting is cleaner).

Readers can still override these values in their own personal `ornaments.json` inside the app. The generated file only sets the pack's defaults.

### Processing fields (per image)

Rules can also change how an image is processed, so one pack can mix settings. The typical case is outlines around figures but not around posters, which already have a frame:

```yaml
defaults:
  outline: 3

ornaments:
  - match: "Hatsune Miku: Project Mirai 2/Posters/"
    outline: 0
```

| Field | Values | Meaning |
|---|---|---|
| `outline` | integer, 0 to 100 | Outline width in pixels for matching images. |
| `width`, `height` | integer | Size of the finished image for matching images. |

These fields are applied at build time and are never written to `ornaments.json`. They are only allowed in rules, not in `defaults.ornament`. Where several settings apply to one image, later layers win:

1. `defaults`
2. global `ornaments:` rules
3. the pack's own `width`, `height` and `outline` keys
4. the pack's own `ornaments:` rules

This means a pack with `outline: 0` is outline-free for every image, even where a global rule asks for an outline. A rule inside the pack still beats the pack key. Use a global rule for "this kind of image never gets an outline", and the pack key or a pack rule for packs that differ.

On the preview page, a pack with mixed settings shows all outline widths it uses, for example "outlines 0/3 px".

### Centering

`center` calculates the `lift` for every matching image, so posters and similar pieces hang in the middle without trial and error:

```yaml
ornaments:
  - match: "Hatsune Miku: Project Mirai 2/Posters/"
    anchor: bottom
    center: wall
    lift: 0.02       # optional: added to the calculated centre (+ = up)
```

- `center: wall` centers between the underside of the shelf above and the plank's top surface. `center: books` centers in the space the books stand in. They differ noticeably, because the plank's top surface is deep. `center: off` turns it off again, for example in a pack rule.
- `lift` stays a normal number. Together with `center` it is an offset on top of the calculated centre, so `center: wall` + `lift: 0.02` ends up 0.02 above the centre. The written `ornaments.json` contains only the final `lift` value.
- The calculation uses the actual processed image: its aspect ratio and the visible drawing (transparent margins are ignored), the rule's `scale` and its `anchor`. Put `scale` and `anchor` in the same rule or an earlier one.
- With `anchor: top`, Bookshelf only lets a piece hang lower, never higher, so the calculated lift is zero or negative. If the piece can't be centered (it is too tall for the gap), the build prints a warning and uses the closest value.
- The build fails if the final lift is outside -1 to 1.5.
- Bookshelf applies a reader's own size change on top of the pack's `scale`, which moves the centre a little. The centering is exact for the pack's own values.

### `shelf`

The calculation needs a reference shelf. Lift is measured in book heights, so the defaults work for most devices, and you only need `shelf:` if you want to match your own reader more closely. The values are the same ones as in the ornament placement simulator.

```yaml
shelf:
  row_height: 420   # px, height of one shelf row
  row_gap: 40       # px, gap between two rows
  dp_scale: 1.9     # DPI / 160
```

## Preview site and builder page

The site is generated automatically and needs no configuration in `packs.yml`. It is published at `https://OWNER.github.io/REPO/`.

- The main page lists all releases. Each release page shows every preset with thumbnails and a download button, and the release description links back to it. Presets can be linked directly with `https://OWNER.github.io/REPO/<release>/#<preset-name>`.
- If you define `parts`, the main page also links to the builder at `/builder/`.

### Builder page

Visitors pick a release, switch parts on or off, untick single images, choose a pack name and download one zip. The zip contains the images and a merged `ornaments.json`, inside a folder named after the pack, so it can be extracted straight into Bookshelf's `ornaments/` folder. Reserved names (Plain, mine, none, own) are rejected. Zips are created in the visitor's browser, nothing is uploaded anywhere.

- **Outline toggle:** parts that exist with and without outline get a checkbox. Posters whose outline is always 0 don't.
- **Custom outline:** if any part has the toggle, a "Custom outline" option appears. It lets visitors choose the outline width (1 to 20 px) and colour. The outline is then drawn in the browser on the outline-free image: the figure is scaled into the smaller inner box and its silhouette is grown by the chosen width, which is the same geometry as the build. Against the build's own result, the silhouettes overlap by about 99.5%, so edges can differ by a pixel. It applies to every selected part with the outline option ticked. Thumbnails keep showing the standard outline.
- **Ornament settings:** the merged `ornaments.json` uses the values calculated for the standard outline. For `center`ed pieces this can be off by a hair with a very different outline width.
- **Dependencies:** the page loads JSZip 3.10.1 from cdnjs.
