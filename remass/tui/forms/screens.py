"""Screen Customization"""
import npyscreen as nps
import os
import curses
import threading
from pdf2image import convert_from_path
from pdf2image.generators import counter_generator

from ..utilities import add_empty_row, safe_filename, open_with_default_application

from ..widgets import ProgressBarBox, TitleCustomFilenameCombo, TitleAlphaSlider, TitlePageRange
from ..fileselect import TitleRFilenameCombo
from ...tablet import RAConnection
from ...config import RAConfig, abbreviate_user
from ...filesystem import RDocument


class ScreenCustomizationForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RAConfig, connection: RAConnection, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cfg = cfg
        self._connection = connection

    def on_ok(self):
        self._to_main()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main
        })
        self.add(nps.Textfield, value="TODO:", editable=False, color='STANDOUT')
        # self.select_tablet = self.add(TitleRFilenameCombo, name="reMarkable Notebook", label=True,
        #                               when_value_edited_cb=self._on_remote_file_selected,
        #                               rm_dirents=self.fs_dirents, select_dir=False, relx=4,
        #                               begin_entry_at=24)
        # self.select_local = self.add(TitleCustomFilenameCombo, name="Output PDF",
        #                              when_value_edited_cb=self._on_local_file_selected,
        #                              value=None, select_dir=False,
        #                              label=True, must_exist=False, relx=4,
        #                              confirm_if_exists=True, begin_entry_at=24)
        # add_empty_row(self)
        # self.add(nps.Textfield, value="Rendering Options:", editable=False, color='STANDOUT')
        # self.rendering_pages = self.add(TitlePageRange, name='Pages to Export', value='*', relx=4, begin_entry_at=24)
        # self.rendering_template_alpha = self.add(TitleAlphaSlider, name='Template Alpha', value=3, begin_entry_at=24, relx=4)
        # self.rendering_expand_pages = self.add(nps.RoundCheckBox, name='Expand Pages to rM View', value=True, relx=4)
        # # self.rendering_only_annotated = self.add(nps.RoundCheckBox, name='Only Annotated Pages', value=False, relx=4)
        # self.rendering_png = self.add(nps.RoundCheckBox, name='Convert to PNG', value=False, relx=4)
        # self.rendering_dpi = self.add(nps.TitleText, name="Image Quality (DPI)", value='300', relx=4, begin_entry_at=24)
        # add_empty_row(self)
        # self.btn_start = self.add(nps.ButtonPress, name='[Start Export]', relx=3,
        #                           when_pressed_function=self._start_export)
        # add_empty_row(self)
        # self.btn_open_folder = self.add(nps.ButtonPress, name='[Open Output Folder]', relx=3,
        #                                 when_pressed_function=self._open_folder)
        # self.btn_open_pdf = self.add(nps.ButtonPress, name='[Open PDF]', relx=3,
        #                              when_pressed_function=self._open_pdf)
        # add_empty_row(self)
        # screen_height, _ = self.widget_useable_space()  # This does NOT include the already created widgets!
        # for i in range(screen_height - 22):
        #     add_empty_row(self)
        # self.progress_bar = self.add(ProgressBarBox, name='Export Progress', lowest=0,
        #                              step=1, out_of=100, label=True, value=0,
        #                              max_height=3)
        # self._toggle_widgets(True)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()
