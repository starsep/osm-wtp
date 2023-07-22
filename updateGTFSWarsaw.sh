#!/usr/bin/env bash
set -eu
cd GTFS-Warsaw || exit 1
OLD_HASH=$(md5sum warsaw.zip)
wget -c -O warsaw.zip https://mkuran.pl/gtfs/warsaw.zip
if [[ $(md5sum warsaw.zip) != "$OLD_HASH" ]]; then
    unzip -o warsaw.zip
    chmod 0644 -- *
fi
