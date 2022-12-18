"""PDF Export"""
import npyscreen as nps
import os
import curses
import threading
from pdf2image import convert_from_path
from pdf2image.generators import counter_generator

from ..utilities import add_empty_row, safe_filename, open_with_default_application

from ..widgets import ProgressBarBox, TitleCustomFilenameCombo, TitleAlphaSlider, TitlePageRange
from ..fileselect import TitleRFilenameCombo
from ...tablet import TabletConnection
from ...config import RemassConfig, abbreviate_user
from ...filesystem import RDocument


class ExportForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Back'
    def __init__(self, cfg: RemassConfig, connection: TabletConnection, *args, **kwargs):
        self._cfg = cfg
        self._connection = connection
        self.fs_root, self.fs_trash, self.fs_dirents = self._connection.get_filesystem()
        self.export_thread = None
        self.is_exporting = False
        # As long as the user has not manually set a local output file name, we
        # keep suggesting a suitable filename based on the selected (remote) notebook
        self.auto_replace_local_filename = True  # Flag indicating if we're still allowed to auto-replace
        self.prev_auto_replaced_filename = None  # Needed because a widget's when_value_changed is also triggered if the user just skips over the widget
        self.notification_txt = ''
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self._to_main()

    def create(self, *args, **kwargs):
        super().create(*args, **kwargs)
        self.keypress_timeout = 2
        self.add_handlers({
            "^X": self.exit_application,
            "^B": self._to_main,
            "^S": self._start_export
        })
        self.add(nps.Textfield, value="Files:", editable=False, color='STANDOUT')
        self.select_tablet = self.add(
            TitleRFilenameCombo, name="reMarkable Notebook", label=True,
            when_value_edited_cb=self._on_remote_file_selected,
            rm_dirents=self.fs_dirents, select_dir=False, relx=4,
            begin_entry_at=24)
        self.select_local = self.add(
            TitleCustomFilenameCombo, name="Output PDF",
            when_value_edited_cb=self._on_local_file_selected,
            value=None, select_dir=False,
            label=True, must_exist=False, relx=4,
            confirm_if_exists=True, begin_entry_at=24)
        add_empty_row(self)

        self.add(
            nps.Textfield, value="Rendering Options:",
            editable=False, color='STANDOUT')
        self.rendering_pages = self.add(
            TitlePageRange, name='Pages to Export', value='*',
            relx=4, begin_entry_at=24)
        self.add(
            nps.Textfield,
            value="Examples: * (all), 1-3 (range), 5- (until last), -2 (second-to-last), -5- (last 5 pages)",
            editable=False, relx=9)
        self.rendering_template_alpha = self.add(
            TitleAlphaSlider, name='Template Alpha', value=3,
            begin_entry_at=24, relx=4)
        self.rendering_expand_pages = self.add(
            nps.RoundCheckBox, name='Expand Pages to rM View',
            value=True, relx=4)
        # self.rendering_only_annotated = self.add(nps.RoundCheckBox, name='Only Annotated Pages', value=False, relx=4)
        self.rendering_png = self.add(
            nps.RoundCheckBox, name='Convert to PNG', value=False, relx=4)
        self.rendering_dpi = self.add(
            nps.TitleText, name="PNG Quality (DPI)", value='300',
            relx=4, begin_entry_at=24)
        add_empty_row(self)

        self.btn_start = self.add(
            nps.ButtonPress, name='[Start Export]', relx=3,
            when_pressed_function=self._start_export)
        add_empty_row(self)

        self.btn_open_folder = self.add(
            nps.ButtonPress, name='[Open Output Folder]', relx=3,
            when_pressed_function=self._open_folder)
        self.btn_open_pdf = self.add(
            nps.ButtonPress, name='[Open PDF]', relx=3,
            when_pressed_function=self._open_pdf)
        add_empty_row(self)

        screen_height, _ = self.widget_useable_space()  # This does NOT include the already created widgets!
        for i in range(screen_height - 22):
            add_empty_row(self)
        self.progress_bar = self.add(
            ProgressBarBox, name='Export Progress', lowest=0,
            step=1, out_of=100, label=True, value=0, max_height=3)
        self._toggle_widgets(True)
    
    def while_waiting(self):
        if not self.is_exporting and len(self.notification_txt) > 0:
            nps.notify_confirm(self.notification_txt, title="Info", editw=1)
            self.notification_txt = ''

    def _on_remote_file_selected(self):
        if self.auto_replace_local_filename:
            if self.select_tablet.value is None:
                self.select_local.value = None
            else:
                fn = os.path.join(
                    abbreviate_user(self._cfg.export_dir),
                    safe_filename(self.select_tablet.value.visible_name) + '.pdf')
                self.select_local.value = fn
                self.prev_auto_replaced_filename = fn
            self.select_local.display()
            self._toggle_open_buttons()

    def _on_local_file_selected(self):
        if (self.select_local.value is not None) and (self.select_local.value != self.prev_auto_replaced_filename):
            self.auto_replace_local_filename = False
        self._toggle_open_buttons()

    def _start_export(self, *args, **kwargs):
        if self.is_exporting:
            return False
        # Check if the user selected input and destination
        if (self.select_tablet.value is None) or (self.select_tablet.value.dirent_type != RDocument.dirent_type):
            nps.notify_confirm(
                "You must select a notebook to export!",
                title='Error', form_color='CAUTION', editw=1)
            return False
        if self.select_local.filename is None:
            nps.notify_confirm(
                "You must select an output file!",
                title='Error', form_color='CAUTION', editw=1)
            return False
        # Parse page range input
        pages = self.rendering_pages.pages
        if len(pages) == 0:
            nps.notify_confirm(
                "You must enter a valid page range value.",
                title='Error', form_color='CAUTION', editw=1)
            return False
        # Parse DPI input
        try:
            dpi = int(self.rendering_dpi.value)
        except ValueError:
            nps.notify_confirm(
                "You must enter a valid (integer) DPI value.",
                title='Error', form_color='CAUTION', editw=1)
            return False
        # Reset progress bar
        self._rendering_progress_callback(0)
        if nps.notify_ok_cancel(
                'Do you really want to export:\n'
                f"    '{self.select_tablet.value.hierarchy_name}'\nto\n"
                f"    '{abbreviate_user(self.select_local.value)}'?"
                '\n------------------------------------------------------\n'
                'This form will be >locked< until completion.',
                title='Confirmation', editw=1):  # Select 'cancel' by default (to prevent premature export start)
            # Disable all inputs
            self._toggle_widgets(False)
            self.is_exporting = True
            self.export_thread = threading.Thread(
                target=self._export_blocking,
                args=(self.select_tablet.value, self.select_local.filename,
                    self.rendering_template_alpha.alpha,
                    self.rendering_expand_pages.value,
                    pages, self.rendering_png.value, dpi))
            self.export_thread.start()
        return True

    def _open_pdf(self, *args, **kwargs):
        fname = self.select_local.filename
        if fname is None or not os.path.exists(fname):
            nps.notify_confirm(
                'Nothing exported so far.', title='Error',
                form_color='CAUTION', editw=1)
        else:
            open_with_default_application(fname)

    def _open_folder(self, *args, **kwargs):
        folder = os.path.dirname(self.select_local.filename)
        if (folder is None) or (not os.path.exists(folder)):
            return
        else:
            open_with_default_application(folder)

    def _toggle_open_buttons(self, editable=True):
        file_nonexisting = self.select_local.filename is None or\
                           not os.path.exists(self.select_local.filename)
        folder_nonexisting = self.select_local.filename is None or\
                             not os.path.exists(os.path.dirname(self.select_local.filename))
                          
        self.btn_open_folder.editable = editable
        self.btn_open_folder.hidden = folder_nonexisting
        self.btn_open_folder.display()

        self.btn_open_pdf.editable = editable
        self.btn_open_pdf.hidden = file_nonexisting
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
        self._toggle_open_buttons(editable)
        # The form button will only be added (and removed) within the
        # base class' edit() method
        if hasattr(self, '_added_buttons'):
            self._added_buttons['ok_button'].editable = editable
            self._added_buttons['ok_button'].display()

    def _export_blocking(
            self, rm_file, output_filename, alpha, expand_pages,
            pages, export_png, dpi):
        self._connection.render_document(
            rm_file, output_filename, self._rendering_progress_callback,
            template_alpha=alpha, expand_pages=expand_pages,
            #  only_annotated=self.rendering_only_annotated.value
            page_selection=pages,
            template_path=self._cfg.template_backup_dir)
        if export_png:
            output_folder = os.path.dirname(output_filename)
            notification_suffix = '\n------------------------------------------------------\n'\
                f"\nPNGs have been exported to\n"\
                f"  '{abbreviate_user(output_folder)}'"
            fname = os.path.splitext(os.path.basename(output_filename))[0]
            fmt = 'png'
            _ = convert_from_path(
                output_filename, output_folder=output_folder,
                dpi=dpi, fmt=fmt, paths_only=True,
                single_file=False, thread_count=4,
                output_file=counter_generator(fname + '-', padding_goal=4))
        else:
            notification_suffix = ''
        self.notification_txt = f"Successfully exported\n  '{rm_file.hierarchy_name}'\nto\n"\
                                f"  '{abbreviate_user(output_filename)}'{notification_suffix}"
        self.is_exporting = False
        # Re-enable all widgets & notify the user (as we blocked all user 
        # inputs, this works from within this export thread, too)
        self._toggle_widgets(True)

    def _rendering_progress_callback(self, percentage):
        self.progress_bar.value = percentage
        self.progress_bar.display()

    def exit_application(self, *args, **kwargs):
        if self.is_exporting:
            return
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()

    def _to_main(self, *args, **kwargs):
        if self.is_exporting:
            return
        self.parentApp.setNextForm('MAIN')
        self.editing = False
        self.parentApp.switchFormNow()
