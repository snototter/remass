import npyscreen as nps
import os
import curses
import paramiko
import socket
import threading
from pdf2image import convert_from_path
from pdf2image.generators import counter_generator
import platform
import subprocess

from remass.tui.utilities import add_empty_row, full_class_name, safe_filename

from .widgets import ProgressBarBox, TitleCustomFilenameCombo, TitleCustomPassword, TitleAlphaSlider, TitlePageRange
from .fileselect import TitleRFilenameCombo
from ..tablet import RAConnection
from ..config import RAConfig, abbreviate_user
from ..filesystem import RDocument


###############################################################################
# Connection/Configuration
###############################################################################
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


###############################################################################
# PDF Export
###############################################################################
class ExportForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self.fs_root, self.fs_trash, self.fs_dirents = self._connection.get_filesystem()
        self.export_thread = None
        self.is_exporting = False
        # As long as the user has not manually set a local output file name, we
        # keep suggesting a suitable filename based on the selected (remote) notebook
        self.auto_replace_local_filename = True  # Flag indicating if we're still allowed to auto-replace
        self.prev_auto_replaced_filename = None  # Needed because a widget's when_value_changed is also triggered if the user just skips over the widget
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
                                      when_value_edited_cb=self._on_remote_file_selected,
                                      rm_dirents=self.fs_dirents, select_dir=False, relx=4,
                                      begin_entry_at=24)
        self.select_local = self.add(TitleCustomFilenameCombo, name="Output PDF",
                                     when_value_edited_cb=self._on_local_file_selected,
                                     value=None, select_dir=False,
                                     label=True, must_exist=False, relx=4,
                                     confirm_if_exists=True, begin_entry_at=24)
        add_empty_row(self)
        self.add(nps.Textfield, value="Rendering Options:", editable=False, color='STANDOUT')
        self.rendering_pages = self.add(TitlePageRange, name='Pages to Export', value='*', relx=4, begin_entry_at=24)
        self.rendering_template_alpha = self.add(TitleAlphaSlider, name='Template Alpha', value=3, begin_entry_at=24, relx=4)
        self.rendering_expand_pages = self.add(nps.RoundCheckBox, name='Expand Pages to rM View', value=True, relx=4)
        # self.rendering_only_annotated = self.add(nps.RoundCheckBox, name='Only Annotated Pages', value=False, relx=4)
        self.rendering_png = self.add(nps.RoundCheckBox, name='Convert to PNG', value=False, relx=4)
        self.rendering_dpi = self.add(nps.TitleText, name="Image Quality (DPI)", value='300', relx=4, begin_entry_at=24)
        add_empty_row(self)
        self.btn_start = self.add(nps.ButtonPress, name='[Start Export]', relx=3,
                                  when_pressed_function=self._start_export)
        add_empty_row(self)
        self.btn_open_folder = self.add(nps.ButtonPress, name='[Open Output Folder]', relx=3,
                                        when_pressed_function=self._open_folder)
        self.btn_open_pdf = self.add(nps.ButtonPress, name='[Open PDF]', relx=3,
                                     when_pressed_function=self._open_pdf)
        add_empty_row(self)
        screen_height, _ = self.widget_useable_space()  # This does NOT include the already created widgets!
        for i in range(screen_height - 22):
            add_empty_row(self)
        self.progress_bar = self.add(ProgressBarBox, name='Export Progress', lowest=0,
                                     step=1, out_of=100, label=True, value=0,
                                     max_height=3)
        self._toggle_widgets(True)

    def _on_remote_file_selected(self):
        if self.auto_replace_local_filename:
            if self.select_tablet.value is None:
                self.select_local.value = None
            else:
                fn = os.path.join(abbreviate_user(self._cfg.export_dir),
                                safe_filename(self.select_tablet.value.visible_name) + '.pdf')
                self.select_local.value = fn
                self.prev_auto_replaced_filename = fn
            self.select_local.display()
            self._toggle_open_pdf()

    def _on_local_file_selected(self):
        if self.select_local.value is not None and self.select_local.value != self.prev_auto_replaced_filename:
            self.auto_replace_local_filename = False
        self._toggle_open_pdf()

    def _start_export(self, *args, **kwargs):
        if self.is_exporting:
            return False
        # Check if the user selected input and destination
        if self.select_tablet.value is None or self.select_tablet.value.dirent_type != RDocument.dirent_type:
            nps.notify_confirm("You must select a notebook to export!",
                               title='Error', form_color='CAUTION', editw=1)
            return False
        if self.select_local.filename is None:
            nps.notify_confirm("You must select an output file!",
                               title='Error', form_color='CAUTION', editw=1)
            return False
        # Disable all inputs
        self._toggle_widgets(False)
        self._rendering_progress_callback(0)
        nps.notify('Export started - please be patient.\n'
                   '------------------------------------------\n'
                   'This form will be locked until completion.', title='Info')
        curses.napms(1200)
        curses.flushinp()
        self.is_exporting = True
        self.export_thread = threading.Thread(target=self._export_blocking,
                                              args=(self.select_tablet.value, 
                                                    self.select_local.filename,))
        self.export_thread.start()
        return True

    def _open_pdf(self, *args, **kwargs):
        fname = self.select_local.filename
        if fname is None or not os.path.exists(fname):
            nps.notify_confirm('Nothing exported so far.', title='Error',
                               form_color='CAUTION', editw=1)
        else:
            if platform.system() == 'Darwin':
                subprocess.call(('open', fname),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif platform.system() == 'Windows':
                os.startfile(fname)
            else:
                subprocess.call(('xdg-open', fname),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _open_folder(self, *args, **kwargs):
        folder = os.path.dirname(self.select_local.filename)
        if folder is None or not os.path.exists(folder):
            return
        else:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            if platform.system() == "Windows":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])

    def _toggle_open_pdf(self, editable=True):
        self.btn_open_pdf.editable = editable and \
            (self.select_local.filename is not None and
             os.path.exists(self.select_local.filename))
        self.btn_open_pdf.display()

    def _toggle_widgets(self, editable):
        # File selection widgets
        self.select_tablet.editable = editable
        self.select_tablet.display()
        self.select_local.editable = editable
        self.select_local.display()
        # Rendering option widgets
        self.rendering_pages.editable = editable
        self.rendering_pages.display()
        self.rendering_template_alpha.editable = editable
        self.rendering_template_alpha.display()
        self.rendering_expand_pages.editable = editable
        self.rendering_expand_pages.display()
        # self.rendering_only_annotated.editable = editable
        # self.rendering_only_annotated.display()
        self.rendering_png.editable = editable
        self.rendering_png.display()
        self.rendering_dpi.editable = editable
        self.rendering_dpi.display()
        # Buttons
        self.btn_start.editable = editable
        self.btn_start.display()
        self.btn_open_folder.editable = editable
        self.btn_open_folder.display()
        self._toggle_open_pdf(editable)
        # The form button will only be added (and removed) within the
        # base class' edit() method
        if hasattr(self, '_added_buttons'):
            self._added_buttons['ok_button'].editable = editable
            self._added_buttons['ok_button'].display()

    def _export_blocking(self, rm_file, output_filename):
        self._connection.render_document(rm_file, output_filename,
                                         self._rendering_progress_callback,
                                         template_alpha=self.rendering_template_alpha.alpha,
                                         expand_pages=self.rendering_expand_pages.value,
                                        #  only_annotated=self.rendering_only_annotated.value
                                         page_selection=self.rendering_pages.pages
                                         )
        if self.rendering_png.value:
            output_folder = os.path.dirname(output_filename)
            notification_suffix = '\n------------------------------------------\n'\
                                  f"\nPNGs have been exported to\n"\
                                  f"  '{abbreviate_user(output_folder)}'"
            fname = os.path.splitext(os.path.basename(output_filename))[0]
            dpi = int(self.rendering_dpi.value)
            fmt = 'png'
            _ = convert_from_path(output_filename, output_folder=output_folder,
                                  dpi=dpi, fmt=fmt, paths_only=True,
                                  single_file=False, thread_count=4,
                                  output_file=counter_generator(fname + '-', padding_goal=4))
        else:
            notification_suffix = ''
        self.is_exporting = False
        # Re-enable all widgets & notify the user (as we blocked all user 
        # inputs, this works from within this export thread, too)
        self._toggle_widgets(True)
        nps.notify(f"Successfully exported\n  '{rm_file.hierarchy_name}'\nto\n"
                   f"  '{abbreviate_user(output_filename)}'{notification_suffix}",
                   title='Info', form_color='STANDOUT')
        curses.napms(3000)
        curses.flushinp()
        self.display(clear=True)

    def _rendering_progress_callback(self, percentage):
        self.progress_bar.value = percentage
        self.progress_bar.display()

    def exit_application(self, *args, **kwargs):
        if self.is_exporting:
            return
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()


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
            hostname = self._connection.get_hostname()
            self._info_lbl.value = f"Connected to '{hostname}':"
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
