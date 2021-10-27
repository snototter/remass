import npyscreen
import logging

from .tablet import RAConnection
from .config import RAConfig

class StartUpForm(npyscreen.ActionForm):
    # BLANK_COLUMNS_RIGHT= 2
    # BLANK_LINES_BASE = 2
    OK_BUTTON_TEXT = 'Connect'
    # OK_BUTTON_BR_OFFSET = (2,6)
    # OKBUTTON_TYPE = button.MiniButton
    # DEFAULT_X_OFFSET = 2
    CANCEL_BUTTON_BR_OFFSET = (2, 20)
    CANCEL_BUTTON_TEXT = "Cancel"

    def __init__(self, config, *args, **kwargs):
        self._cfg = config
        super().__init__(*args, **kwargs)

    def activate(self):
        self.edit()

    def create(self):
        self._host = self.add(npyscreen.TitleText, name="Host",
                              value=self._cfg['connection']['host'])
        self._keyfile = self.add(npyscreen.TitleFilenameCombo,
                                 name="Private Key", label=True,
                                 value=self._cfg['connection']['keyfile'],
                                 select_dir=False, must_exist=True)
        self._password = self.add(npyscreen.TitlePassword, name="Password",
                                  value=self._cfg['connection']['password'])

    def on_cancel(self):
        self.parentApp.switchForm(None)  # Exits the application

    def on_ok(self):
        # Adjust configuration if needed
        self._cfg['connection']['host'] = self._host.value
        self._cfg['connection']['keyfile'] = self._keyfile.value
        self._cfg['connection']['password'] = self._password.value
        self.parentApp.setNextForm('MAIN')


class MainForm(npyscreen.Form):
    def __init__(self, config, *args, **kwargs):
        self._cfg = config
        super().__init__(*args, **kwargs)

    def create(self):
        self.hello = self.add(npyscreen.TitleFixedText, name="Main form!", value=f"this is the main form {self._cfg['connection']['host']}")
        #TODO edit, exit
        #add menu (ctrl+x)
        # submenues: templates, pdf export, change screens


class RATui(npyscreen.NPSAppManaged):
    STARTING_FORM = 'CONNECT'

    def __init__(self):
        self._cfg = RAConfig()
        self._connection = RAConnection(self._cfg)
        super().__init__()

    def onStart(self):
        self.addForm('CONNECT', StartUpForm, self._cfg, name='Connection Options')
        # Since the user may change configuration parameters within 'CONNECT',
        # the following forms should be initialized upon every invocation (to
        # inject the up-to-date parametrization)
        self.addFormClass('MAIN', MainForm, self._cfg, name='Main')
