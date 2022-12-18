import npyscreen as nps
import paramiko
import socket

from remass.tui.utilities import add_empty_row, full_class_name

from remass import __version__ as remass_version
from remass.tablet import TabletConnection
from remass.config import RemassConfig
from remass.tui.forms import StartUpForm, ExportForm, ScreenCustomizationForm,\
    TemplateSynchronizationForm, TemplateRemovalForm, DeviceSettingsForm


###############################################################################
# Main
###############################################################################
class MainForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Exit'

    def __init__(
            self, cfg: RemassConfig, connection: TabletConnection,
            *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        super().__init__(*args, **kwargs)

    def beforeEditing(self):
        try:
            self._connection.open()
        except (paramiko.SSHException, socket.timeout, socket.gaierror) as e:
            nps.notify_confirm(
                "Cannot connect to tablet - aborting now.\n"
                "----------------------------------------\n"
                f"Exception ({full_class_name(e)}):\n{e}",
                title='Error', form_color='CAUTION', editw=1)
            # self.exit_application() will be ignored when invoked from this
            # exception handler, thus we have to quit the ugly way:
            raise RuntimeError(
                f'Aborting due to connection error: {e}') from None
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
            self._tablet_free_space_root.value = self._connection.get_free_space_str('/').rjust(max_text_width)
            self._tablet_free_space_home.value = self._connection.get_free_space_str('/home').rjust(max_text_width)
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
            "^T": self._switch_form_template_sync,
            "^R": self._switch_form_template_del,
            "^S": self._switch_form_screens
        })
        self._info_lbl = self.add(
            nps.Textfield, value="", editable=False, color='STANDOUT')
        self._tablet_model = self.add(
            nps.TitleFixedText, name='Model',
            begin_entry_at=24, relx=4,
            value="", editable=False)
        self._tablet_fwver = self.add(
            nps.TitleFixedText, name="Firmware",
            begin_entry_at=24, relx=4,
            value="", editable=False)
        self._tablet_free_space_root = self.add(
            nps.TitleFixedText, name="Free space at `/`",
            begin_entry_at=24, relx=4,
            value="", editable=False)
        self._tablet_free_space_home = self.add(
            nps.TitleFixedText, name="Free space at `/home`",
            begin_entry_at=24, relx=4,
            value="", editable=False)
        self._tablet_battery_info = self.add(
            nps.TitleFixedText, name="Battery status",
            value="", begin_entry_at=24,
            relx=4, editable=False)
        self._tablet_uptime = self.add(
            nps.TitleFixedText, name="Uptime", value="",
            relx=4, begin_entry_at=24, editable=False)
        add_empty_row(self)

        self.add(
            nps.Textfield, value='Utilities', editable=False, color='STANDOUT')
        self.add(
            nps.ButtonPress, name='[Export Notebooks]', relx=3,
            when_pressed_function=self._switch_form_export)
        self.add(
            nps.ButtonPress, name='[Up-/Download Templates]', relx=3,
            when_pressed_function=self._switch_form_template_sync)
        self.add(
            nps.ButtonPress, name='[Remove Templates]', relx=3,
            when_pressed_function=self._switch_form_template_del)
        self.add(
            nps.ButtonPress, name='[Change Screens]', relx=3,
            when_pressed_function=self._switch_form_screens)
        add_empty_row(self)

        self.add(
            nps.Textfield, value='Tablet Control',
            editable=False, color='STANDOUT')
        self.add(
            nps.ButtonPress, name='[Adjust Settings]', relx=3,
            when_pressed_function=self._switch_form_control)
        add_empty_row(self)

        self.add(
            nps.ButtonPress, name='[Restart Tablet UI]', relx=3,
            when_pressed_function=self._restart_tablet_ui)
        self.add(
            nps.ButtonPress, name='[Reboot Tablet]', relx=3,
            when_pressed_function=self._reboot_tablet)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()
    
    def _switch_form_template_sync(self, *args, **kwargs):
        self.parentApp.setNextForm('TEMPLATESYNC')
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_template_del(self, *args, **kwargs):
        self.parentApp.setNextForm('TEMPLATEDEL')
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_screens(self, *args, **kwargs):
        self.parentApp.setNextForm('SCREENS')
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_control(self, *args, **kwargs):
        self.parentApp.setNextForm('CONTROL')
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_export(self, *args, **kwargs):
        self.parentApp.setNextForm('EXPORT')
        self.editing = False
        self.parentApp.switchFormNow()

    def _restart_tablet_ui(self, *args, **kwargs):
        self._connection.restart_ui()

    def _reboot_tablet(self, *args, **kwargs):
        if nps.notify_yes_no(
                'Do you really want to reboot the tablet?\nreMass will exit, too.',
                title='Confirm', form_color='STANDOUT', editw=1):
            self._connection.reboot_tablet()
            self.exit_application()


class RATui(nps.NPSAppManaged):
    STARTING_FORM = 'CONNECT'

    def __init__(self, args):
        self._args = args
        self._cfg = RemassConfig(args)
        self._connection = TabletConnection(self._cfg)
        super().__init__()

    def onStart(self):
        vers_str = f'reMass v{remass_version}'
        self.addForm(
            'CONNECT', StartUpForm, self._cfg,
            name=f'Connection Options - {vers_str}')
        # Since the user may change configuration parameters within 'CONNECT',
        # the following forms should be initialized upon every invocation (to
        # inject the up-to-date parametrization)
        self.addFormClass(
            'MAIN', MainForm, self._cfg, self._connection,
            name=vers_str)
        self.addFormClass(
            'EXPORT', ExportForm, self._cfg, self._connection,
            name=f'Export Notebooks - {vers_str}')
        self.addFormClass(
            'TEMPLATESYNC', TemplateSynchronizationForm, self._cfg,
            self._connection,
            name=f'Template Up-/Download - {vers_str}')
        self.addFormClass(
            'TEMPLATEDEL', TemplateRemovalForm, self._cfg, self._connection,
            name=f'Template Removal - {vers_str}')
        self.addFormClass(
            'SCREENS', ScreenCustomizationForm, self._cfg, self._connection,
            name=f'Screen Customization - {vers_str}')
        self.addFormClass(
            'CONTROL', DeviceSettingsForm, self._cfg, self._connection,
            name=f'Device Settings - {vers_str}')

    def onCleanExit(self):
        self._connection.close()
