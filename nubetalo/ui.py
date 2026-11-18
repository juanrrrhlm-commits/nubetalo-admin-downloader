from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QAction, QKeySequence, QShortcut, QColor
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel,
    QPushButton, QLineEdit, QTreeWidget, QTreeWidgetItem, QHeaderView, QMenu, QProgressBar,
    QSystemTrayIcon, QMessageBox, QDialog, QStackedWidget, QInputDialog, QStyle)
from .domain import APP_NAME, DONATE_URL
from .theme import assets_dir, size_text, eta_text, neon_glow
from .notices import server_notice_text
from .notifications import CompletionIsland, play_completion_sound
from .i18n import translate, status_text, error_text
from .dialogs import AddDialog, SettingsDialog, SelectDialog, DetailsDialog, button


class MainWindow(QMainWindow):
    def __init__(self, controller, start_timer=True):
        super().__init__()
        self.controller = controller
        self.filter_key = 'all'
        self.shutting_down = False
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(940, 570)
        self.resize(1160, 710)
        self.setAcceptDrops(True)
        self.setWindowIcon(QIcon(str(assets_dir() / 'logo.png')))
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.island = CompletionIsland(self)
        self.island.clicked.connect(self.show_from_notice)
        self.build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        if start_timer:
            self.timer.start(500)
            self.tray.show()
        self.refresh()

    def tr(self, text):
        return translate(text, self.controller.settings.language)

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName('toolbar')
        bar = QHBoxLayout(header)
        bar.setContentsMargins(22, 16, 22, 16)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(assets_dir() / 'logo.png')).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        bar.addWidget(logo)
        neon_glow(logo, 22, 150)
        brand = QLabel(APP_NAME)
        brand.setObjectName('brand')
        bar.addWidget(brand)
        bar.addStretch()
        add_button = button(self.tr('Añadir descarga'), self.add_dialog, bar, True)
        neon_glow(add_button, 18, 85)
        button(self.tr('Pausar todo'), self.pause_all, bar)
        donate = button(self.tr('Donar'), self.donate, bar)
        donate.setObjectName('donate')
        outer.addWidget(header)
        body = QHBoxLayout()
        body.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 24, 16, 18)
        side.setSpacing(5)
        section = QLabel(self.tr('Descargas'))
        section.setObjectName('muted')
        side.addWidget(section)
        side.addSpacing(10)
        self.filter_buttons = {}
        for key, text in [('all', 'Todas'), ('active', 'Activas'), ('waiting', 'En espera'), ('completed', 'Completadas'), ('error', 'Con problemas')]:
            b = button(self.tr(text), lambda checked=False, k=key: self.set_filter(k), side)
            b.setObjectName('filter')
            b.setCheckable(True)
            b.setChecked(key == self.filter_key)
            self.filter_buttons[key] = b
        side.addStretch()
        side.addWidget(QLabel(self.tr('Red')))
        self.limit_label = QLabel()
        self.limit_label.setObjectName('muted')
        self.limit_label.setWordWrap(True)
        side.addWidget(self.limit_label)
        button(self.tr('Límite personalizado'), self.settings_dialog, side)
        side.addSpacing(18)
        button(self.tr('Ajustes'), self.settings_dialog, side)
        body.addWidget(sidebar)
        content = QVBoxLayout()
        content.setContentsMargins(25, 24, 25, 16)
        content.setSpacing(18)
        titlebar = QHBoxLayout()
        title = QLabel(self.tr('Descargas'))
        title.setObjectName('heading')
        titlebar.addWidget(title)
        titlebar.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr('Buscar descargas'))
        self.search.setAccessibleName(self.tr('Buscar descargas'))
        self.search.setMaximumWidth(290)
        self.search.textChanged.connect(self.refresh)
        titlebar.addWidget(self.search)
        content.addLayout(titlebar)
        sharing = QHBoxLayout()
        sharing.setSpacing(8)
        self.policy_buttons = {}
        for mode, label in [('equal', 'Repartir'), ('priority', 'Priorizar'), ('free', 'Libre')]:
            control = button(self.tr(label), lambda checked=False, m=mode: self.change_bandwidth(m), sharing)
            control.setCheckable(True)
            control.setObjectName('policy')
            self.policy_buttons[mode] = control
            effect = neon_glow(control, 16, 115)
            effect.setEnabled(False)
        self.policy_buttons['equal'].setToolTip(self.tr('Repartir la velocidad configurada entre las descargas activas.'))
        self.policy_buttons['priority'].setToolTip(self.tr('Dar cuatro veces más velocidad a las seleccionadas, dentro del límite total.'))
        self.policy_buttons['free'].setToolTip(self.tr('Quitar el límite general y las preferencias. Se conservan los horarios y límites por descarga.'))
        self.budget_button = button('', self.edit_bandwidth, sharing)
        sharing.addStretch()
        content.addLayout(sharing)
        self.stack = QStackedWidget()
        self.table = QTreeWidget()
        self.table.setAccessibleName(self.tr('Descargas'))
        self.table.setHeaderLabels([self.tr(s) for s in ('Nombre', 'Progreso', 'Tamaño', 'Velocidad', 'Estado', 'Tiempo restante')])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, width in enumerate((0, 90, 90, 95, 175, 110)):
            if i:
                self.table.setColumnWidth(i, width)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)
        self.table.itemDoubleClicked.connect(lambda item, _: self.details())
        self.table.itemSelectionChanged.connect(self.update_actions)
        self.stack.addWidget(self.table)
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch()
        mark = QLabel('↓')
        mark.setStyleSheet('font-size: 68px; color: #57ff93;')
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(mark)
        self.empty_title = QLabel(self.tr('Tus descargas, en un solo lugar'))
        self.empty_title.setObjectName('emptyTitle')
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_title)
        self.empty_note = QLabel(self.tr('Pega un enlace o arrastra un archivo torrent para empezar.'))
        self.empty_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_note.setObjectName('muted')
        empty_layout.addWidget(self.empty_note)
        row = QHBoxLayout()
        row.addStretch()
        button(self.tr('Añadir descarga'), self.add_dialog, row, True)
        row.addStretch()
        empty_layout.addSpacing(20)
        empty_layout.addLayout(row)
        empty_layout.addStretch()
        self.stack.addWidget(empty)
        content.addWidget(self.stack, 1)
        controls = QHBoxLayout()
        self.resume_button = button(self.tr('Continuar'), self.resume_selected, controls)
        self.pause_button = button(self.tr('Pausar'), self.pause_selected, controls)
        self.details_button = button(self.tr('Detalles'), self.details, controls)
        controls.addStretch()
        self.folder_button = button(self.tr('Abrir carpeta'), self.open_folder, controls)
        content.addLayout(controls)
        footer = QHBoxLayout()
        self.traffic = QLabel()
        self.traffic.setObjectName('muted')
        footer.addWidget(self.traffic)
        footer.addStretch()
        version = QLabel('Nubetalo · 0.3.0')
        version.setObjectName('muted')
        footer.addWidget(version)
        content.addLayout(footer)
        body.addLayout(content, 1)
        outer.addLayout(body, 1)
        tray_menu = QMenu(self)
        for text, action in [('Mostrar', self.showNormal), ('Pausar todo', self.pause_all), ('Continuar todo', self.resume_all), ('Salir', self.quit)]:
            tray_menu.addAction(self.tr(text), action)
        self.tray.setContextMenu(tray_menu)
        QShortcut(QKeySequence('Ctrl+N'), central, self.add_dialog)
        QShortcut(QKeySequence('Ctrl+F'), central, self.search.setFocus)
        self.update_actions()

    def change_language(self, language):
        self.controller.settings.language = language
        self.controller.apply_settings(self.controller.settings)
        self.build_ui()
        self.refresh()

    def selected_ids(self):
        return [i.data(0, Qt.ItemDataRole.UserRole) for i in self.table.selectedItems()]

    def update_actions(self):
        selected = bool(self.table.selectedItems())
        for name in ('resume_button', 'pause_button', 'details_button', 'folder_button'):
            if hasattr(self, name):
                getattr(self, name).setEnabled(selected)
        if hasattr(self, 'policy_buttons'):
            self.policy_buttons['priority'].setEnabled(selected)

    def set_filter(self, key):
        self.filter_key = key
        for k, b in self.filter_buttons.items():
            b.setChecked(k == key)
        self.refresh()

    def matches(self, task):
        if self.search.text().casefold() not in task.name.casefold():
            return False
        return (self.filter_key == 'all' or self.filter_key == 'active' and task.status in ('downloading', 'seeding', 'checking', 'metadata')
                or self.filter_key == 'waiting' and task.status in ('paused', 'queued', 'waiting', 'selection')
                or self.filter_key == 'completed' and task.status == 'completed'
                or self.filter_key == 'error' and task.status in ('error', 'restart_required'))

    def refresh(self):
        selection = set(self.selected_ids())
        self.table.blockSignals(True)
        self.table.clear()
        for task in sorted(self.controller.tasks.values(), key=lambda t: t.added, reverse=True):
            if not self.matches(task):
                continue
            percent = int(task.done * 100 / task.total) if task.total else 0
            remaining = (task.total - task.done) / task.speed if task.speed and task.total else 0
            eta = eta_text(remaining, self.controller.settings.language) if task.status == 'downloading' else '—'
            preferred = self.controller.settings.bandwidth_mode == 'priority' and task.priority == 2
            state = self.tr('Esperando servidor') if task.status == 'waiting' and task.server_notice in ('http_429', 'http_503') else status_text(task.status, self.controller.settings.language)
            item = QTreeWidgetItem([('↑ ' if preferred else '') + (task.name or 'Torrent'), f'{percent} %' if task.total else '—', size_text(task.total) if task.total else '—',
                size_text(task.speed) + '/s' if task.speed else '—', state, eta])
            item.setData(0, Qt.ItemDataRole.UserRole, task.id)
            item.setToolTip(0, task.destination)
            item.setToolTip(4, error_text(task.error, self.controller.settings.language))
            notice = server_notice_text(task.server_notice, self.controller.settings.language)
            if notice and task.status not in ('completed', 'seeding'):
                item.setIcon(4, self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
                problem = error_text(task.error, self.controller.settings.language)
                item.setToolTip(4, notice + ('\n\n' + problem if problem else ''))
                item.setData(4, Qt.ItemDataRole.AccessibleDescriptionRole, notice)
            if preferred:
                item.setForeground(0, QColor('#57ff93'))
            self.table.addTopLevelItem(item)
            item.setSelected(task.id in selection)
        self.table.blockSignals(False)
        self.stack.setCurrentIndex(0 if self.table.topLevelItemCount() else 1)
        self.empty_title.setText(self.tr('Tus descargas, en un solo lugar' if not self.controller.tasks else 'Sin coincidencias'))
        self.limit_label.setText(self.tr('Sin límite') if not self.controller.settings.download_limit else size_text(self.controller.settings.download_limit) + '/s')
        for mode, control in self.policy_buttons.items():
            control.setChecked(self.controller.settings.bandwidth_mode == mode)
            control.graphicsEffect().setEnabled(control.isChecked())
        self.budget_button.setText(self.tr('Velocidad') + ': ' + (size_text(self.controller.settings.download_limit) + '/s' if self.controller.settings.download_limit else self.tr('Sin límite')))
        down = sum(t.speed for t in self.controller.tasks.values())
        up = sum(t.upload_speed for t in self.controller.tasks.values())
        self.traffic.setText(f'↓ {size_text(down)}/s     ↑ {size_text(up)}/s     ·     {len(self.controller.tasks)} ' + self.tr('Descargas').lower())
        self.update_actions()

    def request_bandwidth(self):
        value, accepted = QInputDialog.getDouble(self, self.tr('Velocidad disponible'),
            self.tr('Velocidad total para repartir (MB/s). Usa la velocidad de descarga, no la de subida.'),
            max(.01, self.controller.settings.download_limit / 1000000), .01, 100000, 2)
        return int(round(value * 1000000)) if accepted else None

    def edit_bandwidth(self):
        total = self.request_bandwidth()
        if total is not None:
            self.controller.settings.download_limit = total
            if self.controller.settings.bandwidth_mode == 'free':
                self.controller.settings.bandwidth_mode = 'equal'
            self.controller.apply_settings(self.controller.settings)
        self.refresh()

    def change_bandwidth(self, mode):
        ids = self.selected_ids()
        if mode == 'priority' and not ids:
            self.refresh()
            return
        total = None
        if mode != 'free' and not self.controller.settings.download_limit:
            total = self.request_bandwidth()
            if total is None:
                self.refresh()
                return
        self.controller.set_bandwidth_policy(mode, ids, total)
        self.refresh()

    def tick(self):
        try:
            finished = {task.id: task for task in self.controller.tick()
                        if task.status in ('completed', 'seeding') and not task.completion_notified}
            for task in finished.values():
                task.completion_notified = True
                self.controller.store.save_task(task)
            if finished:
                if self.controller.settings.completion_sound:
                    play_completion_sound()
                if self.controller.settings.completion_notice:
                    names = ', '.join(t.name for t in finished.values())
                    self.island.show_download(names, self.controller.settings.language, len(finished))
            self.refresh()
        except (OSError, ValueError, RuntimeError) as exc:
            self.timer.stop()
            QMessageBox.warning(self, self.tr('Error'), 'No se pudo actualizar la cola / Cannot update queue. ' + type(exc).__name__)

    def show_from_notice(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def add_dialog(self):
        dialog = AddDialog(self, self.controller.settings.folder)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            sources = [x.strip() for x in dialog.links.toPlainText().splitlines() if x.strip()]
            self.add_sources(sources, dialog.folder.text().strip(), dialog.name.text().strip() if len(sources) == 1 else '', dialog.checksum.text().strip() if len(sources) == 1 else '')

    def add_sources(self, sources, folder=None, name='', checksum=''):
        for source in sources:
            try:
                if source.startswith('magnet:?') or Path(source).suffix.lower() == '.torrent' and not source.startswith(('http:', 'https:')):
                    task = self.controller.add_torrent(source, folder or self.controller.settings.folder)
                    if self.controller.engine.files(task.id):
                        self.select_files(task.id)
                else:
                    self.controller.add_http(source, folder or self.controller.settings.folder, name, checksum)
            except (ValueError, OSError, RuntimeError) as exc:
                QMessageBox.warning(self, self.tr('Error'), error_text(str(exc), self.controller.settings.language))
        self.refresh()

    def select_files(self, task_id):
        files = self.controller.engine.files(task_id)
        if not files:
            QMessageBox.information(self, self.tr('Aviso'), self.tr('Sin metadatos todavía; inténtalo cuando estén disponibles.'))
            return
        dialog = SelectDialog(self, files)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.controller.select(task_id, dialog.selected(), {k: v.currentData() for k, v in dialog.priorities.items()})

    def settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.controller.apply_settings(dialog.config)
            self.build_ui()
            self.refresh()

    def pause_all(self):
        for task in self.controller.tasks.values():
            if task.status != 'completed':
                self.controller.pause(task.id)
        self.refresh()

    def resume_all(self):
        for task in self.controller.tasks.values():
            self.controller.resume(task.id)
        self.refresh()

    def pause_selected(self):
        for task_id in self.selected_ids():
            self.controller.pause(task_id)
        self.refresh()

    def resume_selected(self):
        for task_id in self.selected_ids():
            task = self.controller.tasks[task_id]
            if task.kind == 'torrent' and task.selected is None:
                if self.controller.engine.files(task_id):
                    self.select_files(task_id)
                else:
                    self.controller.resume(task_id)
            elif task.status == 'restart_required':
                self.restart(task_id)
            else:
                self.controller.resume(task_id)
        self.refresh()

    def details(self):
        ids = self.selected_ids()
        if ids:
            DetailsDialog(self, self.controller.tasks[ids[0]]).exec()

    def open_folder(self):
        ids = self.selected_ids()
        if ids:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.controller.tasks[ids[0]].destination))

    def donate(self):
        QDesktopServices.openUrl(QUrl(DONATE_URL))

    def restart(self, task_id):
        if QMessageBox.question(self, self.tr('Reiniciar descarga'), self.tr('Reiniciar descarta solo el progreso temporal de esta descarga. ¿Continuar?')) == QMessageBox.StandardButton.Yes:
            try:
                self.controller.restart(task_id)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, self.tr('Error'), str(exc))

    def remove_selected(self):
        if QMessageBox.question(self, self.tr('Quitar de la lista'), self.tr('Quitar conserva los archivos descargados y temporales.')) != QMessageBox.StandardButton.Yes:
            return
        for task_id in self.selected_ids():
            try:
                self.controller.remove(task_id)
            except ValueError as exc:
                QMessageBox.information(self, self.tr('Aviso'), str(exc))
        self.refresh()

    def context_menu(self, point):
        if not self.selected_ids():
            return
        menu = QMenu(self)
        for text, callback in [('Continuar', self.resume_selected), ('Pausar', self.pause_selected), ('Detalles', self.details), ('Abrir carpeta', self.open_folder)]:
            menu.addAction(self.tr(text), callback)
        menu.addSeparator()
        menu.addAction(self.tr('Quitar de la lista'), self.remove_selected)
        menu.exec(self.table.viewport().mapToGlobal(point))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        sources = ([u.toLocalFile() if u.isLocalFile() else u.toString() for u in event.mimeData().urls()]
                   if event.mimeData().hasUrls() else event.mimeData().text().splitlines())
        self.add_sources([s.strip() for s in sources if s.strip()])

    def closeEvent(self, event):
        if not self.shutting_down and self.controller.settings.minimize_tray and self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self.timer.stop()
            self.tray.hide()
            self.island.dismiss(animate=False)
            event.accept()

    def quit(self):
        self.shutting_down = True
        self.island.dismiss(animate=False)
        self.close()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
