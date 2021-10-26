
import logging
from .config import *


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # print(config_filename())
    cfg = AppConfig()
    #cfg.save()
    #cfg.load()
    print(cfg)
    print(cfg['connection'])