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

## 4. Backend directo para un módulo Circuit-Synth revisado

PCB Forge incorpora la herramienta MCP `pcb_generate_from_circuit_synth_source(name, source_filename)`. Esta ruta no usa el wrapper genérico: ejecuta un módulo Python con el Circuit-Synth instalado en el mismo intérprete configurado para PCB Forge.

Flujo recomendado:

1. Crea el proyecto con `pcb_create_workspace`.
2. Añade al directorio del proyecto un archivo `.py` revisado, por ejemplo `design.py`.
3. El módulo debe exponer `build_circuit()`, que devuelve un objeto Circuit-Synth con el método `generate_kicad_project(project_name)`.
4. Llama a `pcb_generate_from_circuit_synth_source` con el nombre del proyecto y `design.py`.
5. Confirma que se detectan archivos KiCad y ejecuta `pcb_validate_project` antes de cualquier exportación.

Contrato mínimo del módulo:

```python
def build_circuit():
    # Construye y devuelve aquí un objeto Circuit-Synth válido.
    # Implementa el circuito usando la API de la versión instalada.
    return circuit
```

El ejemplo es una interfaz, no un circuito funcional. La sintaxis concreta para construir componentes, redes y alimentar el generador depende de la versión instalada de Circuit-Synth. Instala Circuit-Synth en un entorno compatible con su versión de Python y consulta la documentación de esa versión antes de escribir el módulo.

**Seguridad:** el módulo se ejecuta en un proceso separado, pero esto no constituye un sandbox de seguridad. Solo uses código propio o revisado; no aceptes módulos arbitrarios de usuarios externos. La fuente debe estar dentro del workspace del proyecto. El backend devuelve error si la ejecución falla o no detecta archivos `.kicad*`.

Esta integración genera desde código Circuit-Synth revisado; **no convierte por sí misma una descripción en lenguaje natural en un circuito**. La traducción automática de especificación a código Circuit-Synth y la prueba E2E con Circuit-Synth + KiCad reales siguen siendo tareas separadas.

## 5. Validación y fabricación

La herramienta `pcb_validate_project` ejecuta DRC para cada `.kicad_pcb` y ERC para cada `.kicad_sch`. La herramienta `pcb_export_manufacturing` bloquea la exportación si la validación no pasa y genera, por placa, esta estructura:

```text
manufacturing/<nombre-placa>/
  gerber/   # capas Gerber
  drill/    # taladrado Excellon
  <nombre-placa>.step  # modelo 3D de la placa
```

Un código de salida cero indica que KiCad completó el comando; no garantiza que los archivos sean correctos ni que la placa sea fabricable. Revisa capas, unidades, contorno, taladros, stack-up, modelos 3D, reglas del fabricante y la lista de materiales antes de pedir producción. La salida STEP depende de la información disponible en la placa y de la versión/configuración de KiCad.

## 6. Iniciar MCP y ejecutar pruebas

```bash
pcb-forge-mcp
pytest
ruff check src tests
```

Configura el cliente MCP para iniciar `pcb-forge-mcp` en el mismo entorno virtual. La CI actual prueba el código Python con herramientas externas simuladas; no equivale a una prueba E2E con KiCad y un wrapper real instalados. Para declarar integración real, ejecuta también una prueba en un entorno que contenga versiones registradas de KiCad y del wrapper de generación.

## 7. Prueba E2E real con Circuit-Synth + KiCad

El workflow manual `.github/workflows/circuit-synth-e2e.yml` prueba el backend contra herramientas reales. No se ejecuta en los runners hospedados estándar: requiere un runner Linux propio y de confianza con las etiquetas `self-hosted`, `linux` y `pcb-forge-e2e`, además de KiCad CLI instalado y accesible en `PATH`. El workflow instala Circuit-Synth en Python 3.12.

La prueba de referencia es `examples/circuit_synth/regulator_5v.py`. Para ejecutarla localmente:

```bash
python -m pip install -e ".[dev,circuit-synth]"
python scripts/run_circuit_synth_e2e.py examples/circuit_synth/regulator_5v.py
```

El script genera el proyecto en un directorio temporal, comprueba que existan al menos un esquema y una placa KiCad, y ejecuta ERC y DRC, mostrando las salidas y las rutas de los informes. El script falla si la generación no produce los archivos esperados o si los comandos de KiCad no pueden ejecutarse; **un código de salida cero no significa que ERC/DRC estén libres de infracciones**. Revisa los informes y el diseño en KiCad antes de considerar fabricar la placa. La referencia de 5 V es una base de integración, no un diseño certificado ni listo para producción.

Para habilitar el workflow, registra un runner autohospedado aislado con las tres etiquetas indicadas y ejecútalo manualmente desde la pestaña Actions. No registres como runner una máquina personal o de producción sin evaluar los riesgos de ejecutar código del repositorio.

