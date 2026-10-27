# Integración local

## 1. Preparar Python

Recomendado: Python 3.11 o 3.12 en un entorno virtual.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
```

## 2. Configurar KiCad

Instala KiCad y comprueba en terminal:

```bash
kicad-cli version
kicad-cli pcb export gerbers --help
kicad-cli pcb export drill --help
kicad-cli pcb export step --help
kicad-cli pcb drc --help
kicad-cli sch erc --help
```

Configura `PCB_FORGE_KICAD_CLI` con la ruta absoluta al ejecutable si no está en `PATH`. Los argumentos y opciones disponibles dependen de la versión instalada; confirma los comandos con `--help` en el equipo destino.

## 3. Generación de circuitos: límite actual

**PCB Forge todavía no invoca directamente la API Python de Circuit-Synth.** La API pública de Circuit-Synth requiere definir/obtener una función de circuito en Python y llamar a `generate_kicad_project(...)`; no existe un contrato universal asumido aquí de `circuit-synth --request-file ... --output-dir ...`.

El adaptador actual llama a un **wrapper externo de confianza** con el contrato fijo:

```text
<ejecutable-y-argumentos-fijos> --request-file <ruta/design_request.txt> --output-dir <directorio-del-proyecto>
```

`PCB_FORGE_CIRCUIT_SYNTH_COMMAND` debe apuntar a ese wrapper, no directamente al ejecutable upstream de Circuit-Synth, salvo que el usuario haya comprobado que un wrapper compatible existe. El wrapper es responsable de transformar la descripción en un diseño de circuito válido, generar el proyecto KiCad y devolver un código de salida distinto de cero si falla. No ejecutes wrappers o scripts de procedencia desconocida.

La siguiente integración real debe añadir un backend versionado que transforme la especificación en código de circuito revisable, lo ejecute en un entorno aislado y verifique que se generaron los archivos KiCad esperados. Hasta entonces, una descripción en lenguaje natural por sí sola **no produce automáticamente un diseño electrónico fiable**.

## 4. Validación y fabricación

La herramienta `pcb_validate_project` ejecuta DRC para cada `.kicad_pcb` y ERC para cada `.kicad_sch`. La herramienta `pcb_export_manufacturing` bloquea la exportación si la validación no pasa y genera, por placa, esta estructura:

```text
manufacturing/<nombre-placa>/
  gerber/   # capas Gerber
  drill/    # taladrado Excellon
  <nombre-placa>.step  # modelo 3D de la placa
```

Un código de salida cero indica que KiCad completó el comando; no garantiza que los archivos sean correctos ni que la placa sea fabricable. Revisa capas, unidades, contorno, taladros, stack-up, modelos 3D, reglas del fabricante y la lista de materiales antes de pedir producción. La salida STEP depende de la información disponible en la placa y de la versión/configuración de KiCad.

## 5. Iniciar MCP y ejecutar pruebas

```bash
pcb-forge-mcp
pytest
ruff check src tests
```

Configura el cliente MCP para iniciar `pcb-forge-mcp` en el mismo entorno virtual. La CI actual prueba el código Python con herramientas externas simuladas; no equivale a una prueba E2E con KiCad y un wrapper real instalados. Para declarar integración real, ejecuta también una prueba en un entorno que contenga versiones registradas de KiCad y del wrapper de generación.
