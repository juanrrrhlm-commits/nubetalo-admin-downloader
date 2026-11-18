"""Explanations for observable server responses, with no speed-based guesses."""
MESSAGES = {
    'http_429': (
        'El servidor ha rechazado temporalmente más solicitudes (HTTP 429). La descarga esperará antes de reintentar; el progreso guardado se conserva.',
        'The server temporarily rejected further requests (HTTP 429). The download will wait before retrying; saved progress is preserved.'),
    'http_503': (
        'El servidor no está disponible temporalmente (HTTP 503). Se respetará el tiempo de espera que indique antes de reintentar.',
        'The server is temporarily unavailable (HTTP 503). Its requested waiting period will be respected before retrying.'),
    'ranges_ignored': (
        'El servidor ignora las solicitudes de descarga por partes. Este enlace se descarga con una sola conexión; no se puede acelerar añadiendo conexiones.',
        'The server ignores byte-range requests. This link uses a single connection; adding connections cannot speed it up.'),
    'no_ranges': (
        'El servidor indica que no admite descargas por partes. Se usa una sola conexión; la reanudación segura puede requerir reiniciar el archivo.',
        'The server states that byte ranges are unsupported. One connection is used; safe recovery may require restarting the file.'),
}


def server_notice_text(code, language='es'):
    return MESSAGES.get(code, ('', ''))[language == 'en']
