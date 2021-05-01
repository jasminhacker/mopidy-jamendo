# structure largely adapted from Mopidy-Soundcloud
# https://github.com/mopidy/mopidy-soundcloud/

import logging
from contextlib import closing
from typing import List, Optional

import cachetools.func
import pykka
import requests
from mopidy import backend, httpclient
from mopidy.audio import Audio
from mopidy.models import Album, Artist, Track
from requests import HTTPError

import mopidy_jamendo

logger = logging.getLogger(__name__)


def get_requests_session(
    proxy_config: dict, user_agent: str
) -> requests.Session:
    proxy = httpclient.format_proxy(proxy_config)
    full_user_agent = httpclient.format_user_agent(user_agent)

    session = requests.Session()
    session.proxies.update({"http": proxy, "https": proxy})
    session.headers.update({"user-agent": full_user_agent})

    return session


def parse_track(data: dict) -> Optional[Track]:
    if not data:
        return None

    track_kwargs = {}
    artist_kwargs = {}
    album_kwargs = {}

    if "name" in data:
        track_kwargs["name"] = data["name"]
    if "artist_name" in data:
        artist_kwargs["name"] = data["artist_name"]
    album_kwargs["name"] = "Jamendo"

    if "releasedate" in data:
        track_kwargs["date"] = data["releasedate"]

    track_kwargs["uri"] = data["audio"]

    track_kwargs["length"] = int(data.get("duration", 0) * 1000)
    track_kwargs["comment"] = data.get("shareurl", "")

    if artist_kwargs:
        track_kwargs["artists"] = [Artist(**artist_kwargs)]

    if album_kwargs:
        track_kwargs["album"] = Album(**album_kwargs)

    return Track(**track_kwargs)


class JamendoClient:
    def __init__(self, config: dict):
        super().__init__()
        self.http_client = get_requests_session(
            proxy_config=config["proxy"],
            user_agent=(
                f"{mopidy_jamendo.Extension.dist_name}/"
                f"{mopidy_jamendo.__version__}"
            ),
        )
        self.client_id = config["jamendo"]["client_id"]

    def _get(self, url: str, params: dict = None) -> dict:
        url = f"https://api.jamendo.com/v3.0/{url}"
        if not params:
            params = {}
        params["client_id"] = self.client_id
        try:
            with closing(self.http_client.get(url, params=params)) as res:
                logger.debug(f"Requested {res.url}")
                res.raise_for_status()
                return res.json()
        except Exception as e:
            if isinstance(e, HTTPError) and e.response.status_code == 401:
                logger.error(
                    'Invalid "client_id" used for Jamendo authentication!'
                )
            else:
                logger.error(f"Jamendo API request failed: {e}")
        return {}

    @cachetools.func.ttl_cache(ttl=3600)
    def get_track(self, track_id: str) -> Optional[Track]:
        logger.debug(f"Getting info for track with ID {track_id}")
        try:
            result = self._get("tracks/", params={"id": track_id})["results"][0]
        except (KeyError, IndexError):
            logger.warning(f"No results for track {track_id}")
            return None
        track = parse_track(result)
        return track


class JamendoPlaybackProvider(backend.PlaybackProvider):
    def translate_uri(self, uri: str) -> Optional[str]:
        if "jamendo:track:" in uri:
            uri = uri[len("jamendo:track:") :]
            track = self.backend.remote.get_track(uri)
            if track is None:
                return None
            return track.uri
        return None


class JamendoLibraryProvider(backend.LibraryProvider):
    def lookup(self, uri: str) -> List[Optional[Track]]:
        if "jamendo:track:" in uri:
            uri = uri[len("jamendo:track:") :]
            return [self.backend.remote.get_track(uri)]
        return [None]


class JamendoBackend(pykka.ThreadingActor, backend.Backend):
    def __init__(self, config: dict, audio: Audio):
        super(JamendoBackend, self).__init__()

        self.audio = audio

        self.config = config
        self.remote = JamendoClient(config)
        self.library = JamendoLibraryProvider(backend=self)
        self.playback = JamendoPlaybackProvider(audio=audio, backend=self)

        self.uri_schemes = ["jamendo"]
