"""Screen Customization"""
import npyscreen as nps
import os

from ..utilities import add_empty_row
from ...tablet import TabletConnection
from ...config import RemassConfig, abbreviate_user
from ...templates import TemplateOrganizer, template_name


class TemplateSynchronizationForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RemassConfig, connection: TabletConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self._organizer = TemplateOrganizer(cfg, connection)
        self._uploadable = list()
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        self.lbl_remote = self.add(nps.Textfield, value='', editable=False, color='STANDOUT')
        add_empty_row(self)
        self.lbl_backups = self.add(nps.Textfield, value='', editable=False, color='STANDOUT')
        add_empty_row(self)
        self.btn_load = self.add(nps.ButtonPress, name='[Download Templates From Tablet]', relx=3,
                                 when_pressed_function=self._download_templates)
        add_empty_row(self)
        self.lbl_uploads = self.add(nps.Textfield, value='', editable=False, color='STANDOUT')
        self.select_uploads = self.add(nps.TitleMultiSelect, max_height=-4, name='Select for Upload',
                                       relx=4, scroll_exit=True, begin_entry_at=20)
        self.btn_upload = self.add(nps.ButtonPress, name="[Upload Selected]", relx=3,
                                   when_pressed_function=self._upload_templates)
        self.btn_reload_ui = self.add(nps.ButtonPress, name='[Restart Tablet UI]', relx=3,
                                      when_pressed_function=self._restart_ui)
        self._update_widgets()
    
    def _update_widgets(self):
        backed_up = self._organizer.load_backedup_templates()
        lbl = f'Templates available on PC: {len(backed_up)}'
        self.lbl_backups.value = lbl

        remote = self._organizer.load_remote_templates()
        self.lbl_remote.value = f'Templates available on Tablet: {len(remote)}'

        uploadable = self._organizer.load_uploadable_templates()
        lbl = f'Custom Templates for Upload: {len(uploadable)}'
        self.lbl_uploads.value = lbl

        
        if len(uploadable) != len(self._uploadable):
            self._uploadable = uploadable
            lbls = [template_name(u) for u in self._uploadable]
            self.select_uploads.values = lbls
            self.select_uploads.value = [i for i in range(len(self._uploadable))]
        super().display(clear=True)

    def _download_templates(self, *args, **kwargs):
        self._connection.download_templates(self._cfg.template_backup_dir)
        nps.notify_confirm(f"Templates have been downloaded to\n{self._cfg.template_backup_dir}",
                           title='Info', form_color='STANDOUT', editw=1)
        self._update_widgets()

    def _upload_templates(self, *args, **kwargs):
        to_upload = [self._uploadable[i] for i in self.select_uploads.value]
        if len(to_upload) > 0:
            self._organizer.synchronize(templates_to_add=to_upload, replace_templates=True,
                                        backup_template_json=False)
            nps.notify_confirm("Templates have been uploaded.\nRestarting UI now.",
                               title='Info', form_color='STANDOUT', editw=1)
            self._update_widgets()

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
    def __init__(self, cfg: RemassConfig, connection: TabletConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self._organizer = TemplateOrganizer(cfg, connection)
        self._remote_templates = list()
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        self.lbl_remote = self.add(nps.Textfield, value='', editable=False, color='STANDOUT')
        add_empty_row(self)
        self.select_templates = self.add(nps.TitleMultiSelect, max_height=-4, name='Deselect to Remove',
                                         relx=4, scroll_exit=True, begin_entry_at=20)
        self.add(nps.ButtonPress, name="[Synchronize Selection]", relx=3,
                 when_pressed_function=self._synchronize_selection)
        self._update_widgets()
    
    def _update_widgets(self):
        remote = self._organizer.load_remote_templates()
        lbl = f'Templates available on Tablet: {len(remote)}'
        self.lbl_remote.value = lbl
        
        if len(remote) != len(self._remote_templates):
            self._remote_templates= remote
            lbls = [template_name(u) for u in self._remote_templates]
            self.select_templates.values = lbls
            self.select_templates.value = [i for i in range(len(self._remote_templates))]
        super().display(clear=True)

    def _synchronize_selection(self, *args, **kwargs):
        to_disable = [self._remote_templates[i] for i in range(len(self._remote_templates)) if i not in self.select_templates.value]
        if len(to_disable) > 0:
            fn = self._organizer.synchronize(templates_to_disable=to_disable,
                                             backup_template_json=True)
            nps.notify_confirm("Templates have been disabled.\n"
                               "Original template configuration was backed up at:\n"
                               f"{abbreviate_user(fn)}",
                               title='Info', form_color='STANDOUT', editw=1)
        self._update_widgets()

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()
