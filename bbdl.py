#!/bin/env python3

from urllib.parse import urlparse, urljoin
import bs4 as BeautifulSoup
import requests
import logging
import argparse
import os
import time
from typing import Any
import json


logger = logging.getLogger(__name__)
logging.basicConfig(encoding='utf-8', level=logging.INFO)


_BB_BASE_URL = "https://blubrry.com"
_PAGE_PARAM = "pi"
_EPISODE_TITLE_CLASS = "pr-title"


_OG_METADATA_PROPERTIES = frozenset([
    "title",
    "description",
    "url",
    "image",
])
_DATE_CLASS = "ep-date"


def extract_episode_metadata(soup: BeautifulSoup.BeautifulSoup) -> dict[str, Any]:
    metadata = {}

    for md_field in _OG_METADATA_PROPERTIES:
        elem = soup.find("meta", property="og:{}".format(md_field))
        if elem:
            if elem.has_attr("content"):
                metadata[md_field] = elem["content"].strip()
            else:
                logger.warning("metadata field missing content: %s", md_field)
        else:
            logger.debug("missing metadata field: %s", md_field)

    date_elem = soup.find("div", class_=_DATE_CLASS)
    if date_elem:
        child = date_elem.find("i")
        if child:
            metadata["date"] = child.get_text().strip()
        elif date_elem.get_text().strip():
            logger.warning("falling back to date element text")
            metadata["date"] = date_elem.get_text().strip()
        else:
            logger.warning("failed to find date metadata in date element")
    else:
        logger.warning("failed to find date element")

    return metadata


def file_name_from_url(url: str) -> str:
    parsed_url = urlparse(url)
    return os.path.basename(parsed_url.path)


def get_episode_page_urls(podcast_name: str, req_sess: requests.Session) -> set[str]:
    podcast_archive_url = urljoin(_BB_BASE_URL, "/".join([podcast_name, "archive"]))
    logger.info("retrieving episode pages. Archive URL: %s", podcast_archive_url)

    all_episode_page_urls = set()
    page = 0
    while True:
        soup: BeautifulSoup.BeautifulSoup = None

        with req_sess.get(url=podcast_archive_url, params={_PAGE_PARAM: page}) as r:
            r.raise_for_status()
            soup = BeautifulSoup.BeautifulSoup(r.content, features="html.parser")

        episode_anchors = soup.find_all("a", class_=_EPISODE_TITLE_CLASS)
        episode_page_urls = {a["href"] for a in episode_anchors}

        # empty page which means we are at the end
        if not episode_page_urls:
            logger.debug("found empty page: %d", page)
            break

        all_episode_page_urls.update(episode_page_urls)
        page += 1

    logger.debug(all_episode_page_urls)

    return all_episode_page_urls


def download_episode_from_episode_page(episode_page_url: str, output_dir: str, req_sess: requests.Session, overwrite: bool) -> bool:
    logger.info("checking episode page %s", episode_page_url)

    soup: BeautifulSoup.BeautifulSoup = None

    with req_sess.get(episode_page_url) as r:
        r.raise_for_status()
        soup = BeautifulSoup.BeautifulSoup(r.content, features="html.parser")

    download_anchors = soup.find_all("a", title="Download Episode")
    audio_urls = {a["href"] for a in download_anchors}

    if not audio_urls:
        logger.warning("found no audio download links")
        return
    elif len(audio_urls) > 1:
        logger.warning("found multiple audo links, downloading first found")

    logger.debug(audio_urls)
    audio_url = audio_urls.pop()

    audio_file_name = file_name_from_url(audio_url)
    if not audio_file_name:
        logger.error("failed to get file name from audio url: %s", audio_url)
        return
    
    audio_output_path = os.path.join(output_dir, audio_file_name)

    if overwrite or not os.path.exists(audio_output_path):
        logger.info("downloading %s to %s", audio_url, audio_output_path)
        r = req_sess.get(audio_url, timeout=(5, 20))
        r.raise_for_status()
        with open(audio_output_path, "wb") as f:
            f.write(r.content)

    
    metadata_output_path = f"{os.path.splitext(audio_output_path)[0]}-metadata.json"
    if overwrite or not os.path.exists(metadata_output_path):
        metadata = extract_episode_metadata(soup)
        if metadata:
            logger.info("writing metadata to %s", metadata_output_path)
            with open(metadata_output_path, "w") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        else:
            logger.info("no metadata found for %s", episode_page_url)


def main() -> int:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-p", "--podcast-name", help="name of the podcast to download", type=str)
    arg_parser.add_argument("-o", "--output-dir", help="path to save episode downloads", type=str)
    arg_parser.add_argument("--dl-pause", help="seconds to sleep between audio downloads", type=int, default=1)
    arg_parser.add_argument("--overwrite", help="overwrite existing files", action=argparse.BooleanOptionalAction, default=False)
    args = arg_parser.parse_args()

    podcast_name: str = args.podcast_name
    output_dir: str = args.output_dir
    dl_pause: int = args.dl_pause
    overwrite: bool = args.overwrite

    try:
        os.makedirs(name = output_dir, exist_ok=True)
        if not os.path.isdir(output_dir):
            logger.error("output dir is not a directory")
            return 1
    except Exception as e:
        logger.exception("failed to create output dir: %s", output_dir)
        return 1

    with requests.Session() as sess:
        try:
            episode_page_urls = get_episode_page_urls(podcast_name, sess)
        except Exception:
            logger.exception("failed to get episode pages")
            return 1

        episode_dl_count = 0
        for url in episode_page_urls:
            try:
                download_episode_from_episode_page(url, output_dir, sess, overwrite)
                episode_dl_count += 1
            except Exception:
                logger.exception("failed to download episode from page url: %s", url)

            time.sleep(dl_pause)        

    logger.info("Complete. Downloaded %d episodes", episode_dl_count)
    return 0


if __name__ == "__main__":
    quit(main())
