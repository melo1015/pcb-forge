# Seguridad y límites de confianza

- Ejecutar el servicio con un usuario sin privilegios y acceso de escritura limitado al workspace.
- No usar \`shell=True\` ni interpolar texto del usuario en comandos.
- El adaptador de circuit-synth recibe un archivo de solicitud; la interfaz de línea de comandos debe verificarse con la versión real instalada.
- No ejecutar scripts generados por el modelo en el proceso del servidor.
- Antes de habilitar ejecución automática, utilizar contenedor o sandbox con límites de CPU, memoria, tiempo, red y sistema de archivos.
- No exponer el servidor MCP a una red pública sin autenticación y controles de acceso.
- Tratar archivos de salida y logs como datos potencialmente no confiables.
- ERC/DRC exitosos no sustituyen revisión de huellas, reglas del fabricante, aislamiento, disipación, tolerancias ni seguridad eléctrica.
