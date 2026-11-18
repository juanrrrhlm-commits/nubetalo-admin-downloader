# Seguridad

Reporta problemas de forma privada a **juanrrrhlm@gmail.com**, asunto
`Nubetalo Admin Downloader — Seguridad`. No adjuntes tu cola, URLs privadas,
credenciales, códigos ni archivos personales. Describe la versión, el impacto y
pasos mínimos con datos de ejemplo. No publiques detalles de explotación en issues.

La versión mantenida actualmente es **0.3.x**. Se recomienda actualizar versiones
anteriores; los avisos y correcciones se publicarán en GitHub Releases.

## Protecciones

- Sin API remota de control; comunicación entre aperturas mediante pipe del usuario.
- HTTPS con certificados verificados y bloqueo de redirecciones a HTTP.
- Rutas de destino comprobadas, sin sobrescribir archivos completos por HTTP.
- Reanudación con validadores y rangos comprobados; hashes cuando están disponibles.
- Datos de cola, configuración y copias internas de torrents/resume protegidos mediante
  DPAPI de Windows para el usuario actual, sin claves incrustadas.
- Sin ejecución automática ni extracción automática de archivos descargados.

## Límites

DPAPI no protege frente a un atacante que ya ejecute código como el mismo usuario o
administrador, ni cifra los archivos que eliges descargar. El estado no es portable
entre usuarios/equipos sin conservar las claves del perfil Windows. No abras la base
de datos migrada con versiones anteriores.

Los torrents de entrada y los archivos descargados que guardas fuera de la carpeta
de estado no se cifran. Copias antiguas, historial del navegador, copias del sistema
y datos conservados por proveedores quedan fuera del borrado/migración de la app.

La auditoría es acotada y no equivale a una garantía de ausencia de vulnerabilidades.
Las bibliotecas nativas también requieren seguimiento; consultar docs/SECURITY_AUDIT.md.
