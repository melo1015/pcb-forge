# Arquitectura

## Flujo

1. El cliente llama una herramienta MCP.
2. El orquestador valida nombre y descripción y crea un workspace confinado.
3. El adaptador configurado invoca circuit-synth sin shell.
4. El adaptador KiCad localiza archivos de esquema y PCB y ejecuta ERC/DRC cuando están disponibles.
5. Los diagnósticos se devuelven como datos estructurados para revisión y corrección.

## Componentes

- \`mcp_server.py\`: superficie MCP; no contiene lógica de diseño.
- \`orchestrator.py\`: coordinación del flujo.
- \`agents/\`: roles separados y reemplazables.
- \`integrations/\`: límites para herramientas externas.
- \`workspace.py\`: validación de nombres y confinamiento de rutas.
- \`models.py\`: contratos de diagnósticos y reportes.

## Próximas iteraciones

- Añadir interfaz de circuito con API real de circuit-synth fijada por versión.
- Añadir validación de netlist y detección de referencias duplicadas.
- Implementar ciclo de corrección con máximo de cinco iteraciones, comparación de diffs y aprobación explícita.
- Implementar exportación de Gerber, taladros, STEP y BOM con verificación de artefactos.
- Añadir fixtures de diseños conocidos y pruebas end-to-end en un entorno que tenga KiCad instalado.


## Requisitos LLM y puertas de fabricación

- `agents/requirements.py` define el contrato estructurado que debe devolver el adaptador LLM para los requisitos eléctricos.
- Los valores críticos desconocidos permanecen como `null`; no se completan con valores típicos. La revisión eléctrica queda bloqueada si faltan los límites de entrada, salida, temperatura ambiente o referencia exacta del regulador.
- El cliente de LLM se inyecta mediante `RequirementsAgent(llm_call=...)`; las credenciales y el proveedor quedan fuera del agente. La conexión concreta con el proveedor debe configurarse en la aplicación anfitriona.
- `integrations/cam_preflight.py` valida la estructura de Gerbers, Excellon y metadatos de fabricación.
- La exportación de fabricación se bloquea si falla el preflight estructural. Aunque pase, `ready_for_manufacturing` continúa siendo `false` hasta la revisión eléctrica, la inspección CAM independiente y la confirmación de las reglas del fabricante.
