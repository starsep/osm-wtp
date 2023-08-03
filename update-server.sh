#!/usr/bin/env bash
set -eu
date=$(/bin/date '+%Y%m%d')
mkdir -p cache
touch cache/dateOfLastRun
if [[ "$(cat cache/dateOfLastRun)" != "$date" ]]; then
    rm -rf cache/scraper
fi
./updateGTFSWarsaw.sh
git clone https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com/starsep/osm-wtp/ --depth 1
rm -rf cache/overpass
python main.py
(
    cd osm-wtp || exit 1
    git config user.name "OSM WTP Bot"
    git config user.email "<>"
    git add -- *.html
    git commit -m "Update $date"
    git push origin main
)
echo "$date" > cache/dateOfLastRun
