# Public radio website

From this directory, use Node 24, `npm ci`, then `npm run dev` for local development or `npm run build` for a static site in `dist/`. Astro reads the checked-in compact snapshot (`../data/web.sqlite`) **only at build time** using `node:sqlite` and bound `sql-template-tag` queries. A clean checkout can build the site without the full FCC database, a Census key, Python, D1, or a live API.

The station directory supports call sign, city, licensee, documented owner, location and estimate-availability filters. Only transmitter coordinates are embedded in the directory. Station and owner pages load one local GeoJSON outline; map tiles use OpenStreetMap with attribution. Links, the directory, ownership lists and profile tables work without JavaScript. The `vendor/` tarball is pinned in the lockfile.

`npm run dev` listens on the local network and prints a terminal QR code for the actual network URL. Scan it from a phone on the same Wi-Fi. Press Ctrl+C to stop.

## Cloudflare

- **Workers Static Assets:** root directory `website`, build `npm ci && npm run build`, deploy `npx wrangler deploy` with `wrangler.jsonc`. Only run the deploy command when ready to publish.
- **Pages:** root `website`, build `npm run build`, output `dist`, Node 24. No adapter, runtime bindings, secrets, or database upload. Preserve the full repository checkout so the build can read `../data/web.sqlite`.
- Publish only `dist/`. The database, authoring tools and Census downloads do not belong in the public asset directory.

## Refresh and verify

From the project root, `make -C data web-db check-web-db`, review the changed snapshot, then rebuild Astro. `/methods/` documents the population model and `/sources.json` gives input checksums. See [the data workflow](../data/README.md#dashboard-database).
