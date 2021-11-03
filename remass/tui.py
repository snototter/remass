import npyscreen as nps
# import logging
import os
import time
import paramiko
import socket
import threading
from pathlib import Path

from .tablet import RAConnection
from .config import RAConfig, config_filename
from .fileselect import TitleRFilenameCombo
from .filesystem import RDocument


#TODO list:
# * to "cycle" the focus, we likely have to override ActionForm.edit() and set
#   editw accordingly. Caveat: what happens if the first widget is not editable?
# * try boxes to frame the main form's "tab buttons"

###############################################################################
# TUI Utilities
###############################################################################
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


###############################################################################
# Connection/Configuration
###############################################################################
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


class CustomFilenameCombo(nps.FilenameCombo):
    """Customizes the filename display of the default FilenameCombo"""
    def display_value(self, vl):
        # Try to abbreviate the user home directory
        try:
            f = Path(vl)
            return str('~' / f.relative_to(Path.home()))
        except ValueError:
            return str(vl)

    def _print(self):  # override (because I didn't like the "-Unset-" display)
        if self.value == None:
            printme = '- Not set -'
        else:
            try:
                printme = self.display_value(self.value)
            except IndexError:
                printme = '- Error -'
        if self.do_colors():
            self.parent.curses_pad.addnstr(self.rely, self.relx, printme, self.width, self.parent.theme_manager.findPair(self))
        else:
            self.parent.curses_pad.addnstr(self.rely, self.relx, printme, self.width)


class TitleCustomFilenameCombo(nps.TitleCombo):
    _entry_type = CustomFilenameCombo


class StartUpForm(nps.ActionForm):
    OK_BUTTON_TEXT = 'Connect'
    CANCEL_BUTTON_BR_OFFSET = (2, 20)
    CANCEL_BUTTON_TEXT = "Cancel"

    def __init__(self, config: RAConfig, *args, **kwargs):
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
        cfg_dname, cfg_fname = config_filename(self._cfg.config_filename)
        cfg_path = os.path.join(cfg_dname, cfg_fname)
        self._cfg_filename = self.add(TitleCustomFilenameCombo,
                                      name="Path", relx=4,
                                      value=cfg_path, select_dir=False,
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


###############################################################################
# PDF Export
###############################################################################
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
        super().__init__(screen, *args, lowest=0, step=1, out_of=10, label=True, color='STANDOUT', **kwargs)

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
        self.export_thread = None
        self.is_exporting = False
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()
    
    def _to_main(self, *args, **kwargs):
        if self.is_exporting:
            return
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main,
            "^S": self._start_export
        })
        self.add(nps.Textfield, value="Files:", editable=False, color='STANDOUT')
        self.select_tablet = self.add(TitleRFilenameCombo, name="reMarkable Notebook", label=True,
                                      rm_dirents=self.fs_dirents, select_dir=False, relx=4,
                                      begin_entry_at=24)
        self.select_local = self.add(TitleCustomFilenameCombo, name="Output PDF",
                                     value='exported-notebook.pdf', select_dir=False,
                                     label=True, must_exist=False, relx=4,
                                     confirm_if_exists=True, begin_entry_at=24)
        add_empty_row(self)
        self.add(nps.Textfield, value="Rendering Options:", editable=False, color='STANDOUT')
        self.rendering_template_alpha = self.add(TitleAlphaSlider, name='Template Alpha', value=3, begin_entry_at=24, relx=4)
        self.rendering_expand_pages = self.add(nps.RoundCheckBox, name='Expand Pages to rM View', value=True, relx=4)
        self.rendering_only_annotated = self.add(nps.RoundCheckBox, name='Only Annotated Pages', value=False, relx=4)
        add_empty_row(self)
        add_empty_row(self)
        self.btn_start = self.add(nps.ButtonPress, name='[Start PDF Export]', relx=3,
                                  when_pressed_function=self._start_export)
        add_empty_row(self)
        add_empty_row(self)
        screen_height, _ = self.widget_useable_space()  # This does NOT include the already created widgets!
        for i in range(screen_height - 19):
            add_empty_row(self)
        self.progress_bar = self.add(ProgressBarBox, name='Export Progress', lowest=0,
                                     step=1, out_of=100, label=True, value=0,
                                     max_height=3)

    def _start_export(self, *args, **kwargs):
        if self.is_exporting:
            return False
        # Check if the user selected input and destination
        if self.select_tablet.value is None or self.select_tablet.value.dirent_type != RDocument.dirent_type:
            nps.notify_confirm("You must select a notebook to export!",
                               title='Error', form_color='CAUTION', editw=1)
            return False
        if self.select_local.value is None:
            nps.notify_confirm("You must select an output file!",
                               title='Error', form_color='CAUTION', editw=1)
            return False
        # Disable all inputs
        self._toggle_widgets(False)
        #TODO upon 100% finished, clean up & notify the user (TODO add this to while_waiting! notify_confirm)
        self._rendering_progress_callback(0)
        nps.notify('Exporting can take several minutes!\n'
                   'Please be patient.\n'
                   '------------------------------------------\n'
                   'This form will be locked until completion.', title='Info')
        time.sleep(2)
        self.is_exporting = True
        self.export_thread = threading.Thread(target=self._export_blocking,
                                              args=(self.select_tablet.value, self.select_local.value,))
        self.export_thread.start()
        return True
    
    def _toggle_widgets(self, editable):
        self.rendering_only_annotated.editable = editable
        self.rendering_only_annotated.display()
        self.rendering_expand_pages.editable = editable
        self.rendering_expand_pages.display()
        self.rendering_template_alpha.editable = editable
        self.rendering_template_alpha.display()
        self.select_tablet.editable = editable
        self.select_tablet.display()
        self.select_local.editable = editable
        self.select_local.display()
        self.btn_start.editable = editable
        self.btn_start.display()
        self._added_buttons['ok_button'].editable = editable
        self._added_buttons['ok_button'].display()
    
    def _export_blocking(self, rm_file, output_filename):
        self._connection.render_document(rm_file, output_filename,
                                         self._rendering_progress_callback,
                                         template_alpha=self.rendering_template_alpha.alpha,
                                         expand_pages=self.rendering_expand_pages.value,
                                         only_annotated=self.rendering_only_annotated.value)
        self.is_exporting = False
        self._toggle_widgets(True)
        # nps.notify_confirm('Exported TODO to TODO', # don't show message box from this thread!!
        #                    title='Info', editw=1)

    def _rendering_progress_callback(self, percentage):
        self.progress_bar.value = percentage
        self.progress_bar.display()

    def exit_application(self, *args, **kwargs):
        if self.is_exporting:
            return
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()
    
    # def while_waiting(self):
    # TODO remove is_exporting
    #     if self.export_thread is not None and not self.is_exporting:
    #         nps.notify_confirm('Exported TODO to TODO', # doesn't work
    #                            title='Info', editw=1)
    #         time.sleep(2)
    #         self.export_thread = None
    #     #     self.progress_bar.update()
    #     # if self.export_thread is not None and self.export_thread.
    #     pass


