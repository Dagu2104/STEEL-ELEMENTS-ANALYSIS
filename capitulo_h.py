"""AISC 360-22 — Capítulo H: fuerzas combinadas y torsión.

El módulo usa las unidades internas de la aplicación:
- fuerzas en N
- momentos y torsión en N·mm
- longitudes en mm
- esfuerzos en MPa = N/mm²

Alcance:
- H1-1a y H1-1b para flexión y fuerza axial en miembros simétricos.
- H1-2, modificación permitida de Cb cuando hay tensión axial.
- H1-3, verificación especial opcional para perfiles laminados compactos.
- H2-1 como evaluador de razones de esfuerzo suministradas por el análisis.
- H3-1 a H3-6 para HSS circular, cuadrado y rectangular.
- H3.3 como verificación asistida, pues Fcr debe provenir de análisis.
- H4-1 para rotura de patines con agujeros y tensión.

Las resistencias axial, a flexión y a cortante no se recalculan aquí: se reciben
como resistencias disponibles obtenidas de los capítulos D/E, F y G.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import pi, sqrt
from typing import Iterable, Mapping


PHI_T = 0.90
OMEGA_T = 1.67


@dataclass(frozen=True)
class ResultadoInteraccionH:
    seccion: str
    ecuacion: str
    interaccion: float | None
    cumple: bool | None
    terminos: Mapping[str, float] = field(default_factory=dict)
    observaciones: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoTorsionHSS:
    tipo: str
    Fcr: float
    C: float
    Tn: float
    phi_Tn: float
    Tn_sobre_omega: float
    ecuacion_Fcr: str
    observaciones: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoH13:
    interaccion_plano: float
    interaccion_fuera_plano: float
    interaccion_gobernante: float
    ecuacion_plano: str
    cumple: bool
    observaciones: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoH33:
    Fn_normal: float
    Fn_cortante: float
    Fn_pandeo: float
    Fn_gobernante: float
    estado_gobernante: str
    phi_Fn: float
    Fn_sobre_omega: float


def _positivo(nombre: str, valor: float) -> None:
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")


def _no_negativo(nombre: str, valor: float) -> None:
    if valor < 0:
        raise ValueError(f"{nombre} no puede ser negativo.")


def _razon(demanda: float, capacidad: float, nombre: str) -> float:
    _no_negativo(nombre, demanda)
    if demanda <= 0:
        return 0.0
    _positivo(f"capacidad para {nombre}", capacidad)
    return demanda / capacidad


def ruta_capitulo_h(*, simetria: str, es_hss: bool, tiene_torsion: bool,
                    tiene_agujeros_patines: bool, axial_tension: bool) -> tuple[str, ...]:
    """Devuelve las secciones del Capítulo H que deben revisarse."""
    rutas: list[str] = []
    if simetria in {"Doble simetría", "Monosimétrica"}:
        rutas.append("H1")
    else:
        rutas.append("H2")
    if tiene_torsion:
        rutas.append("H3.1/H3.2" if es_hss else "H3.3")
    if tiene_agujeros_patines and axial_tension:
        rutas.append("H4")
    return tuple(rutas)


def calcular_h11(*, Pr: float, Pc: float, Mrx: float = 0.0, Mcx: float = 0.0,
                  Mry: float = 0.0, Mcy: float = 0.0) -> ResultadoInteraccionH:
    """Interacción H1-1a/H1-1b para compresión o tensión y flexión biaxial.

    Todas las demandas se toman como magnitudes positivas, como exige la nota de
    usuario de H1. Pc, Mcx y Mcy son resistencias disponibles, no nominales.
    """
    rp = _razon(abs(Pr), Pc, "Pr")
    rmx = _razon(abs(Mrx), Mcx, "Mrx")
    rmy = _razon(abs(Mry), Mcy, "Mry")
    if rp >= 0.20:
        ir = rp + (8.0 / 9.0) * (rmx + rmy)
        ecuacion = "H1-1a"
        terminos = {
            "Pr/Pc": rp,
            "Mrx/Mcx": rmx,
            "Mry/Mcy": rmy,
            "8/9(Mrx/Mcx+Mry/Mcy)": (8.0 / 9.0) * (rmx + rmy),
        }
    else:
        ir = rp / 2.0 + rmx + rmy
        ecuacion = "H1-1b"
        terminos = {
            "Pr/Pc": rp,
            "Pr/(2Pc)": rp / 2.0,
            "Mrx/Mcx": rmx,
            "Mry/Mcy": rmy,
        }
    return ResultadoInteraccionH(
        seccion="H1.1/H1.2",
        ecuacion=ecuacion,
        interaccion=ir,
        cumple=ir <= 1.0,
        terminos=terminos,
        observaciones=("Todos los términos de H1-1a y H1-1b se tomaron positivos.",),
    )


def calcular_pey(*, E: float, Iy: float, Lb: float) -> float:
    for nombre, valor in {"E": E, "Iy": Iy, "Lb": Lb}.items():
        _positivo(nombre, valor)
    return pi**2 * E * Iy / Lb**2


def modificar_cb_tension(*, Cb: float, Pr: float, Pey: float, metodo: str) -> tuple[float, float]:
    """Modificación permitida por H1.2 para miembros doblemente simétricos."""
    _positivo("Cb", Cb)
    _no_negativo("Pr", Pr)
    _positivo("Pey", Pey)
    if metodo not in {"LRFD", "ASD"}:
        raise ValueError("El método debe ser LRFD o ASD.")
    alfa = 1.0 if metodo == "LRFD" else 1.6
    factor = sqrt(1.0 + alfa * Pr / Pey)
    return Cb * factor, factor


def calcular_h13(*, Pr: float, Pc_plano: float, Pcy: float,
                  Mrx: float, Mcx_fluencia: float, Mcx_ltb_cb1: float,
                  Cb: float) -> ResultadoH13:
    """Verificación especial H1.3 para el caso que satisface sus requisitos."""
    plano = calcular_h11(
        Pr=Pr, Pc=Pc_plano, Mrx=Mrx, Mcx=Mcx_fluencia, Mry=0.0, Mcy=1.0,
    )
    rp_y = _razon(abs(Pr), Pcy, "Pr/Pcy")
    rm_ltb = _razon(abs(Mrx), Cb * Mcx_ltb_cb1, "Mrx/(Cb Mcx)")
    fuera = rp_y * (1.5 - 0.5 * rp_y) + rm_ltb**2
    gob = max(float(plano.interaccion), fuera)
    return ResultadoH13(
        interaccion_plano=float(plano.interaccion),
        interaccion_fuera_plano=fuera,
        interaccion_gobernante=gob,
        ecuacion_plano=plano.ecuacion,
        cumple=gob <= 1.0,
        observaciones=(
            "H1.3 solo es válido cuando se satisfacen todas las condiciones de elegibilidad de la sección.",
            "Mcx_ltb_cb1 debe ser la resistencia disponible a LTB calculada con Cb=1.0.",
        ),
    )


def calcular_h2(*, razones_puntos: Iterable[Mapping[str, float]]) -> ResultadoInteraccionH:
    """Evalúa H2-1 a partir de razones de esfuerzo en puntos críticos.

    Cada elemento debe contener las claves ``axial``, ``flexion_w`` y
    ``flexion_z``. Los signos se conservan dentro de la suma y luego se toma el
    valor absoluto, como indica H2-1.
    """
    max_ir = -1.0
    gob: Mapping[str, float] | None = None
    for punto in razones_puntos:
        suma = float(punto.get("axial", 0.0)) + float(punto.get("flexion_w", 0.0)) + float(punto.get("flexion_z", 0.0))
        ir = abs(suma)
        if ir > max_ir:
            max_ir = ir
            gob = punto
    if gob is None:
        raise ValueError("Debe suministrarse al menos un punto crítico para H2-1.")
    terminos = {
        "fra/Fca": float(gob.get("axial", 0.0)),
        "frbw/Fcbw": float(gob.get("flexion_w", 0.0)),
        "frbz/Fcbz": float(gob.get("flexion_z", 0.0)),
    }
    return ResultadoInteraccionH(
        seccion="H2",
        ecuacion="H2-1",
        interaccion=max_ir,
        cumple=max_ir <= 1.0,
        terminos=terminos,
        observaciones=(
            "H2-1 debe evaluarse en los ejes principales y en todos los puntos críticos de la sección.",
        ),
    )


def constante_torsional_hss_circular(*, D: float, t: float) -> float:
    _positivo("D", D)
    _positivo("t", t)
    if 2.0 * t >= D:
        raise ValueError("Para un HSS circular debe cumplirse 2t < D.")
    return pi * (D - t) ** 2 * t / 2.0


def constante_torsional_hss_rectangular(*, B: float, H: float, t: float) -> float:
    for nombre, valor in {"B": B, "H": H, "t": t}.items():
        _positivo(nombre, valor)
    if 2.0 * t >= min(B, H):
        raise ValueError("Para un HSS rectangular debe cumplirse 2t < min(B,H).")
    return 2.0 * (B - t) * (H - t) * t - 4.5 * (4.0 - pi) * t**3


def calcular_torsion_hss_circular(*, E: float, Fy: float, D: float, t: float,
                                   L: float) -> ResultadoTorsionHSS:
    for nombre, valor in {"E": E, "Fy": Fy, "D": D, "t": t, "L": L}.items():
        _positivo(nombre, valor)
    if 2.0 * t >= D:
        raise ValueError("Para un HSS circular debe cumplirse 2t < D.")
    relacion = D / t
    f1 = 1.23 * E / (sqrt(L / D) * relacion ** (5.0 / 4.0))
    f2 = 0.60 * E / relacion ** (3.0 / 2.0)
    if f1 >= f2:
        fcr_sin_limite = f1
        ecuacion = "H3-2a"
    else:
        fcr_sin_limite = f2
        ecuacion = "H3-2b"
    Fcr = min(fcr_sin_limite, 0.6 * Fy)
    C = constante_torsional_hss_circular(D=D, t=t)
    Tn = Fcr * C
    observaciones = [f"Se tomó el mayor de H3-2a ({f1:.6g} MPa) y H3-2b ({f2:.6g} MPa)."]
    if Fcr < fcr_sin_limite - 1e-12:
        observaciones.append("Fcr fue limitado a 0.6Fy.")
    return ResultadoTorsionHSS(
        tipo="HSS circular", Fcr=Fcr, C=C, Tn=Tn,
        phi_Tn=PHI_T * Tn, Tn_sobre_omega=Tn / OMEGA_T,
        ecuacion_Fcr=ecuacion, observaciones=tuple(observaciones),
    )


def calcular_torsion_hss_rectangular(*, E: float, Fy: float, B: float, H: float,
                                      t: float, h_plano: float) -> ResultadoTorsionHSS:
    for nombre, valor in {"E": E, "Fy": Fy, "B": B, "H": H, "t": t, "h_plano": h_plano}.items():
        _positivo(nombre, valor)
    lam = h_plano / t
    limite1 = 2.45 * sqrt(E / Fy)
    limite2 = 3.07 * sqrt(E / Fy)
    if lam <= limite1:
        Fcr = 0.6 * Fy
        ecuacion = "H3-3"
    elif lam <= limite2:
        Fcr = 0.6 * Fy * limite1 / lam
        ecuacion = "H3-4"
    elif lam <= 260.0:
        Fcr = 0.458 * pi**2 * E / lam**2
        ecuacion = "H3-5"
    else:
        raise ValueError("H3.1(b) no proporciona una resistencia para h/t > 260.")
    C = constante_torsional_hss_rectangular(B=B, H=H, t=t)
    Tn = Fcr * C
    return ResultadoTorsionHSS(
        tipo="HSS rectangular", Fcr=Fcr, C=C, Tn=Tn,
        phi_Tn=PHI_T * Tn, Tn_sobre_omega=Tn / OMEGA_T,
        ecuacion_Fcr=ecuacion,
        observaciones=(f"h/t = {lam:.6g}; límites: {limite1:.6g} y {limite2:.6g}.",),
    )


def calcular_h36(*, Pr: float, Pc: float, Mrx: float, Mcx: float,
                  Mry: float, Mcy: float, Vrx: float, Vcx: float,
                  Vry: float, Vcy: float, Tr: float, Tc: float) -> ResultadoInteraccionH:
    """Interacción H3-6 para HSS cuando Tr/Tc > 0.20."""
    rp = _razon(abs(Pr), Pc, "Pr")
    rmx = _razon(abs(Mrx), Mcx, "Mrx")
    rmy = _razon(abs(Mry), Mcy, "Mry")
    rvx = _razon(abs(Vrx), Vcx, "Vrx")
    rvy = _razon(abs(Vry), Vcy, "Vry")
    rv = max(rvx, rvy)
    rt = _razon(abs(Tr), Tc, "Tr")
    cuadratico = (rv + rt) ** 2
    ir = rp + rmx + rmy + cuadratico
    return ResultadoInteraccionH(
        seccion="H3.2",
        ecuacion="H3-6",
        interaccion=ir,
        cumple=ir <= 1.0,
        terminos={
            "Pr/Pc": rp,
            "Mrx/Mcx": rmx,
            "Mry/Mcy": rmy,
            "Vrx/Vcx": rvx,
            "Vry/Vcy": rvy,
            "Vr/Vc gobernante": rv,
            "Tr/Tc": rt,
            "(Vr/Vc+Tr/Tc)^2": cuadratico,
        },
        observaciones=("Vr/Vc se tomó como el mayor de los valores para los ejes x e y.",),
    )


def verificar_h33_manual(*, Fy: float, Fcr: float) -> ResultadoH33:
    """Estados límite de H3.3 para perfiles no HSS.

    El valor Fcr debe provenir del análisis de pandeo torsional de la sección.
    """
    _positivo("Fy", Fy)
    _positivo("Fcr", Fcr)
    candidatos = {
        "Fluencia bajo esfuerzo normal — H3-7": Fy,
        "Fluencia bajo esfuerzo cortante — H3-8": 0.6 * Fy,
        "Pandeo — H3-9": Fcr,
    }
    estado, Fn = min(candidatos.items(), key=lambda item: item[1])
    return ResultadoH33(
        Fn_normal=Fy,
        Fn_cortante=0.6 * Fy,
        Fn_pandeo=Fcr,
        Fn_gobernante=Fn,
        estado_gobernante=estado,
        phi_Fn=PHI_T * Fn,
        Fn_sobre_omega=Fn / OMEGA_T,
    )


def calcular_h4(*, Pr: float, Pc_rotura: float, Mrx: float,
                 Mcx_rotura: float) -> ResultadoInteraccionH:
    """Interacción H4-1 para un patín con agujeros sometido a tensión."""
    rp = _razon(abs(Pr), Pc_rotura, "Pr")
    rm = _razon(abs(Mrx), Mcx_rotura, "Mrx")
    ir = rp + rm
    return ResultadoInteraccionH(
        seccion="H4",
        ecuacion="H4-1",
        interaccion=ir,
        cumple=ir <= 1.0,
        terminos={"Pr/Pc": rp, "Mrx/Mcx": rm},
        observaciones=(
            "Cada patín sometido a tensión por la combinación de fuerza axial y flexión debe verificarse por separado.",
        ),
    )
