import npyscreen as nps
import logging
import os

import paramiko
import socket

from remass.filesystem import RDocument

from .tablet import RAConnection
from .config import RAConfig, config_filename
from .fileselect import TitleRFilenameCombo


#TODO list:
# * to "cycle" the focus, we likely have to override ActionForm.edit() and set
#   editw accordingly. Caveat: what happens if the first widget is not editable?
# * try boxes to frame the main form's "tab buttons"


class CustomPasswordEntry(nps.Textfield):
    """Extension to npyscreen's PasswordEntry which allows overriding the
    password replacement character."""
    def __init__(self, *args, pwd_char: str='*', **kwargs):
        self.pwd_char = pwd_char
        super().__init__(*args, **kwargs)

    def _print(self):
        strlen = len(self.value)
        tmp_x = self.relx
        if self.maximum_string_length < strlen:
            n = self.maximum_string_length
            fx = self.parent.curses_pad.addch
        else:
            n = strlen
            fx = self.parent.curses_pad.addstr
        for i in range(n):
            fx(self.rely, tmp_x, self.pwd_char)
            tmp_x += 1


class TitleCustomPassword(nps.TitleText):
    _entry_type = CustomPasswordEntry




def add_empty_row(form: nps.Form) -> None:
    """Adds an empty row to the given form."""
    form.add(nps.FixedText, value='', hidden=True)


def full_class_name(o):
    """Returns the fully qualified class name of the given object.
    Taken from MB's answer: https://stackoverflow.com/a/13653312
    """
    module = o.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return o.__class__.__name__
    return module + '.' + o.__class__.__name__


#TODO nice-to-have: 2 boxes (connection & configuration)
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
        self.add_handlers({
            "^X": self.exit_application  # exit
        })
        self._host = self.add(nps.TitleText, name="Host",
                              value=self._cfg['connection']['host'])
        self._fallback_host = self.add(nps.TitleText, name="Fallback Host",
                                       value=self._cfg['connection']['host_fallback'])
        self._keyfile = self.add(nps.TitleFilenameCombo,
                                 name="Private Key", label=True,
                                 value=self._cfg['connection']['keyfile'],
                                 select_dir=False, must_exist=True)
        self._password = self.add(TitleCustomPassword, name="Password",
                                  pwd_char = '*', value=self._cfg['connection']['password'])
        
        add_empty_row(self)
        self._cfg_text = self.add(nps.FixedText, value=self._get_cfg_text_label(), editable=False)
        cfg_dname, cfg_fname = config_filename(self._cfg.config_filename)
        cfg_path = os.path.join(cfg_dname, cfg_fname)
        self._cfg_filename = self.add(nps.TitleFilenameCombo,
                                      name="Path",
                                      value=cfg_path, select_dir=False,
                                      label=True, must_exist=False,
                                      confirm_if_exists=True)
        self.add(nps.ButtonPress, name='Save Configuration File', relx=17,
                 when_pressed_function=self._save_config)

        # We want to focus/highlight the ok button (which is created inside
        # the base class' edit())
        self.preserve_selected_widget = True
        self.editw = 9

    def on_cancel(self):
        self.exit_application()
    
    def exit_application(self, *args, **kwargs):
        self.parentApp.switchForm(None)  # Exits the application
        # self.parentApp.setNextForm(None)
        # self.editing = False
        # self.parentApp.switchFormNow()


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
            nps.notify_confirm('You must select a valid configuration file path!', title='Error', form_color='CAUTION')
            return
        self._update_config()
        self._cfg.save(fname)
        nps.notify_confirm(f'Configuration has been saved to:\n{fname}', title='Success')
        self._cfg_text.value = self._get_cfg_text_label()
        self._cfg_text.update()


def _ralign(txt: str, width: int) -> str:
    """Aligns the text right (for labels/text fields) by padding it with spaces."""
    if txt is None or len(txt) >= width:
        return txt
    return ' '*(width - len(txt)) + txt






class AlphaSlider(nps.Slider):
    """Slider widget to select a transparency/alpha value in [0,1] with increments of 0.1"""
    def translate_value(self):
        assert self.step == 1
        assert self.out_of == 10
        return f'{self.alpha:.1f}'.rjust(8)

    @property
    def alpha(self):
        return self.value / self.out_of


class TitleAlphaSlider(nps.TitleText):
    _entry_type = AlphaSlider
    def __init__(self, screen, *args, **kwargs):
        super().__init__(screen, lowest=0, step=1, out_of=10, label=True, *args, **kwargs)

    @property
    def alpha(self):
        return self.entry_widget.alpha



class ProgressBar(nps.Slider):
    def __init__(self, *args, **keywords):
        super().__init__(*args, **keywords)
        self.editable = False

    def translate_value(self):
        assert self.out_of == 100
        percent = int(self.value)
        return f'{percent:d} %'.rjust(8)

class ProgressBarBox(nps.BoxTitle):   
    _contained_widget = ProgressBar


class ExportForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self.fs_root, self.fs_trash, self.fs_dirents = self._connection.get_filesystem()
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,  # exit
            "^B": self.on_ok,  # go back
            "^S": self._start_export
        })
        self.select_tablet = self.add(TitleRFilenameCombo, name="reMarkable Notebook", label=True,
                                      rm_dirents=self.fs_dirents, select_dir=False,
                                      begin_entry_at=24)
        self.select_local = self.add(nps.TitleFilenameCombo, name="Output PDF",
                                     value='exported-notebook.pdf', select_dir=False,
                                     label=True, must_exist=False,
                                     confirm_if_exists=True, begin_entry_at=24)
        add_empty_row(self)
        self.rendering_template_alpha = self.add(TitleAlphaSlider, name='Template Alpha', value=3, begin_entry_at=24)
        self.rendering_expand_pages = self.add(nps.RoundCheckBox, name='Expand Pages to rM View', value=True)
        self.rendering_only_annotated = self.add(nps.RoundCheckBox, name='Only Annotated Pages', value=False)
        add_empty_row(self)
        self.add(nps.ButtonPress, name='Start PDF Export', relx=23+2,
                 when_pressed_function=self._start_export)
        add_empty_row(self)
        add_empty_row(self)
        self.progress_bar = self.add(ProgressBarBox, name='Export Progress', value=0, max_height=3, out_of=100)

    def _start_export(self, *args, **kwargs):
        # Check if the user selected input and destination
        if self.select_tablet.value is None or\
           self.select_tablet.value.dirent_type != RDocument.dirent_type:
            nps.notify_confirm("You must select a notebook to export!",
                               title='Error', form_color='CAUTION')
            return False
        if self.select_local.value is None:
            nps.notify_confirm("You must select an output file!",
                               title='Error', form_color='CAUTION')
            return False
        # raise RuntimeError(f'Need to render: {self.select_tablet.value.hierarchy_name} --> '
        #                    f'{self.select_local.value}, alpha {self.rendering_template_alpha.alpha},'
        #                    f' expand {self.rendering_expand_pages.value}, annotated-only {self.rendering_only_annotated.value}')
        #TODO start thread, implement callback to adjust progress bar
        #TODO upon 100% finished, clean up & notify the user
        self._rendering_progress_callback(42.3)
        return True
    
    def _rendering_progress_callback(self, percentage):
        self.progress_bar.value = percentage
        self.progress_bar.update()

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()


class MainForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Exit'

    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        super().__init__(*args, **kwargs)

    def beforeEditing(self):
        try:
            self._connection.open()
        except (paramiko.SSHException, socket.timeout, socket.gaierror) as e:
            nps.notify_confirm("Cannot connect to tablet - aborting now.\n"
                               "----------------------------------------\n"
                               f"Exception ({full_class_name(e)}):\n{e}",
                               title='Error', form_color='CAUTION')
            # self.exit_application() will be ignored when invoked from this
            # exception handler, thus we have to quit the ugly way:
            raise RuntimeError(f'Aborting due to connection error: {e}') from None
        self.update_device_info()

    def on_ok(self):
        self.exit_application()

    def update_device_info(self):
        if self._connection.is_connected():
            max_text_width = 22
            self._info_lbl.value = 'Connected to device:'
            self._tablet_model.value = _ralign(self._connection.get_tablet_model(),
                                               max_text_width)
            self._tablet_fwver.value = _ralign(self._connection.get_firmware_version(),
                                               max_text_width)
            self._tablet_free_space_root.value = _ralign(self._connection.get_free_space('/'),
                                                         max_text_width)
            self._tablet_free_space_home.value = _ralign(self._connection.get_free_space('/home'),
                                                         max_text_width)
            self._tablet_uptime.value = _ralign(self._connection.get_uptime(),
                                                max_text_width)
            bcap, bhealth, btemp = self._connection.get_battery_info()
            self._tablet_battery_info.value = _ralign(f'{bcap} ({bhealth}), {btemp}',
                                                      max_text_width)
        else:
            self._info_lbl.value = '[ERROR] Not Connected!'
        super().display(clear=True)

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^E": self._switch_form_export,
            "^T": self._switch_form_templates,
            "^S": self._switch_form_screens
        })
        self._info_lbl = self.add(nps.Textfield, value="", editable=False)
        add_empty_row(self)
        self._tablet_model = self.add(nps.TitleFixedText, name='Model',
                                      begin_entry_at=20,
                                      value="", editable=False)
        self._tablet_fwver = self.add(nps.TitleFixedText, name="Firmware",
                                      begin_entry_at=20,
                                      value="", editable=False)
        self._tablet_free_space_root = self.add(nps.TitleFixedText, name="Free space /",
                                                begin_entry_at=20,
                                                value="", editable=False)
        self._tablet_free_space_home = self.add(nps.TitleFixedText, name="Free space /home",
                                                begin_entry_at=20,
                                                value="", editable=False)
        self._tablet_battery_info = self.add(nps.TitleFixedText, name="Battery status",
                                             value="", begin_entry_at=20,
                                             editable=False)
        self._tablet_uptime = self.add(nps.TitleFixedText, name="Uptime", value="",
                                       begin_entry_at=20, editable=False)
        add_empty_row(self)
        add_empty_row(self)
        add_empty_row(self)
        self.add(nps.ButtonPress, name='Export PDF', relx=8,
                 when_pressed_function=self._switch_form_export)
        add_empty_row(self)   
        self.add(nps.ButtonPress, name='Manage Templates', relx=8,
                 when_pressed_function=self._switch_form_templates)
        add_empty_row(self)
        self.add(nps.ButtonPress, name='Change Screens', relx=8,
                 when_pressed_function=self._switch_form_screens)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()
    
    def _switch_form_templates(self, *args, **kwargs):
        self.parentApp.setNextForm('TEMPLATES')  # TODO
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_screens(self, *args, **kwargs):
        self.parentApp.setNextForm('SCREENS')  # TODO
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_export(self, *args, **kwargs):
        self.parentApp.setNextForm('EXPORT')
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
        self.addFormClass('MAIN', MainForm, self._cfg, self._connection, name='reMass')
        self.addFormClass('EXPORT', ExportForm, self._cfg, self._connection, name='reMass: Export PDF')

    def onCleanExit(self):
        self._connection.close()
