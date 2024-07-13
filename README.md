# osm-wtp
Compares public transportation data in Warsaw with OpenStreetMap routes.

Results hosted at https://starsep.com/osm-wtp/

## Docker
Docker for updating server.
You can use `--entrypoint "python main.py"` for development.

```
docker build -t osm-wtp .

docker run --rm \
    -v "$(pwd)/GTFS-Warsaw:/app/GTFS-Warsaw" \
    -v "$(pwd)/cache:/app/cache" \
    --env GITHUB_USERNAME=example \
    --env GITHUB_TOKEN=12345 \
    -t osm-wtp
```
