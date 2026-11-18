EN = {'Repartir': 'Share equally', 'Priorizar': 'Prioritize', 'Libre': 'Unrestricted', 'Velocidad disponible': 'Available speed', 'Velocidad total para repartir (MB/s). Usa la velocidad de descarga, no la de subida.': 'Total download speed to share (MB/s). Enter download speed, not upload speed.', 'Repartir la velocidad configurada entre las descargas activas.': 'Share the configured speed equally between active downloads.', 'Dar cuatro veces más velocidad a las seleccionadas, dentro del límite total.': 'Give selected downloads four times the share, within the total limit.', 'Quitar el límite general y las preferencias. Se conservan los horarios y límites por descarga.': 'Remove the general limit and preferences. Schedules and per-download limits remain.'}
EN.update({
    'Privacidad y licencias': 'Privacy and licenses',
    'Sonido al terminar una descarga': 'Play sound when a download completes',
    'Aviso flotante al terminar una descarga': 'Show a floating completion notification',
    'Esperando servidor': 'Waiting for server',
    'Añadir descarga': 'Add download', 'Pausar todo': 'Pause all', 'Continuar todo': 'Resume all',
    'Donar': 'Donate', 'Ajustes': 'Settings', 'Todas': 'All downloads', 'Activas': 'Active',
    'En espera': 'Waiting', 'Completadas': 'Completed', 'Con problemas': 'Needs attention',
    'Buscar descargas': 'Search downloads', 'Nombre': 'Name', 'Progreso': 'Progress',
    'Tamaño': 'Size', 'Velocidad': 'Speed', 'Estado': 'Status', 'Tiempo restante': 'Time left',
    'Pausar': 'Pause', 'Continuar': 'Resume', 'Detalles': 'Details', 'Quitar de la lista': 'Remove from list',
    'Abrir carpeta': 'Open folder', 'Seleccionar archivos': 'Select files', 'Reiniciar descarga': 'Restart download',
    'Tus descargas, en un solo lugar': 'Your downloads, in one place',
    'Pega un enlace o arrastra un archivo torrent para empezar.': 'Paste a link or drop a torrent file to get started.',
    'Sin límite': 'Unlimited', 'Límite personalizado': 'Custom limit', 'Red': 'Network', 'Descargas': 'Downloads',
    'Acerca de': 'About', 'Soporte': 'Support', 'Salir': 'Quit', 'Mostrar': 'Show',
    'Carpeta de destino': 'Destination folder', 'Elegir': 'Browse', 'Enlaces o magnet, uno por línea': 'Links or magnets, one per line',
    'Abrir torrent': 'Open torrent', 'Nombre del archivo (un solo enlace)': 'Filename (single link)',
    'SHA-256 opcional (un solo enlace)': 'Optional SHA-256 (single link)',
    'Cancelar': 'Cancel', 'Guardar': 'Save', 'Descargar': 'Download', 'Archivo': 'File',
    'Los torrents comparten partes con otros usuarios mientras descargan.': 'Torrents share pieces with other peers while downloading.',
    'Descargas simultáneas': 'Concurrent downloads', 'Conexiones por servidor': 'Connections per server',
    'Límite de descarga': 'Download limit', 'Límite de subida': 'Upload limit', '0 = sin límite': '0 = unlimited',
    'Torrents': 'Torrents', 'Compartir al terminar': 'Seed after completion', 'Ratio máximo': 'Maximum ratio',
    'Minutos compartiendo': 'Minutes seeding', 'Detener al alcanzar el primero de los límites.': 'Stop when the first limit is reached.',
    'Horarios': 'Schedule', 'Descargar solo durante este horario': 'Download only during this window',
    'Desde': 'From', 'Hasta': 'Until', 'Límite alternativo': 'Alternate limit',
    'Misma hora de inicio y fin = todo el día.': 'Same start and end = all day.',
    'Apariencia': 'Appearance', 'Idioma': 'Language', 'Cerrar minimiza a la bandeja': 'Closing minimizes to tray',
    'Iniciar con Windows': 'Start with Windows', 'Aplicación gratuita, sin anuncios ni cuentas.': 'Free app, no ads or accounts.',
    'Prioridad': 'Priority', 'Baja': 'Low', 'Normal': 'Normal', 'Alta': 'High', 'Carpeta': 'Folder',
    'Huella verificada': 'Checksum verified', 'Sin huella de referencia': 'No reference checksum',
    'Cambiar enlace': 'Replace link', 'Nuevo enlace': 'New link', 'Aviso': 'Notice', 'Error': 'Error',
    'Reiniciar descarta solo el progreso temporal de esta descarga. ¿Continuar?': 'Restart discards only temporary progress for this download. Continue?',
    'Quitar conserva los archivos descargados y temporales.': 'Removing keeps downloaded and temporary files.',
    'Sin coincidencias': 'No matching downloads', 'Listo': 'Ready', 'Descarga terminada': 'Download completed',
    'Selecciona al menos un archivo.': 'Select at least one file.', 'Todos': 'All', 'Ninguno': 'None',
    'Sin metadatos todavía; inténtalo cuando estén disponibles.': 'Metadata is not available yet; try again when ready.',
    'Pares': 'Peers', 'Subida': 'Upload', 'Origen': 'Source',
})
STATUS = {
    'queued': ('En cola', 'Queued'), 'downloading': ('Descargando', 'Downloading'),
    'paused': ('Pausada', 'Paused'), 'waiting': ('Esperando conexión', 'Waiting for connection'),
    'completed': ('Completada', 'Completed'), 'checking': ('Verificando', 'Checking'),
    'error': ('Requiere atención', 'Needs attention'), 'restart_required': ('Requiere reinicio', 'Restart required'),
    'seeding': ('Compartiendo', 'Seeding'), 'metadata': ('Obteniendo metadatos', 'Fetching metadata'),
    'selection': ('Elegir archivos', 'Choose files'),
}


def translate(text, language):
    return EN.get(text, text) if language == 'en' else text


def status_text(status, language):
    return STATUS.get(status, (status, status))[language == 'en']


def error_text(text, language):
    parts = text.split(' / ', 1)
    return parts[-1] if language == 'en' else parts[0]
