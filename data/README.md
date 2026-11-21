# public-radio

A Code for Charlottesville project in collaboration with SemiPublic.org to collect data on public radio and TV stations and store the data on Wikidata.

Our aims are:

1. Group public radio stations by top level ownership

2. Map the geographic reach of all public radio stations, grouped by top level owner

3. Produce a dashboard where demographic data is joined on public radio's geographic reach

4. Store data on wikidata for posterity

## Getting Started

You will need to download the following public FCC Database Files to the tables directory in order to generate the database locally via a script. An index of the files can be found here: [LMS Public Database Files](https://enterpriseefiling.fcc.gov/dataentry/public/tv/lmsDatabase.html#). Individual links to the tables relevant to this work are provided below.

- [application_facility](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/application_facility.zip)
- [application](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/application.zip)
- [facility](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/facility.zip)
- [facility_applicant](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/facility_applicant.zip)
- [license_filing_version](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/license_filing_version.zip)
- [lkp_application_purpose](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/lkp_application_purpose.zip)
- [lkp_application_sub_purpose](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/lkp_application_sub_purpose.zip)
- [lkp_authorization_type](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/lkp_authorization_type.zip)
- [lkp_filing_status](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/lkp_filing_status.zip)
- [lkp_filing_type](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/lkp_filing_type.zip)
- [ownership_reports_respondent_representative_info](https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/11-03-2026/ownership_reports_respondent_representative_info.zip)

We will also need the FM service contour data. Note that this does not include AM stations and a description on the data shape and method used by the FCC to determine these contours can be found [here](https://www.fcc.gov/media/radio/fm-service-contour-data-points).

- [FM_service_contour_current](https://transition.fcc.gov/bureaus/mb/databases/map/FM_service_contour_current.zip)

## Building the Database and Launching Datasette

The project uses a `Makefile` and [uv](https://docs.astral.sh/uv/) to manage tasks. If you don't have uv on your machine, you will need to [install](https://docs.astral.sh/uv/getting-started/installation/) it. On first run, `uv` creates a `.venv` and installs dependencies from `pyproject.toml`. From the repo root, run `cd data` before using the `make` commands below, since the scripts use paths relative to `data/`.

1. Download the FCC files listed above and extract them into `data/tables/`. You may need to create the directory if it does not exist (the build reads `tables/*.dat` from `data/`).

2. Build the SQLite database:

   ```bash
   make db
   ```

   This runs `scripts/create_db.py` and produces `public_radio_facility_data.sqlite`.

3. Launch a local [Datasette](https://datasette.io/) instance to explore the data:

   ```bash
   make launch-datasette
   ```

   This serves the database using `metadata.yaml`, with a 20 second SQL time limit. Open the URL printed in the terminal (by default http://127.0.0.1:8001) in your browser.

Run `make help` to see all available targets, including `stations`, `stations-force`, and `validate` for working with the station YAML files.

## Dashboard database

`make db` remains the complete FCC import for research and Datasette. `make web-db` reads that database **read-only** and atomically builds the separate `web.sqlite` used by Astro. It does not rebuild or overwrite the full database. The compact snapshot is intentionally versioned so a Cloudflare build doesn't have to download national inputs.

```sh
cd data
make db             # if you haven't built the full FCC DB from the source files
make web-db         # keyless national build; first run caches ~2.5 GB
make check-web-db   # includes EXPLAIN QUERY PLAN checks
```

The optional `reach` extra adds Shapely, pyproj, Pyogrio's TIGER reader and NumPy to the builder only. `downloads/reach/` caches 2020 Census state P.L. archives, 2024 TIGER block groups and seven ACS 2020–24 Detailed Tables for all states, DC and Puerto Rico. A rerun checks cached input hashes against the previous manifest. The original FCC files and individual Census units do **not** ship in `web.sqlite`.

**Selection.** The allowlist is `station_index.csv` rows of type Radio or Both. Callsign, state and exact roster filing links identify FCC facilities. Educational FM/LPFM facilities can qualify automatically. `reviewed_facilities.csv` supports individually corroborated public operators, including public broadcasters on commercial-designated channels. Neither flag nor affiliation on its own adds an off-roster station. A selected contour must uniquely match the facility's license and an active, granted primary filing. Ambiguous, auxiliary, AM/TV, unmatched and unsupported records are not assigned a fabricated population. Keep the roster ID stable when reviewing a match.

**Owners.** Populated station YAMLs take precedence; if the control field is `N` a named licensee can be its own owner under the project's schema. Otherwise only exact licensees with evidence in `documented_owners.csv` are grouped. Do not merge by an NPR affiliation, similar name, or historic FRN alone. Owner totals are for documented roster members only. Union their polygons first; if a member lacks an eligible footprint, withhold the complete result. To extend coverage, add a sourced parent relationship, rerun and review the membership and overlap.

**Measurement.** The P.L. geographic header supplies 2020 residents and internal points (summary level `750`); segment 02, H1, supplies occupied units joined by `LOGRECNO`. Cross-check occupied + vacant against the block header. Spatially assign those points to actual 2024 BGs, not truncated 2020 identifiers. Whole BGs receive weight one; for partially intersecting BGs use the covered share of resident points weighted by population, or by occupied units for households. Missing support or missing published estimates are flagged separately from zero. The web tables contain modeled counts, not averages of percentages or medians. Sampling margins use a weighted root-sum-of-squares approximation; they do not include geographic allocation error. A point on a footprint boundary counts once. Foreign populations and Island Areas without comparable ACS coverage are not imputed.

**Lookups.** `target` stores geometry once, 2020 totals and stable station/owner IDs. `station` has state, affiliation, licensee, facility, owner and application/site indexes. `target(kind,name COLLATE NOCASE,id)` supports prefix directory lookup; `profile(target_id,metric_id)` and `metric(id)` serve detail pages. `footprint_key` maps the text IDs to integer R\*Tree keys; `footprint_bounds` finds spatial candidates. Recheck the actual polygons for point or area coverage rather than treating an envelope as the footprint:

```sql
SELECT k.target_id FROM footprint_bounds AS b
JOIN footprint_key AS k USING (spatial_id)
WHERE b.west <= :longitude AND b.east >= :longitude
  AND b.south <= :latitude AND b.north >= :latitude;
```

The browser filters a small, prebuilt directory. The R\*Tree is for build/export and local spatial lookups, not a live Cloudflare dependency. `make check-web-db` checks the snapshot and the selected index plans without downloading new data. For raw source URLs and hashes see the build table or the site's `/sources.json`.

## Comparing demographic sources

Run `make census-sample` from `data/` for a District of Columbia pilot. It downloads the 2020 Census DHC P1 and 2020–2024 ACS B01003 variable dictionaries, the **2020 census blocks** and **2024 block groups**, and writes a source/size/SHA-256 manifest to `downloads/census-sample/`. With `CENSUS_API_KEY` set, it also requests DC population observations (and the ACS margin of error) as CSV with string GEOIDs. Use the manifest to identify the files fetched by a given run. This is a source comparison, not a WAMU coverage extract: WAMU crosses the DC border. It does not modify the FCC database.

The downloaded DC block shapefile itself includes `GEOID20`, `POP20`, and `HOUSING20`. In the sample its 6,012 blocks sum to 689,545 residents and 350,364 housing units; only 4,500 blocks report residents. That makes it a useful baseline without an API key. The 571 block-group shapes do **not** contain ACS demographics; join the estimate and MOE by GEOID. Preserve leading zeros.

See [Radio reach data choices](reports/Radio%20reach%20data%20choices.md) for geography, table choices, uncertainty and SQLite spatial options before choosing a national ingestion path.

## Relevant FCC Radio Service Codes

https://wiki.radioreference.com/index.php/FCC_Radio_Service_Codes

Broadcast/Mass Media 	FB 	FM Booster
Broadcast/Mass Media 	FD 	FM Digital
Broadcast/Mass Media 	FL 	Low Power FM
Broadcast/Mass Media 	FM 	FM Station
Broadcast/Mass Media 	FS 	FM Auxiliary Transmitter
Broadcast/Mass Media 	FX 	FM Translator 

[FCC Public Inspection Files and Countour Search](https://publicfiles.fcc.gov/)
[FCC API Documentation for Developers](https://publicfiles.fcc.gov/developer)
[LMS Public Database Files](https://enterpriseefiling.fcc.gov/dataentry/public/tv/lmsDatabase.html#)
[FM Service Contour Data Points](https://www.fcc.gov/media/radio/fm-service-contour-data-points)
[FCCdata.org](https://fccdata.org/?)
