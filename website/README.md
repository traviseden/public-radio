# Public radio website

From this directory run `npm ci`, then `npm run dev` for local development or `npm run build` for a static site in `dist/`.

The `vendor/` tarball is the unpublished `leaflet-webcomponents` package. It and Leaflet are installed from `package-lock.json`; the hello-world page does not load either into the browser. For a future map, register the components in an Astro client `<script>`, not in server-side frontmatter. FCC and demographic data preparation belongs in `../data/`.
