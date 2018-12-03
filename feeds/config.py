import os
import configparser
from .exceptions import ConfigError

DEFAULT_CONFIG_PATH = "deploy.cfg"
ENV_CONFIG_PATH = "FEEDS_CONFIG"
ENV_CONFIG_BACKUP = "KB_DEPLOYMENT_CONFIG"
ENV_AUTH_TOKEN = "AUTH_TOKEN"

FEEDS_SECTION = "feeds"
SERVICE_SECTION = "services"

# feeds keys
KEY_DB_HOST = "db-host"
KEY_DB_PORT = "db-port"
KEY_DB_USER = "db-user"
KEY_DB_PW = "db-pw"
KEY_DB_NAME = "db-name"
KEY_DB_ENGINE = "db-engine"
KEY_GLOBAL_FEED = "global-feed"
KEY_DEBUG = "debug"
KEY_LIFESPAN = "lifespan"
KEY_AUTH_URL = "auth-url"
KEY_NJS_URL = "njs-url"
KEY_GROUPS_URL = "groups-url"
KEY_WS_URL = "workspace-url"

class FeedsConfig(object):
    """
    Loads a config set from the root deploy.cfg file. This should be in ini format.

    Keys of note are:
    """

    def __init__(self):
        # Look for the file. ENV_CONFIG_PATH > ENV_CONFIG_BACKUP > DEFAULT_CONFIG_PATH
        self.auth_token = os.environ.get(ENV_AUTH_TOKEN)
        if self.auth_token is None:
            raise RuntimeError("The AUTH_TOKEN environment variable must be set!")
        config_file = self._find_config_path()
        cfg = self._load_config(config_file)
        for s in [FEEDS_SECTION, SERVICE_SECTION]:
            if not cfg.has_section(s):
                raise ConfigError(
                    "Error parsing config file: section {} not found!".format(s)
                )

        self._load_feeds_section(cfg)
        self._load_services_section(cfg)

    def _load_feeds_section(self, cfg):
        self.db_engine = self._get_line(cfg, FEEDS_SECTION, KEY_DB_ENGINE)
        self.db_host = self._get_line(cfg, FEEDS_SECTION, KEY_DB_HOST)
        self.db_port = self._get_line(cfg, FEEDS_SECTION, KEY_DB_PORT)
        try:
            self.db_port = int(self.db_port)
        except ValueError:
            raise ConfigError("{} must be an int! Got {}".format(KEY_DB_PORT, self.db_port))
        self.db_user = self._get_line(cfg, FEEDS_SECTION, KEY_DB_USER, required=False)
        self.db_pw = self._get_line(cfg, FEEDS_SECTION, KEY_DB_PW, required=False)
        self.db_name = self._get_line(cfg, FEEDS_SECTION, KEY_DB_NAME, required=False)
        self.global_feed = self._get_line(cfg, FEEDS_SECTION, KEY_GLOBAL_FEED)
        self.lifespan = self._get_line(cfg, FEEDS_SECTION, KEY_LIFESPAN)
        try:
            self.lifespan = int(self._get_line(cfg, FEEDS_SECTION, KEY_LIFESPAN))
        except ValueError:
            raise ConfigError("{} must be an int! Got {}".format(KEY_LIFESPAN, self.lifespan))
        self.debug = self._get_line(cfg, FEEDS_SECTION, KEY_DEBUG, required=False)
        if not self.debug or self.debug.lower() != "true":
            self.debug = False
        else:
            self.debug = True
        self.auth_url = self._get_line(cfg, FEEDS_SECTION, KEY_AUTH_URL)
        self.njs_url = self._get_line(cfg, FEEDS_SECTION, KEY_NJS_URL)
        self.ws_url = self._get_line(cfg, FEEDS_SECTION, KEY_WS_URL)
        self.groups_url = self._get_line(cfg, FEEDS_SECTION, KEY_GROUPS_URL)

    def _load_services_section(self, cfg):
        self.uid_to_service = dict()
        serv_to_id = dict(cfg[SERVICE_SECTION])
        if len(serv_to_id) == 0:
            raise ConfigError("Error parsing config file: services section is empty!")
        for k in serv_to_id:
            self.uid_to_service[serv_to_id[k]] = k

    def _find_config_path(self):
        """
        A little helper to test whether a given file path, or one given by an
        environment variable, exists.
        """
        for env in [ENV_CONFIG_PATH, ENV_CONFIG_BACKUP]:
            env_path = os.environ.get(env)
            if env_path:
                if not os.path.isfile(env_path):
                    raise ConfigError(
                        "Environment variable {} is set to {}, "
                        "which is not a config file.".format(ENV_CONFIG_PATH, env_path)
                    )
                else:
                    return env_path
        if not os.path.isfile(DEFAULT_CONFIG_PATH):
            raise ConfigError(
                "Unable to find config file - can't start server. Either set the {} or {} "
                "environment variable to a path, or copy 'deploy.cfg.example' to "
                "'deploy.cfg'".format(ENV_CONFIG_PATH, ENV_CONFIG_BACKUP)
            )
        return DEFAULT_CONFIG_PATH

    def _load_config(self, cfg_file):
        config = configparser.ConfigParser()
        with open(cfg_file, "r") as cfg:
            try:
                config.read_file(cfg)
            except configparser.Error as e:
                raise ConfigError("Error parsing config file {}: {}".format(cfg_file, e))
        return config

    def _get_line(self, config, section, key, required=True):
        """
        A little wrapper that raises a ConfigError if a required key isn't present.
        """
        val = None
        try:
            val = config.get(section, key)
        except configparser.NoOptionError:
            if required:
                raise ConfigError("Required option {} not found in config".format(key))
        if not val and required:
            raise ConfigError("Required option {} has no value!".format(key))
        return val


__config = None


def get_config(from_disk=False):
    global __config
    if not __config:
        __config = FeedsConfig()
    return __config
