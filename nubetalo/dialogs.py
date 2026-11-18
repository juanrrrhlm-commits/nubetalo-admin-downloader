from dataclasses import replace
from pathlib import Path
import os
import sys
from urllib.parse import urlsplit, urlunsplit
from PySide6.QtCore import Qt, QTime, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFileDialog, QDialogButtonBox, QMessageBox, QTabWidget, QWidget,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QTimeEdit, QTreeWidget, QTreeWidgetItem, QHeaderView)
from .domain import APP_NAME, DONATE_URL
from .i18n import translate, status_text, error_text
from .theme import size_text, assets_dir


def button(text, callback, layout, primary=False):
    result = QPushButton(text)
    if primary:
        result.setObjectName('primary')
    result.clicked.connect(callback)
    layout.addWidget(result)
    return result


def startup_command():
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}" --background'
    return f'"{sys.executable}" "{Path(__file__).resolve().parent.parent / "main.py"}" --background'


def startup_enabled():
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            return winreg.QueryValueEx(key, APP_NAME)[0] == startup_command()
    except OSError:
        return False


def set_startup(enabled):
    if os.name != 'nt':
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


class RateInput(QWidget):
    def __init__(self, value, tr):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(0, 800000)
        self.spin.setDecimals(3)
        self.spin.setSpecialValueText(tr('Sin límite'))
        self.spin.setValue(value / 1e6)
        self.unit = QComboBox()
        self.unit.addItems(['MB/s', 'Mbps'])
        self.previous = 'MB/s'
        self.unit.currentTextChanged.connect(self.convert)
        row.addWidget(self.spin, 1)
        row.addWidget(self.unit)

    def convert(self, unit):
        value = self.spin.value()
        self.spin.setValue(value * 8 if unit == 'Mbps' else value / 8)
        self.previous = unit

    def bytes_per_second(self):
        return int(self.spin.value() * (125000 if self.unit.currentText() == 'Mbps' else 1000000))


class AddDialog(QDialog):
    def __init__(self, parent, folder):
        super().__init__(parent)
        self.tr = lambda s: translate(s, parent.controller.settings.language)
        self.setWindowTitle(self.tr('Añadir descarga'))
        self.resize(610, 440)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(QLabel(self.tr('Enlaces o magnet, uno por línea')))
        self.links = QTextEdit()
        self.links.setAcceptRichText(False)
        self.links.setPlaceholderText('https://…\nmagnet:?xt=…')
        self.links.setAccessibleName(self.tr('Enlaces o magnet, uno por línea'))
        layout.addWidget(self.links)
        browse = QHBoxLayout()
        button(self.tr('Abrir torrent'), self.pick_torrent, browse)
        browse.addStretch()
        layout.addLayout(browse)
        form = QFormLayout()
        self.folder = QLineEdit(folder)
        row = QHBoxLayout()
        row.addWidget(self.folder)
        button(self.tr('Elegir'), self.pick_folder, row)
        form.addRow(self.tr('Carpeta de destino'), row)
        self.name, self.checksum = QLineEdit(), QLineEdit()
        self.name.setMaxLength(220)
        self.checksum.setMaxLength(64)
        form.addRow(self.tr('Nombre del archivo (un solo enlace)'), self.name)
        form.addRow(self.tr('SHA-256 opcional (un solo enlace)'), self.checksum)
        layout.addLayout(form)
        note = QLabel(self.tr('Los torrents comparten partes con otros usuarios mientras descargan.'))
        note.setWordWrap(True)
        note.setObjectName('muted')
        layout.addWidget(note)
        buttons = QHBoxLayout()
        buttons.addStretch()
        button(self.tr('Cancelar'), self.reject, buttons)
        button(self.tr('Añadir descarga'), self.accept, buttons, True)
        layout.addLayout(buttons)

    def pick_torrent(self):
        files, _ = QFileDialog.getOpenFileNames(self, self.tr('Abrir torrent'), '', 'BitTorrent (*.torrent)')
        if files:
            self.links.append('\n'.join(files))

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr('Carpeta de destino'), self.folder.text())
        if folder:
            self.folder.setText(folder)


