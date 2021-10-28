import npyscreen as nps
import logging
import os

from .tablet import RAConnection
from .config import RAConfig, config_filename


def add_empty_row(form):
    form.add(nps.FixedText, value="", hidden=True)


class StartUpForm(nps.ActionForm):
    # BLANK_COLUMNS_RIGHT= 2
    # BLANK_LINES_BASE = 2
    OK_BUTTON_TEXT = 'Connect'
    # OK_BUTTON_BR_OFFSET = (2,6)
    # OKBUTTON_TYPE = button.MiniButton
    # DEFAULT_X_OFFSET = 2
    CANCEL_BUTTON_BR_OFFSET = (2, 20)
    CANCEL_BUTTON_TEXT = "Cancel"

    def __init__(self, config: RAConfig, *args, **kwargs):
        self._cfg = config
        super().__init__(*args, **kwargs)

    def activate(self):
        self.edit()

    def create(self):
        self._host = self.add(nps.TitleText, name="Host",
                              value=self._cfg['connection']['host'])
        self._keyfile = self.add(nps.TitleFilenameCombo,
                                 name="Private Key", label=True,
                                 value=self._cfg['connection']['keyfile'],
                                 select_dir=False, must_exist=True)
        self._password = self.add(nps.TitlePassword, name="Password",
                                  value=self._cfg['connection']['password'])
        
        add_empty_row(self)
        self._cfg_text = self.add(nps.FixedText, value=self._get_cfg_text_label(), editable=False)
        cfg_dname, cfg_fname = config_filename(self._cfg.loaded_from_disk)
        cfg_path = os.path.join(cfg_dname, cfg_fname)
        self._cfg_filename = self.add(nps.TitleFilenameCombo,
                                        name="Path",
                                        value=cfg_path, select_dir=False,
                                        label=True, must_exist=False,
                                        confirm_if_exists=True)
        self.add(nps.ButtonPress, name='Save Configuration File',
                 when_pressed_function=self._save_config)

        # We want to focus/highlight the ok button (which is created inside
        # the base class' edit())
        self.preserve_selected_widget = True
        self.editw = 8

    def on_cancel(self):
        self.parentApp.switchForm(None)  # Exits the application

    def on_ok(self):
        self._update_config()
        self.parentApp.setNextForm('MAIN')
    
    def _get_cfg_text_label(self):
        tlbl = "Configuration file"
        if self._cfg.loaded_from_disk is None:
            tlbl += ' (does not exist)'
        tlbl += ':'
        return tlbl
    
    def _update_config(self):
        # Adjust configuration if needed
        self._cfg['connection']['host'] = self._host.value
        self._cfg['connection']['keyfile'] = self._keyfile.value
        self._cfg['connection']['password'] = self._password.value

    def _save_config(self):
        fname = self._cfg_filename.value
        if fname is None:
            nps.notify_confirm('You must select a valid configuration file path!', title='Error', form_color='CAUTION')
            return
        self._update_config()
        self._cfg.save(fname)
        nps.notify_confirm(f'Configuration has been saved to:\n{fname}', title='Success')
        self._cfg_text.value = self._get_cfg_text_label()
        self._cfg_text.update()



class MainForm(nps.FormWithMenus):
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        #TODO connect to tablet now
        super().__init__(*args, **kwargs)

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^Q": self.exit_application
        })
        self.add(nps.TitleText, name = "Text:", value= "Just some text." )
        self.how_exited_handers[nps.wgwidget.EXITED_ESCAPE]  = self.exit_application

        # The menus are created here.
        # self.m1 = self.add_menu(name="Main Menu", shortcut="^M")
        # self.m1.addItemsFromList([
        #     ("Display Text", self.whenDisplayText, None, None, ("some text",)),
        #     ("Exit Application", self.exit_application, "é"),
        # ])
        
        # self.m3 = self.m2.addNewSubmenu("A sub menu", "^F")
        # self.m3.addItemsFromList([
        #     ("Just Beep",   self.whenJustBeep),
        # ])        

    def whenDisplayText(self, argument):
       nps.notify_confirm(argument)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()


class RATui(nps.NPSAppManaged):
    STARTING_FORM = 'CONNECT'

    def __init__(self, args):
        self._args = args
        self._cfg = RAConfig(args)
        self._connection = RAConnection(self._cfg)
        super().__init__()

    def onStart(self):
        self.addForm('CONNECT', StartUpForm, self._cfg, name='Connection Options')
        # Since the user may change configuration parameters within 'CONNECT',
        # the following forms should be initialized upon every invocation (to
        # inject the up-to-date parametrization)
        self.addFormClass('MAIN', MainForm, self._cfg, self._connection, name='Main')
