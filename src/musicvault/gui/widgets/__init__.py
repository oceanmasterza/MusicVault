"""GUI widget package."""

from musicvault.gui.widgets.desktop import copy_text_to_clipboard, open_path, reveal_in_explorer
from musicvault.gui.widgets.path_picker import PathPickerRow
from musicvault.gui.widgets.pipeline_flow import PipelineFlowWidget

__all__ = [
    "PathPickerRow",
    "PipelineFlowWidget",
    "copy_text_to_clipboard",
    "open_path",
    "reveal_in_explorer",
]
