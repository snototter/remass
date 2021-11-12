"""Screen Customization"""
import npyscreen as nps
import os

from ..utilities import add_empty_row
from ...tablet import RAConnection
from ...config import RAConfig
from ...templates import TemplateOrganizer


class TemplateSynchronizationForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self._organizer = TemplateOrganizer(cfg, connection)
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        self.lbl_backups = self.add(nps.Textfield, value='', editable=False, color='STANDOUT')
        self.btn_load = self.add(nps.ButtonPress, name='[Load Templates From Tablet]', relx=3,
                                 when_pressed_function=self._load_templates)
        add_empty_row(self)
        self.lbl_uploads = self.add(nps.Textfield, value='', editable=False, color='STANDOUT')
        # uploadable = [f'foo {idx}' for idx in range(40)] #TODO remove
        uploadable = self._organizer.custom_template_names
        self.select_uploads = self.add(nps.TitleMultiSelect, max_height=-4, name='Select for Upload',
                                       relx=4, scroll_exit=True, begin_entry_at=20,
                                       value=[idx for idx in range(len(uploadable))],
                                       values=uploadable)
        self.btn_upload = self.add(nps.ButtonPress, name="[Upload Selected]", relx=3,
                                   when_pressed_function=self._upload_templates)
        add_empty_row(self)
        self.btn_reload_ui = self.add(nps.ButtonPress, name='[Restart Tablet UI]', relx=3,
                                      when_pressed_function=self._restart_ui)
        self._update_labels()
    
    def _update_labels(self):
        lbl = f'Templates available local for Export: {len(self._organizer.backedup_templates)}'
        self.lbl_backups.value = lbl

        lbl = f'Templates available for Upload: {len(self._organizer.custom_templates)}'
        self.lbl_uploads.value = lbl
        super().display(clear=True)

    def _load_templates(self, *args, **kwargs):
        self._connection.download_templates(self._cfg.template_backup_dir)
        nps.notify_confirm(f"Templates have been downloaded to\n{self._cfg.template_backup_dir}",
                           title='Info', form_color='STANDOUT', editw=1)
        self._update_labels()

    def _upload_templates(self, *args, **kwargs):
        #TODO self.select_uploads
        pass

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


class TemplateRemovalForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self._organizer = TemplateOrganizer(cfg, connection)
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        self.add(nps.Textfield, value='TODO', editable=False, color='STANDOUT')

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()