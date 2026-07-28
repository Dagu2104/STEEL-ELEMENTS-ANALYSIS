"""Conversión de unidades para la aplicación.

Sistema interno único:
- longitud: mm
- esfuerzo: MPa = N/mm²
- fuerza: N
- momento: N·mm
"""
from __future__ import annotations

LONGITUD_A_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
ESFUERZO_A_MPA = {"MPa": 1.0, "kPa": 0.001, "kgf/cm²": 0.0980665, "ksi": 6.894757293168}
FUERZA_A_N = {"N": 1.0, "kN": 1000.0, "kgf": 9.80665, "tf": 9806.65, "kip": 4448.2216152605}
MOMENTO_A_NMM = {
    "N·mm": 1.0,
    "N·m": 1000.0,
    "kN·m": 1_000_000.0,
    "kgf·m": 9806.65,
    "tf·m": 9_806_650.0,
    "kip·in": 4448.2216152605 * 25.4,
    "kip·ft": 4448.2216152605 * 304.8,
}


def a_interno(valor: float, magnitud: str, unidad: str, potencia: int = 1) -> float:
    if magnitud == "longitud":
        return valor * LONGITUD_A_MM[unidad] ** potencia
    if magnitud == "esfuerzo":
        return valor * ESFUERZO_A_MPA[unidad]
    if magnitud == "fuerza":
        return valor * FUERZA_A_N[unidad]
    if magnitud == "momento":
        return valor * MOMENTO_A_NMM[unidad]
    raise ValueError(f"Magnitud no reconocida: {magnitud}")


def desde_interno(valor: float, magnitud: str, unidad: str, potencia: int = 1) -> float:
    if magnitud == "longitud":
        return valor / LONGITUD_A_MM[unidad] ** potencia
    if magnitud == "esfuerzo":
        return valor / ESFUERZO_A_MPA[unidad]
    if magnitud == "fuerza":
        return valor / FUERZA_A_N[unidad]
    if magnitud == "momento":
        return valor / MOMENTO_A_NMM[unidad]
    raise ValueError(f"Magnitud no reconocida: {magnitud}")


def unidad_propiedad(unidad_longitud: str, potencia: int) -> str:
    superindices = {1: "", 2: "²", 3: "³", 4: "⁴", 6: "⁶"}
    return f"{unidad_longitud}{superindices.get(potencia, f'^{potencia}')}"
