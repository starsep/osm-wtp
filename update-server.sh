#!/usr/bin/env bash
set -eu
date=$(/bin/date '+%Y%m%d')
./updateGTFSWarsaw.sh
git clone https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com/starsep/osm-wtp/ --depth 1 --branch gh-pages
uv run --no-dev --no-progress python main.py
(
    cd osm-wtp || exit 1
    git config user.name "OSM WTP Bot"
    git config user.email "<>"
    git add -- *.html
    git commit -m "Update $date"
    git push origin gh-pages
)
