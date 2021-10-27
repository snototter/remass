import argparse
import logging
from .config import *
from .tui import RemAssTui


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # print(config_filename())
    cfg = AppConfig()
    #cfg.save()
    #cfg.load()
    print(cfg)
    print(cfg['connection'])
    print(f'Loaded from disk? {cfg.loaded_from_disk}')
    # RemAssTui().run()
