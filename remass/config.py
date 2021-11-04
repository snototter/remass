"""Application configuration."""

import logging
from typing import Tuple
import appdirs
import os
import toml
import stat
from pathlib import Path
import platform

APP_NAME = 'remass'


def abbreviate_user(path: str):
    """Tries to abbreviate the home dir within the given path"""
    try:
        f = Path(path)
        home = '%USERPROFILE%' if platform.system() == 'Windows' else '~'
        return str(home / f.relative_to(Path.home()))
    except ValueError:
        return path


def config_filename(filename: str = None) -> Tuple[str, str]:
    """Returns the config folder + filename."""
    if filename is None:
         return (appdirs.user_config_dir(appname=APP_NAME), 'remass.toml')
    return os.path.split(filename)


def setup_app_dir(folder: str) -> str:
    """Ensures that the application's data directory is set up properly.
    If the given 'folder' is None, we use the user's default application data
    directory.
    :return: path to the application directory.
    """
    if folder is None:
        folder = appdirs.user_data_dir(appname=APP_NAME)
    subfolders = [
        os.path.join(folder, 'exports'),
        os.path.join(folder, 'templates'),
        os.path.join(folder, 'screens')]
    for sf in subfolders:
        if not os.path.exists(sf):
            os.makedirs(sf)
    return folder


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


def merge_configs(a: dict, b: dict, path: str = None) -> dict:
    """
    Merges config dict 'b' into dict 'a'. Note that 'a' will be modified and
    entries in 'b' override entries in 'a'.
    """
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_configs(a[key], b[key], path + [str(key)])
            else:
                a[key] = b[key]  # Replace 'a' entry by 'b' counterpart
        else:
            a[key] = b[key]
    return a


class RAConfig(object):
    def __init__(self, args=None):
        #TODO document in README
        self._cfg = {
            'connection': {
                'host': '10.11.99.1',
                'host_fallback': None,  # If connection to 'host' times out, we try to connect to 'host_fallback' if set.
                'user': 'root', # At the time of writing, there is only the root account available on the reMarkable
                'keyfile': None,  # Path to the SSH private key
                'password': None,  # If a keyfile is specified, pwd will be used to unlock it (otherwise, it will be used as the root's pwd)
                'timeout': 1,  # SSH connection timeout in seconds
                'port': 22  # If we ever need/want to adjust the connection port
            }
        }
        # Try to load from default (or overriden) config location:
        self.config_filename = None if args is None else args.cfg
        # Ensure we have the proper folder structure in our app's data directory
        self.load(self.config_filename)
        self.app_dir = setup_app_dir(None if args is None else args.dir)
    
    @property
    def export_dir(self):
        return os.path.join(self.app_dir, 'exports')
    
    @property
    def template_dir(self):
        return os.path.join(self.app_dir, 'templates')

    @property
    def screen_dir(self):
        return os.path.join(self.app_dir, 'screens')

    def load(self, filename: str = None) -> None:
        dname, fname = config_filename(filename)
        ffn = os.path.join(dname, fname)
        if os.path.exists(ffn):
            # Ensure file can only be accessed by the current user
            check_permissions(filename)
            with open(ffn, 'r') as fp:
                uc = toml.load(fp)
                self._cfg = merge_configs(self._cfg, uc)
                self.config_filename = ffn
                logging.getLogger(__name__).info(f"Loaded configuration from '{ffn}'")

    def save(self, filename: str = None) -> None:
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
