# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Compatibility entry for the offline Qt desktop preview."""
from pathlib import Path
import tempfile
from qt_preview import create_preview,create_application,Settings

if __name__=='__main__':
    app = create_application()
    with tempfile.TemporaryDirectory() as directory:
        gui = create_preview(Settings(str(Path(directory)/'settings.json')))
        gui.mainloop()
