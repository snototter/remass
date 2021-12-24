import argparse
import logging
from .tui import RATui
from .tablet import TabletConnection
from .config import RemassConfig


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg', type=str, metavar='PATH', default=None,
                        help='Specify a custom configuration file.')
    parser.add_argument('--dir', type=str, metavar='PATH', default=None,
                        help='Specify a custom application directory to store downloaded files, templates, etc.')
    # Dev options:
    parser.add_argument('--list', action='store_true', default=False,
                        help='List all notebooks.')
    parser.add_argument('--search', action='store', default=None, type=str, metavar='SEARCH',
                        help='List all notebooks which contain "SEARCH" in their name.')
    parser.add_argument('--export', action='store', default=None, type=str, metavar='UUID',
                        help='Export the corresponding notebook.')
    
    return parser.parse_args()


def list_files(args, search: str=None):
    cfg = RemassConfig(args)
    connection = TabletConnection(cfg)
    connection.open()
    _, _, dirent_dict = connection.get_filesystem()
    if search is None:
        print('Notebooks on device:')
        print('--------------------')
        for uuid in dirent_dict:
            print(f'{uuid} {dirent_dict[uuid].visible_name}')
    else:
        print(f'Files which contain: "{search}":')
        found = False
        for uuid in dirent_dict:
            if search in dirent_dict[uuid].visible_name:
                print(f'{uuid} {dirent_dict[uuid].visible_name}')
                found = True
        if not found:
            print('--> No such file found')
    connection.close()


def export(args):
    cfg = RemassConfig(args)
    connection = TabletConnection(cfg)
    connection.open()
    connection.render_document_by_uuid(args.export, 'dev-export-test.pdf', None,
                                       template_alpha=0.4,
                                       expand_pages=True,
                                       #  only_annotated=self.rendering_only_annotated.value
                                        # page_selection=pages,
                                       template_path=cfg.template_backup_dir)
    connection.close()

if __name__ == '__main__':
    # Verbose logging heavily interferes with npyscreen. Thus, restrict it to
    # warning/error levels only.
    logging.basicConfig(level=logging.WARNING)
    args = parse_args()
    if args.list or args.search is not None:
        list_files(args, args.search)
    elif args.export is not None:
        export(args)