class SelectDialog(QDialog):
    def __init__(self, parent, files):
        super().__init__(parent)
        self.tr = lambda s: translate(s, parent.controller.settings.language)
        self.setWindowTitle(self.tr('Seleccionar archivos'))
        self.resize(670, 430)
        layout = QVBoxLayout(self)
        note = QLabel(self.tr('Los torrents comparten partes con otros usuarios mientras descargan.'))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([self.tr('Archivo'), self.tr('Tamaño'), self.tr('Prioridad')])
        self.priorities = {}
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for entry in files:
            if entry['pad']:
                continue
            item = QTreeWidgetItem([entry['name'], size_text(entry['size'])])
            item.setData(0, Qt.ItemDataRole.UserRole, entry['index'])
            item.setCheckState(0, Qt.CheckState.Checked)
            self.tree.addTopLevelItem(item)
            priority = QComboBox()
            for label, value in [('Baja', 1), ('Normal', 4), ('Alta', 7)]:
                priority.addItem(self.tr(label), value)
            priority.setCurrentIndex(1)
            self.tree.setItemWidget(item, 2, priority)
            self.priorities[str(entry['index'])] = priority
        layout.addWidget(self.tree)
        controls = QHBoxLayout()
        button(self.tr('Todos'), lambda: self.check_all(True), controls)
        button(self.tr('Ninguno'), lambda: self.check_all(False), controls)
        controls.addStretch()
        button(self.tr('Cancelar'), self.reject, controls)
        button(self.tr('Descargar'), self.confirm, controls, True)
        layout.addLayout(controls)

    def check_all(self, checked):
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def selected(self):
        return [self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                for i in range(self.tree.topLevelItemCount())
                if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked]

    def confirm(self):
        if not self.selected():
            QMessageBox.information(self, self.tr('Aviso'), self.tr('Selecciona al menos un archivo.'))
            return
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.config = replace(parent.controller.settings)
        self.tr = lambda s: translate(s, self.config.language)
        self.setWindowTitle(self.tr('Ajustes'))
        self.resize(730, 460)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        def page(title):
            widget = QWidget()
            form = QFormLayout(widget)
            form.setContentsMargins(20, 22, 20, 20)
            form.setSpacing(16)
            tabs.addTab(widget, self.tr(title))
            return form

        def integer(value, low, high):
            box = QSpinBox()
            box.setRange(low, high)
            box.setValue(value)
            return box

        def rate(value):
            return RateInput(value, self.tr)

        form = page('Descargas')
        self.folder = QLineEdit(self.config.folder)
        row = QHBoxLayout()
        row.addWidget(self.folder)
        button(self.tr('Elegir'), self.pick_folder, row)
        form.addRow(self.tr('Carpeta de destino'), row)
        self.active = integer(self.config.max_active, 1, 20)
        self.connections = integer(self.config.connections, 1, 4)
        form.addRow(self.tr('Descargas simultáneas'), self.active)
        form.addRow(self.tr('Conexiones por servidor'), self.connections)
        form = page('Red')
        self.down, self.up = rate(self.config.download_limit), rate(self.config.upload_limit)
        form.addRow(self.tr('Límite de descarga'), self.down)
        form.addRow(self.tr('Límite de subida'), self.up)
        conversion = QLabel('1 MB/s = 8 Mbps\n' + self.tr('0 = sin límite'))
        conversion.setObjectName('muted')
        form.addRow(conversion)
        form = page('Torrents')
        self.seed = QCheckBox(self.tr('Compartir al terminar'))
        self.seed.setChecked(self.config.seed_enabled)
        self.ratio = QDoubleSpinBox()
        self.ratio.setRange(.01, 100)
        self.ratio.setValue(self.config.seed_ratio)
        self.minutes = integer(self.config.seed_minutes, 0, 10080)
        form.addRow(self.seed)
        form.addRow(self.tr('Ratio máximo'), self.ratio)
        form.addRow(self.tr('Minutos compartiendo'), self.minutes)
        form.addRow(QLabel(self.tr('Detener al alcanzar el primero de los límites.')))
        form = page('Horarios')
        self.scheduled = QCheckBox(self.tr('Descargar solo durante este horario'))
        self.scheduled.setChecked(self.config.schedule_enabled)
        form.addRow(self.scheduled)

        def times(start, end):
            row = QHBoxLayout()
            a, b = QTimeEdit(QTime.fromString(start, 'HH:mm')), QTimeEdit(QTime.fromString(end, 'HH:mm'))
            a.setDisplayFormat('HH:mm')
            b.setDisplayFormat('HH:mm')
            row.addWidget(QLabel(self.tr('Desde')))
            row.addWidget(a)
            row.addWidget(QLabel(self.tr('Hasta')))
            row.addWidget(b)
            return row, a, b

        row, self.start, self.end = times(self.config.schedule_start, self.config.schedule_end)
        form.addRow(row)
        form.addRow(QLabel(self.tr('Misma hora de inicio y fin = todo el día.')))
        self.alternate = rate(self.config.alternate_limit)
        form.addRow(self.tr('Límite alternativo'), self.alternate)
        row, self.alt_start, self.alt_end = times(self.config.alternate_start, self.config.alternate_end)
        form.addRow(row)
        form = page('Apariencia')
        self.language = QComboBox()
        self.language.addItem('Español', 'es')
        self.language.addItem('English', 'en')
        self.language.setCurrentIndex(self.config.language == 'en')
        self.tray = QCheckBox(self.tr('Cerrar minimiza a la bandeja'))
        self.tray.setChecked(self.config.minimize_tray)
        self.startup = QCheckBox(self.tr('Iniciar con Windows'))
        self.startup.setChecked(startup_enabled())
        form.addRow(self.tr('Idioma'), self.language)
        form.addRow(self.tray)
        form.addRow(self.startup)
        self.completion_sound = QCheckBox(self.tr('Sonido al terminar una descarga'))
        self.completion_sound.setChecked(self.config.completion_sound)
        self.completion_notice = QCheckBox(self.tr('Aviso flotante al terminar una descarga'))
        self.completion_notice.setChecked(self.config.completion_notice)
        form.addRow(self.completion_sound)
        form.addRow(self.completion_notice)
        form = page('Soporte')
        label = QLabel(APP_NAME + '\n0.3.0\n\n' + self.tr('Aplicación gratuita, sin anuncios ni cuentas.'))
        label.setWordWrap(True)
        form.addRow(label)
        donate = QPushButton(self.tr('Donar'))
        donate.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DONATE_URL)))
        form.addRow(donate)
        support = QPushButton(self.tr('Soporte'))
        support.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('mailto:juanrrrhlm@gmail.com?subject=Nubetalo%20Admin%20Downloader%20Soporte')))
        form.addRow(support)
        legal = QPushButton(self.tr('Privacidad y licencias'))
        legal.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(assets_dir() / 'legal.html'))))
        form.addRow(legal)
        buttons = QHBoxLayout()
        buttons.addStretch()
        button(self.tr('Cancelar'), self.reject, buttons)
        button(self.tr('Guardar'), self.confirm, buttons, True)
        layout.addLayout(buttons)

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr('Carpeta de destino'), self.folder.text())
        if folder:
            self.folder.setText(folder)

    def confirm(self):
        if not self.folder.text().strip():
            return
        self.config.folder = self.folder.text().strip()
        self.config.max_active, self.config.connections = self.active.value(), self.connections.value()
        self.config.download_limit, self.config.upload_limit = self.down.bytes_per_second(), self.up.bytes_per_second()
        self.config.seed_enabled, self.config.seed_ratio, self.config.seed_minutes = self.seed.isChecked(), self.ratio.value(), self.minutes.value()
        self.config.schedule_enabled = self.scheduled.isChecked()
        self.config.schedule_start, self.config.schedule_end = self.start.time().toString('HH:mm'), self.end.time().toString('HH:mm')
        self.config.alternate_limit = self.alternate.bytes_per_second()
        self.config.alternate_start, self.config.alternate_end = self.alt_start.time().toString('HH:mm'), self.alt_end.time().toString('HH:mm')
        self.config.language, self.config.minimize_tray = self.language.currentData(), self.tray.isChecked()
        self.config.completion_sound, self.config.completion_notice = self.completion_sound.isChecked(), self.completion_notice.isChecked()
        try:
            set_startup(self.startup.isChecked())
        except OSError:
            QMessageBox.warning(self, self.tr('Error'), 'No se pudo cambiar el inicio con Windows / Cannot update startup')
            return
        self.accept()


