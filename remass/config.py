"""Application configuration."""

import logging
from typing import Tuple
import appdirs
import os
import toml
import stat


APP_NAME = 'remass'


def config_filename(filename: str = None) -> Tuple[str, str]:
    """Returns the config folder + filename."""
    if filename is None:
         return (appdirs.user_config_dir(appname=APP_NAME), 'remass.toml')
    return os.path.split(filename)


def check_permissions(filename: str = None) -> None:
    """Check if the configuration file is readable by other users."""
    dname, fname = config_filename(filename)
    ffn = os.path.join(dname, fname)
    # Readable or writeable by others?
    stm = os.stat(ffn).st_mode
    if (stm & stat.S_IROTH) or (stm & stat.S_IWOTH):
        fperm = str(oct(stm)[4:])

        if fperm.startswith("0") and len(fperm) == 4:
            fperm = fperm[1:]
        logging.getLogger(__name__).warn(f"Configuration file '{ffn}' is readable "
                                         "by other users (permissions: {fperm}). "
                                         "You are strongly encouraged to adjust "
                                         "the file permissions: `chmod 600 {ffn}`")


def merge_dicts(a: dict, b: dict, path: str = None):
    """Merges dict 'b' into dict 'a' (modifies 'a')."""
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dicts(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:  # Same value, keep 'a'
                pass
            else:
                if a[key] is None:
                    a[key] = b[key]  # Replace None in 'a'
                elif b[key] is None:
                    pass  # Keep 'a' value
                else:  # Actual value mismatch
                    raise ValueError("Merge conflict at %s" % '.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a


class RAConfig(object):
    def __init__(self):
        # Initialize with defaults
        self.loaded_from_disk = False
        self._cfg = {
            'connection': {
                'host': '10.11.99.1',
                'user': 'root',
                'keyfile': None,
                'password': None,
                'timeout': 2,
                'port': 22
            }
        }
        # Try to load from default config location:
        self.load()

    def load(self, filename: str = None):
        dname, fname = config_filename(filename)
        ffn = os.path.join(dname, fname)
        if os.path.exists(ffn):
            # Ensure file can only be accessed by the current user
            check_permissions(filename)
            with open(ffn, 'r') as fp:
                uc = toml.load(fp)
                self._cfg = merge_dicts(self._cfg, uc)
                self.loaded_from_disk = True
                logging.getLogger(__name__).info(f"Loaded configuration from '{ffn}'")

    def save(self, filename: str = None):
        dname, fname = config_filename(filename)
        if not os.path.exists(dname):
            logging.getLogger(__name__).info(f"Creating directory structure '{dname}'")
            os.makedirs(dname)
        ffn = os.path.join(dname, fname)
        with open(ffn, 'w') as fp:
            toml.dump(self._cfg, fp)
            logging.getLogger(__name__).info(f"Saved configuration to '{ffn}'")
        os.chmod(ffn, 0o600)

    def __getitem__(self, key):
        return self._cfg[key]

    def __setitem__(self, key, value):
        self._cfg[key] = value

    def __repr__(self):
        return self._cfg.__repr__()
