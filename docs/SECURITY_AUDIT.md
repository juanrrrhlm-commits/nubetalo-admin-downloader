# Revisión de seguridad de 0.3.0

Fecha: 18 de noviembre de 2026. Evaluación acotada del cliente Windows, fuentes,
dependencias fijadas y empaquetado. No es certificación ni garantía de ausencia de fallos.

## Métodos

- Bandit1.9.4: análisis estático de código del cliente y arranque.
- detect-secrets1.5.0 con verificación de credenciales deshabilitada: revisión local.
- pip-audit2.10.1: consulta de paquetes/versiones al índice de avisos; no envío de código.
- Revisión manual de rutas, reanudación, TLS, persistencia, IPC y límites de metadatos.
- Comprobaciones funcionales y pruebas aisladas en loopback; sin pruebas contra
  servidores ajenos, sistemas de producción ni la instalación del usuario.
- Revisión de fuentes públicas permitidas y de los objetos de código del ejecutable.

## Hallazgos atendidos

Suite final del cliente: **83 pruebas aprobadas y1 omitida** por privilegio de symlink
no disponible en el entorno Windows de pruebas. Bandit sin hallazgos; el candidato de
detect-secrets era una URL inválida con credenciales ficticias del test de rechazo,
identificada explícitamente como dato de prueba.

| Hallazgo | Clasificación | Corrección |
|---|---|---|
| Posible cambio de HTTPS a HTTP durante una redirección | Media | Se bloquea antes de realizar la siguiente solicitud |
| Validación repetida de rutas torrent en el hilo de interfaz | Media | Validación por metadatos inmutables, caché de rechazo y límites de tamaño/archivos |
| Enlaces privados y estado guardados en texto claro | Privacidad | DPAPI por usuario para filas SQLite y copias internas torrent/resume; migración y compactación |
| Documentos de trabajo con referencias/rutas locales dentro de fuentes | Privacidad | Manifiesto de exportación explícito; no se exportan planes, logs, bases de datos ni historial local |

Los tests verifican reanudación, integridad, rechazo de rutas inseguras, límites,
asignación de velocidad, migración, cifrado/tamper y ausencia de validaciones repetidas.
Las pruebas automatizadas no cubren compromiso de administrador, otro equipo Windows
ni explotación exhaustiva de todas las bibliotecas nativas.

## Dependencias y avisos

El barrido de paquetes Python fijados no encontró vulnerabilidades conocidas en el
momento de la revisión. Eso no significa que todas las DLL carezcan de avisos.
libcurl8.23.0 declara cero problemas publicados en su tabla oficial a esta fecha.

Qt6.12.0 tiene avisos posteriores a su distribución. En particular, CVE-2026-116337
afecta al tratamiento HTTP de Qt Network y CVE-2026-105924 a conversión CBOR/JSON.
El cliente descarga mediante libcurl y usa Qt Network para pipes locales, sin
QNetworkAccessManager ni conversión CBOR/JSON de datos remotos. Esas rutas de entrada
no están expuestas por esta versión. Esto es una evaluación de alcanzabilidad del
cliente, no una afirmación de que las bibliotecas estén parcheadas.

CVE-2026-105943 afecta a autenticación NTLM de Qt y tampoco se utiliza. Los OpenSSL
identificados son3.5.9 y3.6.5, versiones de corrección indicadas en el aviso oficial
de29 de septiembre de2026. No se ha realizado una certificación independiente de cada DLL.

Los módulos QWebSockets, QHttpServer y Qt5Compat de otros avisos no forman parte del
payload usado por el cliente. Revisar nuevamente si se incorporan funcionalidades
nuevas o al publicarse bibliotecas corregidas.

## Límites y comunicación

DPAPI protege contra lectura casual o desde otro perfil, no contra procesos del mismo
usuario o administrador. Las descargas normales, torrents de entrada y copias antiguas
del sistema no se cifran. La auditoría de malware local y los hashes se deben repetir
en cada nuevo instalador. No se usa un servicio público de envío de binarios para escanearlos.

Reportes privados: ver SECURITY.md. No se publica material de explotación detallado.

## Referencias primarias

- https://curl.se/docs/vuln-8.23.0.html
- https://www.qt.io/blog/security-issue-cve-2026-116337
- https://www.qt.io/blog/security-advisory-cve-2026-105924
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
