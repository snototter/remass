"""Adjust device parameters"""
import datetime
import npyscreen as nps
from typing import Tuple

from remass.tui.utilities import add_empty_row
from remass.tablet import TabletConnection
from remass.config import RemassConfig


def tz_dst2std(tzstr: str) -> str:
    """Return the standard time zone abbreviation for the given
    timezone abbreviation. Needed, because we cannot use DST abbreviations
    when setting the timezone via timedatectl on the tablet.

    Using DST-to-STD mappings from:
    https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    except for GMT --> IST (Irish Std Time)
    """
    mapping = {
        'ACDT': 'ACST',
        'ADT': 'AST',
        'AEDT': 'AEST',
        'AKDT': 'AKST',
        'BST': 'GMT',
        'CDT': 'CST',
        'CEST': 'CET',
        'EDT': 'EST',
        'EEST': 'EET',
        'HDT': 'HST',
        'IDT': 'IST',
        'MDT': 'MST',
        'NDT': 'NST',
        'NZDT': 'NZST',
        'PDT': 'PST',
        'WEST': 'WET'
    }
    if tzstr in mapping:
        return mapping[tzstr]
    else:
        return tzstr


def get_local_time() -> Tuple[str, str]:
    """Returns the current datetime string and timezone."""
    current_time = datetime.datetime.now(datetime.timezone.utc).astimezone()
    return current_time.strftime('%Y-%m-%d %H:%M %Z'), tz_dst2std(current_time.strftime('%Z'))


class DeviceSettingsForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RemassConfig, connection: TabletConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self._remote_templates = list()
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        self.add(nps.Textfield, value='Timezone', editable=False, color='STANDOUT')
        self.tz_remote = self.add(nps.TitleText, name='Tablet Time', value='',
                                  editable=False, begin_entry_at=20, relx=4)
        self.tz_local = self.add(nps.TitleText, name='Local Time', value='',
                                 editable=False, begin_entry_at=20, relx=4)
        self.add(nps.ButtonPress, name="[Adjust Remote Timezone]", relx=3,
                 when_pressed_function=self._update_timezone)

        add_empty_row(self)
        self.add(nps.Textfield, value='Host', editable=False, color='STANDOUT')
        self.hostname = self.add(nps.TitleText, name='Edit Hostname', value='', editable=True,
                                 begin_entry_at=20, relx=4)
        self.add(nps.ButtonPress, name="[Change Hostname]", relx=3,
                 when_pressed_function=self._update_hostname)
        add_empty_row(self)
        self.add(nps.ButtonPress, name='[Restart Tablet UI]', relx=3,
                 when_pressed_function=self._restart_tablet_ui)
        self.add(nps.ButtonPress, name='[Reboot Tablet]', relx=3,
                 when_pressed_function=self._reboot_tablet)
        self._update_widgets()

    def _update_widgets(self):
        self.tz_remote.value = self._connection.get_remote_time()
        display_time, _ = get_local_time()
        self.tz_local.value = display_time

        self.hostname.value = self._connection.get_hostname()
        super().display(clear=True)

    def _update_timezone(self, *args, **kwargs):
        _, tz = get_local_time()
        self._connection.set_remote_timezone(tz)
        nps.notify_confirm(f'Time zone has been adjusted to {tz}',
                           title='Info', editw=1)
        self._update_widgets()

    def _update_hostname(self, *args, **kwargs):
        hostname = self.hostname.value.strip()
        if not self._connection.set_hostname(hostname):
            nps.notify_confirm("Invalid hostname - refer to 'man hostname'\n"
                               "how to choose a valid one.",
                               form_color='CAUTION', title='Error', editw=1)
        else:
            nps.notify_confirm(f'Hostname has been set to "{hostname}".',
                               title='Info', editw=1)
            self._update_widgets()

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()

    def _restart_tablet_ui(self, *args, **kwargs):
        self._connection.restart_ui()

    def _reboot_tablet(self, *args, **kwargs):
        if nps.notify_yes_no('Do you really want to reboot the tablet?\nreMass will exit, too.',
                             title='Confirm', form_color='STANDOUT', editw=1):
            self._connection.reboot_tablet()
            self.exit_application()
