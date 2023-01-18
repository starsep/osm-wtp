#!/usr/bin/env bash
date=$(/bin/date '+%Y%m%d')
touch .dateOfLastRun
if [[ "$(cat .dateOfLastRun)" != "$date" ]]; then
    rm -rf cache/wtp
fi
git pull
rm -rf cache/overpass
source .venv/bin/activate
pip install -r requirements.txt
python main.py
cd ../osm-wtp || return
git config user.name "OSM WTP Bot"
git config user.email "<>"
mv index.html index2.html
git pull
mv index2.html index.html
git add index.html
git commit -m "Update $date"
git push origin main
cd ../osm-wtp-compare || return
echo "$date" > .dateOfLastRun