###############################################################################
# Main
###############################################################################
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
                               title='Error', form_color='CAUTION', editw=1)
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
            self._tablet_model.value = self._connection.get_tablet_model().rjust(max_text_width)
            self._tablet_fwver.value = self._connection.get_firmware_version().rjust(max_text_width)
            self._tablet_free_space_root.value = self._connection.get_free_space('/').rjust(max_text_width)
            self._tablet_free_space_home.value = self._connection.get_free_space('/home').rjust(max_text_width)
            self._tablet_uptime.value = self._connection.get_uptime().rjust(max_text_width)
            bcap, bhealth, btemp = self._connection.get_battery_info()
            self._tablet_battery_info.value = f'{bcap} ({bhealth}), {btemp}'.rjust(max_text_width)
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
        self._info_lbl = self.add(nps.Textfield, value="", editable=False, color='STANDOUT')
        self._tablet_model = self.add(nps.TitleFixedText, name='Model',
                                      begin_entry_at=24, relx=4,
                                      value="", editable=False)
        self._tablet_fwver = self.add(nps.TitleFixedText, name="Firmware",
                                      begin_entry_at=24, relx=4,
                                      value="", editable=False)
        self._tablet_free_space_root = self.add(nps.TitleFixedText, name="Free space /",
                                                begin_entry_at=24, relx=4,
                                                value="", editable=False)
        self._tablet_free_space_home = self.add(nps.TitleFixedText, name="Free space /home",
                                                begin_entry_at=24, relx=4,
                                                value="", editable=False)
        self._tablet_battery_info = self.add(nps.TitleFixedText, name="Battery status",
                                             value="", begin_entry_at=24,
                                             relx=4, editable=False)
        self._tablet_uptime = self.add(nps.TitleFixedText, name="Uptime", value="",
                                       relx=4, begin_entry_at=24, editable=False)
        add_empty_row(self)
        add_empty_row(self)
        self.add(nps.Textfield, value='Tasks', editable=False, color='STANDOUT')
        self.add(nps.ButtonPress, name='[Export PDF]', relx=3,
                 when_pressed_function=self._switch_form_export)
        add_empty_row(self)   
        self.add(nps.ButtonPress, name='[Manage Templates] (not yet available)', relx=3,  # TODO Templates
                 when_pressed_function=self._switch_form_templates)
        add_empty_row(self)
        self.add(nps.ButtonPress, name='[Change Screens] (not yet available)', relx=3,  # TODO Screens
                 when_pressed_function=self._switch_form_screens)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()
    
    def _switch_form_templates(self, *args, **kwargs):
        self.parentApp.setNextForm('TEMPLATES')  # TODO Templates
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_screens(self, *args, **kwargs):
        self.parentApp.setNextForm('SCREENS')  # TODO Screens
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
        #TODO Templates
        #TODO Screens

    def onCleanExit(self):
        self._connection.close()
