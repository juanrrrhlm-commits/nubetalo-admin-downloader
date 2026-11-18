from pathlib import Path
import argparse
import sys
import sqlite3
from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from nubetalo.domain import APP_NAME, data_directory
from nubetalo.controller import Controller
from nubetalo.theme import apply_theme
from nubetalo.ui import MainWindow
from nubetalo.ipc import InstanceServer, forward


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument('sources', nargs='*')
    parser.add_argument('--data-dir', type=Path, default=data_directory())
    parser.add_argument('--background', action='store_true')
    parser.add_argument('--smoke-test', action='store_true')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName('Nubetalo')
    apply_theme(app)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(args.data_dir / 'instance.lock'))
    if not lock.tryLock(100):
        if forward(args.data_dir, args.sources):
            return 0
        QMessageBox.information(None, APP_NAME, 'La aplicación ya está abierta. Revisa la bandeja del sistema.\nThe app is already running; check the system tray.')
        return 1
    try:
        controller = Controller(args.data_dir)
    except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError):
        QMessageBox.warning(None, APP_NAME,
            'No se pudo abrir la cola protegida. Usa el mismo usuario de Windows o contacta con soporte.\n'
            'Cannot open the protected queue. Use the same Windows user or contact support.')
        lock.unlock()
        return 1
    window = MainWindow(controller)
    def receive_sources(sources):
        window.showNormal()
        window.raise_()
        window.activateWindow()
        if sources:
            window.add_sources(sources)
    ipc = InstanceServer(args.data_dir, receive_sources)
    if not args.background or args.smoke_test:
        window.show()
    if args.sources:
        QTimer.singleShot(0, lambda: window.add_sources(args.sources))
    if args.smoke_test:
        QTimer.singleShot(1800, lambda: window.grab().save(str(args.data_dir / 'smoke.png')))
        QTimer.singleShot(2200, window.quit)
    try:
        return app.exec()
    finally:
        controller.close()
        ipc.close()
        lock.unlock()


if __name__ == '__main__':
    sys.exit(main())
