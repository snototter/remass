"""Connection/Configuration"""
import npyscreen as nps
import os

from ..utilities import add_empty_row, full_class_name
from ..widgets import TitleCustomFilenameCombo, TitleCustomPassword
from ...config import RemassConfig


class StartUpForm(nps.ActionForm):
    OK_BUTTON_TEXT = 'Connect'
    CANCEL_BUTTON_BR_OFFSET = (2, 20)
    CANCEL_BUTTON_TEXT = "Cancel"

    def __init__(self, config: RemassConfig, *args, **kwargs):
        self._cfg = config
        super().__init__(*args, **kwargs)

    def activate(self):
        self.edit()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application
        })
        self.add(nps.Textfield, value="Options:", editable=False, color='STANDOUT')
        self._host = self.add(nps.TitleText, name="Host", relx=4,
                              value=self._cfg['connection']['host'])
        self._fallback_host = self.add(nps.TitleText, name="Fallback Host", relx=4,
                                       value=self._cfg['connection']['host_fallback'])
        self._keyfile = self.add(TitleCustomFilenameCombo, relx=4,
                                 name="Private Key", label=True,
                                 value=self._cfg['connection']['keyfile'],
                                 select_dir=False, must_exist=True)
        self._password = self.add(TitleCustomPassword, name="Password", relx=4,
                                  pwd_char = '*', value=self._cfg['connection']['password'])
        add_empty_row(self)
        self._cfg_text = self.add(nps.FixedText, value=self._get_cfg_text_label(),
                                  editable=False, color='STANDOUT')
        self._cfg_filename = self.add(TitleCustomFilenameCombo,
                                      name="Path", relx=4,
                                      value=self._cfg.config_filename, select_dir=False,
                                      label=True, must_exist=False,
                                      confirm_if_exists=True)
        self.add(nps.ButtonPress, name='[Save Configuration File]', relx=3,
                 when_pressed_function=self._save_config)

        # We want to focus/highlight the ok button (which is created inside
        # the base class' edit()). This can be done by:
        self.preserve_selected_widget = True
        self.editw = 10

    def on_cancel(self):
        self.exit_application()

    def exit_application(self, *args, **kwargs):
        self.parentApp.switchForm(None)  # Exits the application

    def on_ok(self):
        self._update_config()
        self.parentApp.setNextForm('MAIN')

    def _get_cfg_text_label(self):
        tlbl = "Configuration file"
        if self._cfg.config_filename is None or not os.path.exists(self._cfg.config_filename):
            tlbl += ' (does not exist)'
        tlbl += ':'
        return tlbl

    def _update_config(self):
        self._cfg['connection']['host'] = self._host.value
        self._cfg['connection']['keyfile'] = self._keyfile.value
        self._cfg['connection']['password'] = self._password.value
        self._cfg['connection']['host_fallback'] = self._fallback_host.value

    def _save_config(self):
        fname = self._cfg_filename.value
        if fname is None:
            nps.notify_confirm('You must select a valid configuration file path!',
                               title='Error', form_color='CAUTION', editw=1)
            return
        self._update_config()
        try:
            self._cfg.save(fname)
            nps.notify_confirm(f'Configuration has been saved to:\n{fname}',
                               title='Success', editw=1)
            self._cfg_text.value = self._get_cfg_text_label()
            self._cfg_text.update()
        except (PermissionError, IOError) as e:
            nps.notify_confirm("Cannot save configuration.\n"
                               "----------------------------------------\n"
                               f"Exception ({full_class_name(e)}):\n{e}",
                               title='Error', form_color='CAUTION', editw=1)
