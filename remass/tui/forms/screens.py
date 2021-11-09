"""Screen Customization"""
import npyscreen as nps
import os

from ..utilities import add_empty_row, open_with_default_application
from ..widgets import TitleCustomFilenameCombo
from ...tablet import RAConnection, SplashScreenUtil, NotEnoughDiskSpaceError
from ...config import RAConfig, abbreviate_user, backup_filename


class ScreenCustomizationForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        # self.add(nps.Textfield, value="Select Image:", editable=False, color='STANDOUT')
        self.screen_filename = self.add(TitleCustomFilenameCombo,
                                        name="Image File", relx=4,
                                        initial_folder=self._cfg.screen_dir, select_dir=False,
                                        label=True, must_exist=True,
                                        confirm_if_exists=False)
        self.add(nps.ButtonPress, name='[Validate Image]', relx=3,
                when_pressed_function=self._validate_image)
        self.add(nps.ButtonPress, name='[Open Image]', relx=3,
                when_pressed_function=self._open_image)
        add_empty_row(self)
        self.rm_screen = self.add(nps.TitleSelectOne,
                                  max_height = min(6, len(SplashScreenUtil.SCREENS)),
                                  value = [0,], name="Use As", relx=4,
                                  values = [s[1] for s in SplashScreenUtil.SCREENS],
                                  scroll_exit=True)
        add_empty_row(self)
        self.btn_backup = self.add(nps.ButtonPress, name='[Backup Current Screen]',
                                   relx=3, when_pressed_function=self._backup_screen)
        self.btn_start = self.add(nps.ButtonPress, name='[Upload Selected Screen]', relx=3,
                                  when_pressed_function=self._upload_screen)
        self.btn_reload_ui = self.add(nps.ButtonPress, name='[Restart Tablet UI]', relx=3,
                                      when_pressed_function=self._restart_ui)

    def _validate_image(self, *args, confirm_success=True, **kwargs) -> bool:
        if self.screen_filename.filename is None:
            nps.notify_confirm("You must select an image file!",
                               title='Error', form_color='CAUTION', editw=1)
            return False
        valid, valmsg = SplashScreenUtil.validate_custom_screen(self.screen_filename.filename)
        if not valid:
            nps.notify_confirm(f"This is not a valid splash screen:\n{valmsg}",
                               title='Error', form_color='CAUTION', editw=1)
            return False
        if confirm_success:
            nps.notify_confirm('This is a valid splash screen!', title='Info',
                               form_color='STANDOUT', editw=1)
        return True

    def _open_image(self, *args, **kwargs):
        fname = self.screen_filename.filename
        if fname is None or not os.path.exists(fname):
            nps.notify_confirm('You must select an image file first.', title='Error',
                               form_color='CAUTION', editw=1)
        else:
            open_with_default_application(fname)

    def _backup_screen(self, *args, **kwargs):
        screen_selection = SplashScreenUtil.SCREENS[self.rm_screen.value[0]]
        remote_file = SplashScreenUtil.tablet_filename(screen_selection)
        bak_file = backup_filename(screen_selection[0], self._cfg.screen_backup_dir)
        self._connection.download_file(remote_file, bak_file)
        nps.notify_confirm(f"'{screen_selection[1]}' screen has been sucessfully backed up to:\n"
                           f"{abbreviate_user(bak_file)}",
                           title='Info', form_color='STANDOUT', editw=1)

    def _upload_screen(self, *args, **kwargs) -> bool:
        if not self._validate_image(confirm_success=False):
            return False
        
        screen_selection = SplashScreenUtil.SCREENS[self.rm_screen.value[0]]
        remote_file = SplashScreenUtil.tablet_filename(screen_selection)
        try:
            self._connection.upload_file(self.screen_filename.filename, remote_file)
            nps.notify_confirm(f"'{screen_selection[1]}' screen has been sucessfully uploaded.\n"
                               "Please restart the UI/reboot the table to use it.",
                               title='Info', form_color='STANDOUT')
        except NotEnoughDiskSpaceError as e:
            nps.notify_confirm("Not enough disk space on tablet.\n"
                               f"----------------------------------------\n{e}",
                               title='Error', form_color='CAUTION', editw=1)

    def _restart_ui(self, *args, **kwargs):
        self._connection.restart_ui()

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()