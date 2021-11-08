import npyscreen as nps
import paramiko
import socket

from .utilities import add_empty_row, full_class_name

from ..tablet import RAConnection
from ..config import RAConfig
from .forms import StartUpForm, ExportForm, ScreenCustomizationForm, TemplateManagementForm

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
        self.add(nps.ButtonPress, name='[Manage Templates]', relx=3,
                 when_pressed_function=self._switch_form_templates)
        add_empty_row(self)
        self.add(nps.ButtonPress, name='[Change Screens]', relx=3,
                 when_pressed_function=self._switch_form_screens)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()
    
    def _switch_form_templates(self, *args, **kwargs):
        self.parentApp.setNextForm('TEMPLATES')
        self.editing = False
        self.parentApp.switchFormNow()

    def _switch_form_screens(self, *args, **kwargs):
        self.parentApp.setNextForm('SCREENS')
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
        self.addFormClass('MAIN', MainForm, self._cfg, self._connection,
                          name='reMass')
        self.addFormClass('EXPORT', ExportForm, self._cfg, self._connection,
                          name='reMass: Export PDF')
        self.addFormClass('TEMPLATES', TemplateManagementForm, self._cfg, self._connection,
                          name='reMass: Template Management')
        self.addFormClass('SCREENS', ScreenCustomizationForm, self._cfg, self._connection,
                          name='reMass: Screen Customization')

    def onCleanExit(self):
        self._connection.close()
