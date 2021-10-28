import argparse
import logging
from .config import RAConfig
from .tablet import RAConnection
from .tui import RATui

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg', type=str, metavar='PATH', default=None,
                        help='Specify a custom configuration file.')
    return parser.parse_args()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    # cfg = RAConfig()
    # #cfg.save()
    # #cfg.load()
    # print(cfg)
    # print(f'Loaded from disk? {cfg.loaded_from_disk}')

    # connection = RAConnection(cfg)
    # connection.open()
    # print(connection.get_tablet_version())
    # connection.close()

    #TODO change log level to warning when using the TUI!
    #TODO argparse: config file & app dir (override default locations)
    RATui(args).run()
