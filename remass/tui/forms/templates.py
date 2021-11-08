"""Screen Customization"""
import npyscreen as nps

from ..utilities import add_empty_row
from ...tablet import RAConnection
from ...config import RAConfig


class TemplateManagementForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cfg = cfg
        self._connection = connection

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        self.add(nps.Textfield, value="TODO:", editable=False, color='STANDOUT')

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()
