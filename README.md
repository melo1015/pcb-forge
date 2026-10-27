# PCB Forge

Sistema multiagente para transformar requisitos en lenguaje natural en proyectos electrónicos KiCad, con circuit-synth como motor de diseño y MCP como interfaz de herramientas.

## Estado

**Fundación inicial del repositorio.** La estructura y los contratos básicos están implementados; la integración real con versiones concretas de circuit-synth y KiCad debe verificarse en el entorno destino antes de considerar los proyectos aptos para fabricación.

## Arquitectura

- **Servidor MCP**: publica herramientas de generación, validación y exportación.
- **Orquestador**: coordina el ciclo diseño → generación → validación → corrección, con un máximo configurable de cinco iteraciones.
- **Agentes**: diseño, generación, validación y corrección; cada agente tiene responsabilidades acotadas.
- **Integraciones**: adaptadores para circuit-synth y kicad-cli, sin acoplar la lógica central a sus APIs.
- **Workspace**: cada proyecto vive en un directorio controlado y se valida para impedir rutas fuera de la raíz.
- **Validación**: reúne diagnósticos estructurados; la aprobación de fabricación requiere comprobaciones reales de ERC/DRC y revisión humana.

## Requisitos

- Python 3.10 o posterior.
- KiCad 7 o posterior para las comprobaciones y exportaciones CLI.
- circuit-synth instalado en el entorno elegido.
- Un cliente MCP compatible para consumir las herramientas.

## Instalación de desarrollo

1. Crear un entorno virtual.
2. Instalar el paquete y dependencias: \`pip install -e ".[dev]"\`.
3. Copiar \`.env.example\` a \`.env\` y configurar rutas si hace falta.
4. Ejecutar pruebas: \`pytest\`.
5. Iniciar el servidor MCP: \`pcb-forge-mcp\`.

El servidor no debe ejecutarse con privilegios elevados. El código generado por modelos no se ejecuta sin límites: utiliza un entorno aislado, permisos mínimos y límites de tiempo antes de habilitar generación automática en producción.

## Herramientas MCP iniciales

- \`pcb_create_workspace\`: crea un workspace con nombre seguro.
- \`pcb_generate_project\`: ejecuta el flujo de diseño con los adaptadores configurados.
- \`pcb_validate_project\`: ejecuta las validaciones disponibles.
- \`pcb_export_manufacturing\`: exporta solo cuando el proyecto pasa las validaciones requeridas.

## Plan por fases

1. Fundación, contratos, pruebas y CI.
2. Integración verificable con circuit-synth.
3. Integración con KiCad CLI: ERC, DRC y comprobación de netlist.
4. Corrección limitada con diagnósticos reproducibles.
5. Exportación Gerber, taladros, STEP y BOM.
6. Pruebas de extremo a extremo con diseños de referencia y revisión de fabricación.

Consulta \`docs/ARCHITECTURE.md\`, \`docs/SECURITY.md\` y \`docs/INTEGRATION.md\`.

## Aviso de fabricación

Un resultado generado automáticamente no se considera listo para fabricar hasta que los chequeos de ERC/DRC, huellas, reglas del fabricante y archivos de salida hayan sido revisados. No se promete compatibilidad universal con fabricantes.
