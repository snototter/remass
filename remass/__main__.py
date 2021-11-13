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
    # from .tablet import SplashScreenUtil
    # print(SplashScreenUtil.tablet_filename('foo'))
    # print(SplashScreenUtil.tablet_filename(('frobnaten', 'bar')))
    # RATui(args).run()

    # from .tablet import validate_custom_screen
    # print(validate_custom_screen('test-std.png'))
    # print(validate_custom_screen('test-alpha.png'))

    cfg = RAConfig(args)
    connection = RAConnection(cfg)
    connection.open()
    from .templates import TemplateOrganizer
    org = TemplateOrganizer(cfg, connection)
    ctpls = org.custom_templates
    org.synchronize([ctpls[1]], True, [ctpls[0]])

    # # connection.download_file('/home/root/log.txt', 'test-download.txt')
    # connection.upload_file('test.txt', '/home/root/uploaded.txt')
    # connection.close()
    # # connection.get_filesystem()
