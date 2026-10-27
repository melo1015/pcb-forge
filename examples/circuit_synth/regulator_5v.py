"""Reference Circuit-Synth design: 5 V linear regulator.

This is an integration-test starting point, not a production-ready PCB.
Review thermal limits, input range, capacitors, footprints, ERC/DRC and layout
before manufacturing.
"""
from circuit_synth import Component, Net, circuit


@circuit(name="regulator_5v")
def build_circuit():
    vin = Net("VIN")
    vout = Net("VOUT_5V")
    gnd = Net("GND")

    regulator = Component(
        symbol="Regulator_Linear:L7805",
        ref="U1",
        value="L7805",
        footprint="Package_TO_SOT_THT:TO-220-3_Vertical",
    )
    input_cap = Component(
        symbol="Device:C",
        ref="C1",
        value="330nF",
        footprint="Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
    )
    output_cap = Component(
        symbol="Device:C",
        ref="C2",
        value="100nF",
        footprint="Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
    )
    input_connector = Component(
        symbol="Connector_Generic:Conn_01x02",
        ref="J1",
        value="DC_IN",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    )
    output_connector = Component(
        symbol="Connector_Generic:Conn_01x02",
        ref="J2",
        value="5V_OUT",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    )

    # Power flags tell ERC that the external input and ground rails are driven.
    vin_flag = Component(symbol="power:PWR_FLAG", ref="#FLG01", value="PWR_FLAG")
    gnd_flag = Component(symbol="power:PWR_FLAG", ref="#FLG02", value="PWR_FLAG")

    # Circuit-Synth Net.__iadd__ accepts one pin at a time; comma-separated
    # values would form a tuple and fail during generation.
    vin += regulator[1]
    vin += input_cap[1]
    vin += input_connector[1]
    vin += vin_flag[1]

    gnd += regulator[2]
    gnd += input_cap[2]
    gnd += output_cap[2]
    gnd += input_connector[2]
    gnd += output_connector[2]
    gnd += gnd_flag[1]

    vout += regulator[3]
    vout += output_cap[1]
    vout += output_connector[1]


if __name__ == "__main__":
    circuit_instance = build_circuit()
    circuit_instance.generate_kicad_project("regulator_5v")
