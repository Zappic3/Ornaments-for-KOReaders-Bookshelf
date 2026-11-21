# Create your own ornament packs

This repository turns a folder of images into ready-to-use ornament packs for the [Bookshelf](https://github.com/AndyHazz/bookshelf.koplugin) KOReader plugin. You put your images in folders, describe the packs in one configuration file, and push. GitHub then does the rest:

- it resizes every image, adds an optional outline and writes the `ornaments.json` files,
- it publishes the packs as downloads on GitHub Releases, one release per topic,
- it publishes a preview website, including a **pack builder** where visitors mix parts into their own pack.

You don't need to write code or run anything on your own computer. Everything is configured in `packs.yml`. This guide covers the setup. The complete list of options is in [`packs.md`](packs.md).

## What you need

- A GitHub account.
- Your images as **PNG files with a transparent background**. Any size works, as long as they are large enough to look sharp (see [Images](#images)).
- Bookshelf 5.3 or newer on the reader that will use the packs.

## Setup

1. **Copy the repository.** Click **Fork** on GitHub. Open the **Actions** tab and enable workflows, because GitHub switches them off in forks.
2. **Remove the existing content.** Delete the existing image folders and replace `packs.yml` with your own (see [Your first pack](#your-first-pack)).
3. **Add your images** in folders of your choice, for example `My Topic/Figures/`. Folder names are only used to select files, they don't appear in the finished packs.
4. **Edit `packs.yml`.**
5. **Turn on GitHub Pages.** Go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**. Without this the website can't be published. Private repositories need a paid GitHub plan for Pages.
6. **Push to `main`.** The workflow *Build ornament packs* starts by itself. You can watch it in the **Actions** tab. It can also be started by hand with **Run workflow**.

When it has finished:

- the packs are on the **Releases** page of your repository, one release per topic,
- the website is at `https://YOUR-NAME.github.io/YOUR-REPOSITORY/`,
- the builder is at `https://YOUR-NAME.github.io/YOUR-REPOSITORY/builder/`.

The first run can take a few minutes, depending on how many images there are. Only pushes to `main` publish anything. Other branches only build, so you can test changes safely.

## Your first pack

`packs.yml` has four parts that matter. A small but complete example:

```yaml
defaults:
  width: 600          # size of the finished images in pixels
  height: 600
  outline: 3          # outline width in pixels, 0 = none
  ornament:
    tap: zoom         # tapping an ornament opens it fullscreen with its info text
    anchor: bottom

releases:             # one GitHub release (and one website section) per topic
  my-topic:           # becomes the git tag: letters, digits and - only
    title: "My Topic"
    notes: "Ornaments for my bookshelf"

parts:                # building blocks, used by presets and the builder page
  figures:
    release: my-topic
    title: "Figures"
    include:
      - "My Topic/Figures"        # a folder: all PNGs below it

presets:              # ready-made downloads
  my-topic-figures:
    release: my-topic
    description: "All figures, with outline."
    folder: "My Topic - Figures"  # name of the folder inside the zip
    parts: [figures]
```

What each section is for:

| Section | Purpose |
|---|---|
| `defaults` | Image size and outline for everything. |
| `releases` | The topics. Each one becomes a GitHub release with its own page on the website. |
| `parts` | Sets of images, such as "figures, front view" and "posters". Presets are built from them, and visitors can mix them in the builder. |
| `presets` | The ready-made zip files attached to a release. |

Choose `folder` for every preset. Bookshelf needs a pack to be a folder inside its `ornaments/` directory, so with `folder` your users can extract the zip straight into it (`koreader/settings/bookshelf/ornaments/`, on Kobo `.adds/koreader/settings/bookshelf/ornaments/`). The name is also what the pack is called in the app. Don't use Plain, mine, none or own.

## Images

- **Format:** PNG with transparency. SVG files aren't processed by this repository.
- **Resolution:** keep the originals large, at least as large as the finished size (600×600 by default). They are cropped to the visible drawing, scaled to fit, and placed at the bottom of the canvas, where the shelf plank is.
- **Names:** the file name is what you see in the app, so name files the way you want them to read. For several views of one object, put the view in the name, for example `Miku Figurine [Front].png` and `Miku Figurine [45°].png`. This also makes it easy to select all front views with `*Front*`.
- **Unique names:** inside one release, every file name can only be used once, because parts can be mixed. The build stops with a message that shows both files if there is a clash.

## Common tasks

### Select files

Entries under `include` are paths from the repository root:

```yaml
include:
  - "My Topic/Figures"                      # a whole folder, including subfolders
  - "My Topic/Figures/*Front*.png"          # a pattern, only direct children of that folder
exclude:
  - "*Draft*"                               # leave out matching files anywhere
```

Always put paths in quotes. Square brackets `[` `]` are special characters in patterns, so write `*Front*` instead of `*[Front]*`.

### Give ornaments a description

Ornament rules set the info text shown when an ornament is opened, and other ornament settings:

```yaml
ornaments:
  - match: "My Topic/"                       # everything in that folder, set this first
    info: "A decorative element from My Topic"

  - match: "Miku Figurine*"                  # a file name or pattern, later rules win
    info: |-
      A figurine of the world super-star.

      My Topic
```

A `match` without `/` is compared with the file name. A match with `/` is compared with the path from the repository root. Rules are applied from top to bottom, so put general rules before specific ones.

### Turn the outline on or off

Set `outline` as a default, per image group, or per preset:

```yaml
ornaments:
  - match: "My Topic/Posters/"
    outline: 0                 # posters that already have a frame
```

Presets with their own `outline: 0` produce a zip without outlines for everything. The builder page always offers an outline toggle for every part. It starts switched on for parts that have an outline in the configuration, and visitors can even choose their own outline width and colour.

### Hang posters in the middle of the shelf

```yaml
ornaments:
  - match: "My Topic/Posters/"
    anchor: bottom
    center: wall               # or `books`
    lift: 0.02                 # optional fine tuning, added to the calculated centre
```

`center` calculates the vertical position for you. See the `center` section of [`packs.md`](packs.md) for the details and the other ornament settings (size, spacing, mirroring and more).

### Add a new topic

Add an entry under `releases`, put its images in a new folder, add one or more `parts` and `presets` that use the new release key, and push. Existing releases are not touched. The parts of one release can be mixed on the builder page, parts of different releases can't.

### Rename or remove a pack

Renaming or removing a preset deletes the old zip from its release on the next run. Links to the old file will stop working. Releases themselves are never deleted automatically, remove them by hand on GitHub if you stop using a topic.

## Run it on your own computer (optional)

This is only needed if you want to test without pushing. You need Python 3 and ImageMagick (version 6 or 7):

```bash
pip install pyyaml
GITHUB_REPOSITORY=your-name/your-repo python scripts/build_packs.py
python -m http.server -d site
```

The packs are written to `dist/`, the website to `site/`. Open `http://localhost:8000` to look at it. The builder works locally. The download buttons on the release pages point at GitHub Releases, so they only work after a real run. Add `build/`, `dist/` and `site/` to your `.gitignore`.

## Settings you might need to change

| What | Where | When |
|---|---|---|
| Website address (`SITE_URL`) | `.github/workflows/build-packs.yml`, the `env` line of the build job | If your repository is named `YOUR-NAME.github.io` (use `https://YOUR-NAME.github.io`) or you use a custom domain. It is used for the "Preview" and "Build your own pack" links in the release descriptions. |
| Website title | `build_packs.py`, the heading `Ornament packs` in `build_site` | If you want a different headline on the main page. |
| Shelf proportions for `center` | `shelf:` in `packs.yml` | Only to match a specific device more closely. The defaults work for most. |

## Troubleshooting

| Message or symptom | Cause and fix |
|---|---|
| `Pack '…' matched no files` | The paths in `include` don't match any PNG. Check spelling, quotes and capitals, and note that `Folder/*.png` doesn't look into subfolders. |
| `name collision for '…'` | Two different files with the same name end up in one pack or release. Rename one of them. |
| `missing or unknown release` | The `release` of a part or preset isn't a key under `releases`. |
| `ornament rule '…' matched no file` (warning) | Usually a typo in the `match` of a rule. The build continues. |
| `'outline' is only allowed in ornament rules` | `outline` was put in `defaults.ornament`. Use the top-level `defaults.outline` or a rule. |
| Pages deployment fails | Check **Settings → Pages → Source** is set to *GitHub Actions*. |
| Creating the release fails with a permission error (403) | Check **Settings → Actions → General → Workflow permissions** and allow read and write access. |
| Nothing happens after a push | In a fork, workflows must be enabled once in the **Actions** tab. Changes to Markdown files and `docs/` don't start a build. |
| The "Preview" link in a release is a 404 | On the very first run the release appears a moment before the website. Try again in a minute. |
| Pack opens but ornaments look too small or float | Adjust `scale`, `lift` or `anchor` in a rule, see [`packs.md`](packs.md). The pack editor in Bookshelf (*Updates → Developer updates → Pack editor*) shows values interactively. |

## Further reading

- [`packs.md`](packs.md): the complete reference of every option in `packs.yml`.
- [Bookshelf](https://github.com/AndyHazz/bookshelf.koplugin): how ornaments, themes and packs work in the plugin.
