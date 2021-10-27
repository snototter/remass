import argparse
import logging
from .config import RAConfig
from .tablet import RAConnection
# from .tui import RATui



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    cfg = RAConfig()
    #cfg.save()
    #cfg.load()
    print(cfg)
    # print(f'Loaded from disk? {cfg.loaded_from_disk}')

    connection = RAConnection(cfg)
    connection.open()

    # RemAssTui().run()
