# gui: the desktop app over porter (docs/ARCHITECTURE.md). It runs `python -m porter …` and draws what the commands print (JSON); it holds no pipeline logic of its own.


def fatal(msg):   # WR-03: a start-up failure in a window (packaging/nx2android.py): a double-clicked bundle has no console to show a traceback in
    from PySide6.QtWidgets import QApplication, QMessageBox
    keep = QApplication.instance() or QApplication([])   # held: a QMessageBox needs a live QApplication
    QMessageBox.critical(None, 'nx2android', msg.removeprefix('[RED] '))
