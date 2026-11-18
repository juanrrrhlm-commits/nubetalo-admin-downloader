# Privacidad — Nubetalo Admin Downloader 0.3.0

La aplicación no requiere cuenta y no incorpora anuncios, analítica ni telemetría. No consulta actualizaciones automáticamente en esta versión.

La cola y preferencias se almacenan en el equipo. Las URLs de descarga y los torrents pueden contener parámetros privados; la base SQLite y sus copias locales deben tratarse como información privada. No se importan cookies del navegador ni se observa continuamente el portapapeles.

Desde0.3, los registros de la cola/configuración y las copias internas torrent/resume
se protegen con DPAPI para tu usuario de Windows. Las colas anteriores se migran y se
compacta SQLite; no se modifican tus archivos descargados ni tus torrents de entrada.
Las copias de seguridad antiguas y las instantáneas del sistema pueden conservar
datos anteriores. DPAPI no protege contra procesos que ya actúen como tu mismo usuario
o administrador, ni permite trasladar sin más el estado a otro perfil/equipo.

Para descargar, la aplicación contacta los servidores elegidos y sus redirecciones. Para torrents contacta trackers, la DHT y otros pares según las características del torrent. Estos participantes pueden conocer tu dirección IP; la aplicación no proporciona anonimato. No habilita UPnP/NAT-PMP ni cambia el router automáticamente.

Donar abre la página de PayPal en el navegador; PayPal procesa el pago con su propia política de privacidad. La aplicación no recibe datos de tarjeta ni confirmaciones de donación. Soporte abre tu cliente de correo y solo envías lo que decidas.

Nubetalo es el editor del programa, con contacto en juanrrrhlm@gmail.com. Si escribes
a soporte, el correo y el contenido que envíes se usarán para atender tu solicitud;
evita enviar URLs privadas, credenciales, la cola o archivos personales. Puedes
solicitar acceso, rectificación o eliminación de los datos aportados por ese mismo
canal. No hay servidor de cuentas, analítica ni subida automática de diagnósticos.
GitHub, itch.io, PayPal y tu proveedor de correo aplican sus propias políticas fuera
de la aplicación. Ver LEGAL.md para el marco y los derechos que no se renuncian.

El inicio con Windows y las asociaciones opcionales utilizan el registro del usuario. La comunicación entre dos aperturas de la aplicación usa una tubería local restringida al usuario, sin servicio de control remoto TCP.

La desinstalación conserva las descargas y el estado del usuario. Para eliminar el historial, con la app cerrada puedes borrar su carpeta de datos local; esto no elimina los archivos descargados en otras carpetas. No compartas esa carpeta públicamente.
