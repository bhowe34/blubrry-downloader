## Blubrry-downloader

A very brittle script that downloads all podcast episodes and some metadata from blubrry.com.
This will break if they redesign their site. If you want something better get an API key.

### How to run

```bash
python -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
./bbdl.py -p my-favorite-podcast -o ./output/my-favorite-podcast
```

This will download all the episodes of the my-favorite-podcast podcast and save them to `./output/my-favorite-podcast` along with some metadata for each episode.
