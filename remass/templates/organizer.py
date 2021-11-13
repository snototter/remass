import json
import os
import shutil
import tempfile
from pathlib import PurePosixPath
from typing import Dict, List
from ..config import RAConfig, latest_backup_filename, next_backup_filename
from ..tablet import RAConnection


RM_TEMPLATE_PATH = '/usr/share/remarkable/templates'
RM_TEMPLATE_JSON_PATH = '/usr/share/remarkable/templates/templates.json'

def template_name(tpl: dict) -> str:
    """Returns a displayable name for the given template configuration"""
    return tpl['name'] + (' Landscape' if tpl['landscape'] else ' Portrait')


def _exists_custom_template(custom: dict, tablet_config: dict) -> bool:
    """Checks if the given template entry already exists within the
    tablet's configuration."""
    for t in tablet_config['templates']:
        if _equal_template(custom, t):
            return True
    return False


def _equal_template(tpl_a: dict, tpl_b: dict) -> bool:
    """Checks if the two template configs are the same"""
    if tpl_a['name'] == tpl_b['name']:
        al = tpl_a['landscape'] if 'landscape' in tpl_a else False
        bl = tpl_b['landscape'] if 'landscape' in tpl_b else False
        return al == bl
    return False


class TemplateOrganizer(object):
    def __init__(self, cfg: RAConfig, connection: RAConnection):
        self._cfg = cfg
        self._connection = connection
        self.local_template_config = None

    def load_backedup_templates(self):
        """Loads the templates from the latest backed up 'templates.json' file."""
        tpl_json = latest_backup_filename('templates.json', self._cfg.template_backup_dir)
        if tpl_json is None:
            return list()
        with open(tpl_json, 'r') as jf:
            tcfg = json.load(jf)
            return tcfg['templates']

    def load_custom_templates(self):
        """Loads all custom templates which are uploadable, i.e. there must be:
        * a "name".inc.json configuration
        * a "name".svg
        * a "name".png
        """
        tpls = list()
        filenames = os.listdir(self._cfg.template_dir)
        for fn in filenames:
            if not fn.lower().endswith('.inc.json'):
                continue
            with open(os.path.join(self._cfg.template_dir, fn), 'r') as jf:
                tcfg = json.load(jf)
                for e in tcfg:
                    svg_fn = os.path.join(self._cfg.template_dir, e['filename'] + '.svg')
                    png_fn = os.path.join(self._cfg.template_dir, e['filename'] + '.png')
                    if os.path.exists(svg_fn) and os.path.exists(png_fn):
                        tpls.append(e)
        return tpls

    def synchronize(self, templates_to_add: List[Dict] = list(), replace_templates: bool = False, templates_to_disable: list = list()):
        """
        :templates_to_add: contains the rm template configuration (check the
                           tablet's "templates.json" file)
        :replace_templates: if a "templates_to_add" entry already exists, we
                            will replace/overwrite it only if the flag is True
        :templates_to_disable: TODO
        The corresponding files (SVG and PNG) on the tablet WILL NOT be deleted
        """
        if len(templates_to_add) == 0 and len(templates_to_disable) == 0:
            return
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download the tablet's templates.json
            temp_tpljson = os.path.join(temp_dir, 'templates.json')
            self._connection.download_file(RM_TEMPLATE_JSON_PATH, temp_tpljson)
            # Load the tablet's templates.json
            with open(temp_tpljson, 'r') as jf:
                tablet_config = json.load(jf)
                print(f'loaded {len(tablet_config["templates"])} tpls from tablet') #TODO remove

            # Collect files to upload and adjust the tablet's config for the
            # requested uploads:
            upload_files = list()
            for tpl in templates_to_add:
                # Sanity check: the local files must exist
                src_svg = os.path.join(self._cfg.template_dir, tpl['filename'] + '.svg')
                src_png = os.path.join(self._cfg.template_dir, tpl['filename'] + '.png')
                if os.path.exists(src_svg) and os.path.exists(src_png):
                    dst_svg = str(PurePosixPath(RM_TEMPLATE_PATH, tpl['filename'] + '.svg'))
                    dst_png = str(PurePosixPath(RM_TEMPLATE_PATH, tpl['filename'] + '.svg'))
                    add = False
                    # Update the tablet's config:
                    if _exists_custom_template(tpl, tablet_config):
                        # Do we want to overwrite (e.g. changing the icon or whatever)?
                        if replace_templates:
                            print(f'-- replacing "{template_name(tpl)}"') #TODO remove
                            tablet_config['templates'] = [e for e in tablet_config['templates'] if not _equal_template(tpl, e)]
                            tablet_config['templates'].append(tpl)
                            add = True
                    else:
                        print(f'-- adding "{template_name(tpl)}"') #TODO remove
                        tablet_config['templates'].append(tpl)
                        add = True
                    if add:
                        upload_files.append((src_svg, dst_svg))
                        upload_files.append((src_png, dst_png))

            # Remove the disabled templates from the tablet's config
            if len(templates_to_disable) > 0:
                # Store the downloaded templates.json into the remass backup
                # folder, in case we need/want to restore it later on
                #TODO copy tempfile to backup dir!
                bfn = next_backup_filename('templates.json', self._cfg.template_backup_dir)
                shutil.copyfile(temp_tpljson, bfn)
                # Remove the template configurations (we DON'T delete the files
                # from the tablet)
                for tpl in templates_to_disable:
                    print(f'-- disabling "{template_name(tpl)}"') #TODO remove
                    tablet_config['templates'] = [e for e in tablet_config['templates'] if not _equal_template(tpl, e)]
            print(f'replacing config by {len(tablet_config["templates"])} tpls') #TODO remove
            # Save modified templates.json (locally)
            with open(temp_tpljson, 'w') as jf:
                json.dump(tablet_config, jf, indent=2)
            upload_files.append((temp_tpljson, RM_TEMPLATE_JSON_PATH))
            # Upload files
            for src, dst in upload_files:
                print(f'Uploading {src} --> {dst}')
            #TODO backup templates also?
