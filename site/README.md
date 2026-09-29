# Website

The public directory is built from the root `README.md`. Change tool entries there. The template, styles and search live in this folder; the build uses Python's standard library.

To preview locally, run these commands from the repository root:

```sh
python3 site/build.py
python3 -m http.server 4173 --directory _site
```

Open `http://localhost:4173`. Generated files in `_site` are ignored by Git.

Run the builder checks with `python3 -m unittest discover -s site -p 'test_*.py'`.

The Website workflow builds pull requests and publishes pushes to `main`. GitHub Pages must use **GitHub Actions** as its publishing source in the repository settings. For a different site address, set `PAGES_URL` when building to update the canonical URL and sitemap.

The local Latin variable fonts match RevManic: [Hanken Grotesk](https://revmanic.com/_next/static/media/hanken-grotesk-latin-wght-normal.3241148m1u9do.woff2) for body text and [Unbounded](https://revmanic.com/_next/static/media/unbounded-latin-wght-normal.1tz5lbfnvawi1.woff2) for the wordmark. Both use the SIL Open Font License 1.1. Their original copyright notices and full licenses are preserved in [HankenGrotesk-OFL.txt](fonts/HankenGrotesk-OFL.txt) and [Unbounded-OFL.txt](fonts/Unbounded-OFL.txt), copied from the official Google Fonts sources for [Hanken Grotesk](https://github.com/google/fonts/blob/main/ofl/hankengrotesk/OFL.txt) and [Unbounded](https://github.com/google/fonts/blob/main/ofl/unbounded/OFL.txt). The build copies the fonts and licenses into `_site/fonts`; no font service is needed at runtime.
