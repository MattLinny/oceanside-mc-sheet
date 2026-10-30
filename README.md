# Oceanside Sunday MC Sheet

Phone-first MC sheet for the Sunday Service (8:30 & 10:30), rebuilt from Planning Center every 10 minutes by GitHub Actions and served on GitHub Pages.

- `fetch_pco.py` pulls today's plan (or the next one) from the Planning Center API into `input.json`.
- `build_page.py` turns `input.json` into the page; `wrap.py` makes it a standalone HTML file.
- `.github/workflows/build.yml` runs both on a schedule and deploys. Run it by hand from the Actions tab ("Run workflow").

Secrets (Settings → Secrets and variables → Actions): `PCO_APP_ID`, `PCO_SECRET` from a Planning Center personal access token.

The page data is never committed; it only exists in the deployed site.
