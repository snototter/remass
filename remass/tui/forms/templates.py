"""Screen Customization"""
import npyscreen as nps
import os

from ..utilities import add_empty_row
from ...tablet import RAConnection
from ...config import RAConfig


class TemplateManagementForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        local_tpls = [f for f in os.listdir(self._cfg.template_dir) if f.lower().endswith('.svg')]
        lbl = f'SVG templates available for export: {len(local_tpls)}'
        self.add(nps.Textfield, value=lbl, editable=False, color='STANDOUT')
        self.btn_load = self.add(nps.ButtonPress, name='[Load Templates From Tablet]', relx=3,
                                 when_pressed_function=self._load_templates)
        add_empty_row(self)

    def _load_templates(self, *args, **kwargs):
        self._connection.download_templates(self._cfg.template_dir)
        nps.notify_confirm(f"Templates have been downloaded to\n{self._cfg.template_dir}",
                           title='Info', form_color='STANDOUT', editw=1)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()
