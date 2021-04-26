import logging
import pathlib

import pkg_resources
from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-Jamendo").version

logger = logging.getLogger(__name__)


class Extension(ext.Extension):

    dist_name = "Mopidy-Jamendo"
    ext_name = "jamendo"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["client_id"] = config.Secret()
        return schema

    def setup(self, registry):
        from .jamendo import JamendoBackend

        registry.add("backend", JamendoBackend)
