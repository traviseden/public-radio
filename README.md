# Public radio reach

Search the public radio roster and explore modeled residential reach and ACS demographics for stations and documented owners. This is a static Astro dashboard; its build-time data is already in the repository.

```sh
cd website
npm ci
npm run dev
```

To build Cloudflare-ready assets, run `npm run build` in `website/`. [Website and hosting instructions](website/README.md).

## Data paths

1. **Full research database:** `make -C data db` imports the local FCC source files for Datasette. See [FCC input setup](data/README.md#getting-started).
2. **Optional dashboard database:** `make -C data web-db` reads the full database, joins the public roster to eligible FCC contours, and precomputes demographic profiles using the 2020 Census and 2020–2024 ACS. `make -C data check-web-db` checks the snapshot and its lookup indexes. See [build and selection rules](data/README.md#dashboard-database).

The shipped snapshot covers 397 roster entries; 383 have mapped primary FM footprints, and 382 have a supported resident estimate. Guam has a footprint but no comparable Census/ACS profile in this build. Three owner groups are documented. Coverage is for linked **roster members**, not every station a network may operate. The next data checkpoint is reviewing unresolved facilities and extending sourced ownership links before rebuilding the snapshot.
