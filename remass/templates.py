import json
import os
import shutil
import tempfile
from pathlib import PurePosixPath
from typing import Dict, List
from .config import RemassConfig, latest_backup_filename, next_backup_filename
from .tablet import TabletConnection


RM_TEMPLATE_PATH = '/usr/share/remarkable/templates'


RM_TEMPLATE_JSON_PATH = '/usr/share/remarkable/templates/templates.json'


def template_name(tpl: dict) -> str:
    """Returns a displayable name for the given template configuration"""
    if 'landscape' in tpl:
        return tpl['name'] + (' Landscape' if tpl['landscape'] else ' Portrait')
    return tpl['name']


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
    def __init__(self, cfg: RemassConfig, connection: TabletConnection):
        self._cfg = cfg
        self._connection = connection
        self.local_template_config = None

    def load_remote_templates(self):
        """Loads the template configuration from the tablet."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download the tablet's templates.json
            temp_tpljson = os.path.join(temp_dir, 'templates.json')
            self._connection.download_file(RM_TEMPLATE_JSON_PATH, temp_tpljson)
            # Load the tablet's templates.json
            with open(temp_tpljson, 'r') as jf:
                tablet_config = json.load(jf)
                return tablet_config['templates']

    def load_backedup_templates(self):
        """Loads the templates from the latest backed up 'templates.json' file."""
        tpl_json = latest_backup_filename('templates.json', self._cfg.template_backup_dir)
        if tpl_json is None:
            return list()
        with open(tpl_json, 'r') as jf:
            tcfg = json.load(jf)
            return tcfg['templates']

    def load_uploadable_templates(self):
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

    def synchronize(self, templates_to_add: List[Dict] = list(), replace_templates: bool = False,
                    templates_to_disable: list = list(), backup_template_json: bool = True):
        """
        :templates_to_add: list of rM template configurations (check the
                           tablet's "templates.json" file) to be uploaded to
                           the device
        :replace_templates: if a "templates_to_add" entry already exists, we
                            will replace/overwrite it only if the flag is True
        :templates_to_disable: list of rM template configurations to be disabled,
                               i.e. only the configuration will be removed from
                               templates.json - the corresponding SVG & PNG files
                               will NOT be deleted from the tablet
        :backup_template_json: if True, a backup of the tablet's original templates.json
                               file will be stored in our local app directory
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
            if backup_template_json:
                # Store the downloaded templates.json into the remass backup
                # folder, in case we need/want to restore it later on
                bfn = next_backup_filename('templates.json', self._cfg.template_backup_dir)
                shutil.copyfile(temp_tpljson, bfn)

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
                            tablet_config['templates'] = [e for e in tablet_config['templates'] if not _equal_template(tpl, e)]
                            tablet_config['templates'].append(tpl)
                            add = True
                    else:
                        tablet_config['templates'].append(tpl)
                        add = True
                    if add:
                        upload_files.append((src_svg, dst_svg))
                        upload_files.append((src_png, dst_png))
                        # Also copy the SVG file to our local backup location,
                        # so it is available for future exports:
                        shutil.copyfile(src_svg,
                                        os.path.join(self._cfg.template_backup_dir, tpl['filename'] + '.svg'))

            # Remove the disabled templates from the tablet's config
            for tpl in templates_to_disable:
                tablet_config['templates'] = [e for e in tablet_config['templates'] if not _equal_template(tpl, e)]
            # Save modified templates.json (locally)
            with open(temp_tpljson, 'w') as jf:
                json.dump(tablet_config, jf, indent=2)
            upload_files.append((temp_tpljson, RM_TEMPLATE_JSON_PATH))
            # Upload files
            for src, dst in upload_files:
                self._connection.upload_file(src, dst)
            # Restart tablet UI to force reloading the changed templates
            self._connection.restart_ui()