class DetailsDialog(QDialog):
    def __init__(self, parent, task):
        super().__init__(parent)
        self.task = task
        self.controller = parent.controller
        self.tr = lambda s: translate(s, self.controller.settings.language)
        self.setWindowTitle(self.tr('Detalles'))
        self.resize(600, 380)
        layout = QVBoxLayout(self)
        title = QLabel(task.name)
        title.setObjectName('heading')
        title.setWordWrap(True)
        layout.addWidget(title)
        form = QFormLayout()
        source = task.source
        if task.kind == 'http':
            p = urlsplit(source)
            source = urlunsplit((p.scheme, p.netloc, p.path, '', ''))
        for label, value in [('Origen', source), ('Carpeta', task.destination), ('Estado', status_text(task.status, self.controller.settings.language)),
                             ('Pares', str(task.peers)), ('Subida', size_text(task.upload_speed) + '/s')]:
            field = QLineEdit(value)
            field.setReadOnly(True)
            form.addRow(self.tr(label), field)
        self.priority = QComboBox()
        self.priority.addItems([self.tr(x) for x in ('Baja', 'Normal', 'Alta')])
        self.priority.setCurrentIndex(task.priority)
        self.limit = RateInput(task.limit, self.tr)
        form.addRow(self.tr('Prioridad'), self.priority)
        form.addRow(self.tr('Límite de descarga'), self.limit)
        layout.addLayout(form)
        if task.error:
            error = QLabel(error_text(task.error, self.controller.settings.language))
            error.setWordWrap(True)
            layout.addWidget(error)
        layout.addWidget(QLabel(self.tr('Huella verificada' if task.verified else 'Sin huella de referencia')))
        controls = QHBoxLayout()
        if task.kind == 'http':
            button(self.tr('Cambiar enlace'), self.replace_link, controls)
        controls.addStretch()
        button(self.tr('Guardar'), self.confirm, controls, True)
        layout.addLayout(controls)

    def replace_link(self):
        from PySide6.QtWidgets import QInputDialog
        url, ok = QInputDialog.getText(self, self.tr('Cambiar enlace'), self.tr('Nuevo enlace'))
        if ok:
            try:
                self.controller.replace_url(self.task.id, url.strip())
            except ValueError as exc:
                QMessageBox.warning(self, self.tr('Error'), str(exc))

    def confirm(self):
        priority = self.priority.currentIndex()
        if priority != 1 and not self.controller.settings.download_limit:
            total = self.parent().request_bandwidth()
            if total is None:
                return
            self.controller.settings.download_limit = total
        self.task.priority, self.task.limit = priority, self.limit.bytes_per_second()
        if priority != 1:
            self.controller.settings.bandwidth_mode = 'priority'
            self.controller.apply_settings(self.controller.settings)
        self.controller.store.save_task(self.task)
        self.accept()
