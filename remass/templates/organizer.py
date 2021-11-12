import json
import os
from ..config import RAConfig, latest_backup_filename
from ..tablet import RAConnection


RM_TEMPLATE_PATH = '/usr/share/remarkable/templates'


class TemplateOrganizer(object):
    def __init__(self, cfg: RAConfig, connection: RAConnection):
        self._cfg = cfg
        self._connection = connection
        self.local_template_config = None

    @property
    def backedup_templates(self):
    # def load_template_backups(self):
        tpl_json = latest_backup_filename('templates.json', self._cfg.template_backup_dir)
        if tpl_json is None:
            return list()
        with open(tpl_json, 'r') as jf:
            tcfg = json.load(jf)
            return tcfg['templates']

    @property
    def custom_templates(self):
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

    @property
    def custom_template_names(self):
        tpls = self.custom_templates
        def _tname(tpl):
            return tpl['name'] + (' Landscape' if tpl['landscape'] else ' Portrait')
        return sorted(list(set([_tname(tpl) for tpl in tpls])))
        #TODO we must keep a list (since nps will discard everything except for the display name and the index...)
