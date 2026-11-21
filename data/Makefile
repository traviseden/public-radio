.PHONY: help db stations stations-force validate census-sample

help:
	@echo "Targets:"
	@echo "  make db               Build public_radio_facility_data.sqlite from tables/*.dat"
	@echo "  make census-sample    Fetch DC boundaries and Census dictionaries for both demographic options"
	@echo "  make stations         Generate stations/<CALLSIGN>.yaml (skips existing files)"
	@echo "  make stations-force   Regenerate all station files, overwriting existing ones"
	@echo "  make validate         Validate station YAML files (all, or FILES=\"stations/WBHM.yaml ...\")"
	@echo "  make launch-datasette Launch a local datasette instance"

# create_db.py uses paths relative to this directory, so run make from here.
# uv creates .venv and installs dependencies from pyproject.toml on first run.
db:
	uv run scripts/create_db.py

census-sample:
	uv run scripts/census_sample.py

stations:
	uv run scripts/generate_stations.py

stations-force:
	uv run scripts/generate_stations.py --force

# Untouched stubs pass; partly filled files must satisfy every rule.
# Pass FILES to check only specific ones.
validate:
	uv run scripts/validate_stations.py $(FILES)

launch-datasette:
	uv run datasette -i public_radio_facility_data.sqlite --metadata metadata.yaml --setting sql_time_limit_ms 20000 --setting truncate_cells_html 80
