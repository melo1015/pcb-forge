# Integración local

## 1. Preparar Python

Recomendado: Python 3.11 o 3.12 en un entorno virtual.

    python -m venv .venv
    # Linux/macOS
    source .venv/bin/activate
    # Windows PowerShell
    .venv\Scripts\Activate.ps1
    pip install -e ".[dev]"

## 2. Configurar KiCad

Instala KiCad 7 o posterior y comprueba en terminal:

    kicad-cli version

Configura PCB_FORGE_KICAD_CLI con la ruta absoluta al ejecutable si no está en PATH. Los argumentos de ERC/DRC pueden variar entre versiones; verifica \`kicad-cli sch erc --help\` y \`kicad-cli pcb drc --help\` en el sistema destino.

## 3. Configurar circuit-synth

La interfaz de invocación todavía debe adaptarse y verificarse contra la versión instalada. PCB Forge no asume que exista un comando universal. El valor PCB_FORGE_CIRCUIT_SYNTH_COMMAND debe ser el ejecutable y sus argumentos fijos; el adaptador añade \`--request-file\` y \`--output-dir\`. Si la versión instalada no admite esos argumentos, implementa un adaptador específico y añade una prueba de integración antes de usarlo.

## 4. Iniciar MCP

    pcb-forge-mcp

Configura el cliente MCP para iniciar ese comando en el mismo entorno virtual. Para depuración directa:

    python -m pcb_forge.mcp_server

## 5. Validar

    pytest

La validación completa requiere herramientas externas instaladas. Sin circuit-synth y KiCad configurados, el sistema devuelve diagnósticos en lugar de declarar el proyecto válido.
