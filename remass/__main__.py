import argparse
import logging
from .config import RAConfig
from .tablet import RAConnection
from .tui import RATui

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg', type=str, metavar='PATH', default=None,
                        help='Specify a custom configuration file.')
    parser.add_argument('--dir', type=str, metavar='PATH', default=None,
                        help='Specify a custom application directory to store downloaded files, templates, etc.')
    return parser.parse_args()


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    args = parse_args()
    RATui(args).run()

    # cfg = RAConfig(args)
    # connection = RAConnection(cfg)
    # connection.open()
    # connection.get_filesystem()
    # connection.render_document('65fa8e6b-3b26-4837-890a-096d35851cd9')
    # # connection.render_document('da845f0b-af7f-4b59-b760-f41b30d45af4')
