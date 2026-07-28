"""Cálculos del Capítulo E de AISC 360 para miembros a compresión.

Las funciones siguen las ecuaciones mostradas por el usuario (E2 a E7). La
aplicación distingue entre clasificación local (Tabla B4.1a) y pandeo global.
Todas las magnitudes deben ingresarse en un sistema coherente de unidades.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from typing import Iterable


@dataclass(frozen=True)
class ResultadoPandeo:
    modo: str
    eje: str
    Lc: float
    esbeltez: float
    Fe: float
    Fn: float
    Pn: float
    ecuacion_fn: str
    observacion: str = ""


@dataclass(frozen=True)
class RutaCapituloE:
    categoria: str
    secciones: tuple[str, ...]
    estados_limite: tuple[str, ...]
    tiene_elementos_esbeltos: bool
    simetria: str
    explicacion: str


def _positivo(nombre: str, valor: float) -> None:
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")


def longitud_efectiva(K: float, L: float) -> float:
    """E2: Lc = K·L."""
    _positivo("K", K)
    _positivo("L", L)
    return K * L


def esfuerzo_euler(E: float, Lc: float, r: float) -> float:
    """E3-4: Fe = pi²E/(Lc/r)²."""
    for n, v in {"E": E, "Lc": Lc, "r": r}.items():
        _positivo(n, v)
    return pi**2 * E / (Lc / r) ** 2


def esfuerzo_nominal_compresion(Fy: float, Fe: float) -> tuple[float, str]:
    """E3-2 y E3-3."""
    _positivo("Fy", Fy)
    _positivo("Fe", Fe)
    if Fy / Fe <= 2.25:
        return (0.658 ** (Fy / Fe)) * Fy, "E3-2"
    return 0.877 * Fe, "E3-3"


def pandeo_flexional(*, eje: str, E: float, Fy: float, Ag: float, K: float, L: float, r: float) -> ResultadoPandeo:
    """E3: pandeo flexional alrededor de un eje."""
    _positivo("Ag", Ag)
    Lc = longitud_efectiva(K, L)
    esbeltez = Lc / r
    Fe = esfuerzo_euler(E, Lc, r)
    Fn, ecuacion = esfuerzo_nominal_compresion(Fy, Fe)
    return ResultadoPandeo(
        modo="Pandeo flexional",
        eje=eje,
        Lc=Lc,
        esbeltez=esbeltez,
        Fe=Fe,
        Fn=Fn,
        Pn=Fn * Ag,
        ecuacion_fn=ecuacion,
        observacion="E3-1: Pn = Fn·Ag.",
    )


def radio_polar_centro_cortante(*, x0: float, y0: float, Ix: float, Iy: float, Ag: float) -> float:
    """E4-9: r0² = x0² + y0² + (Ix+Iy)/Ag."""
    for n, v in {"Ix": Ix, "Iy": Iy, "Ag": Ag}.items():
        _positivo(n, v)
    return sqrt(x0**2 + y0**2 + (Ix + Iy) / Ag)


def constante_flexional_H(*, x0: float, y0: float, r0: float) -> float:
    """E4-8: H = 1 - (x0²+y0²)/r0²."""
    _positivo("r0", r0)
    H = 1.0 - (x0**2 + y0**2) / r0**2
    if H <= 0:
        raise ValueError("H debe ser mayor que cero para aplicar E4-3.")
    return H


def esfuerzos_elasticos_e4(*, E: float, G: float, Ag: float, Ix: float, Iy: float,
                           J: float, Cw: float, Lcx: float, Lcy: float, Lcz: float,
                           r0: float) -> tuple[float, float, float]:
    """E4-5, E4-6 y E4-7."""
    for n, v in {
        "E": E, "G": G, "Ag": Ag, "Ix": Ix, "Iy": Iy,
        "J": J, "Lcx": Lcx, "Lcy": Lcy, "Lcz": Lcz, "r0": r0,
    }.items():
        _positivo(n, v)
    Fex = pi**2 * E / (Lcx / sqrt(Ix / Ag))**2
    Fey = pi**2 * E / (Lcy / sqrt(Iy / Ag))**2
    Fez = ((pi**2 * E * Cw / Lcz**2) + G * J) / (Ag * r0**2)
    return Fex, Fey, Fez


def fe_torsional_doble_simetria(*, E: float, G: float, Cw: float, J: float,
                                 Lcz: float, Ix: float, Iy: float) -> float:
    """E4-2 para miembros doblemente simétricos que giran sobre el centro de cortante."""
    for n, v in {"E": E, "G": G, "Cw": Cw, "J": J, "Lcz": Lcz, "Ix": Ix, "Iy": Iy}.items():
        _positivo(n, v)
    return (pi**2 * E * Cw / Lcz**2 + G * J) / (Ix + Iy)


def fe_flexotorsional_monosimetrico(*, Fes: float, Fez: float, H: float) -> float:
    """E4-3. Fes es el esfuerzo de Euler respecto al eje de simetría."""
    for n, v in {"Fes": Fes, "Fez": Fez, "H": H}.items():
        _positivo(n, v)
    radicando = 1.0 - 4.0 * Fes * Fez * H / (Fes + Fez) ** 2
    if radicando < -1e-10:
        raise ValueError("El radicando de E4-3 es negativo; revise propiedades y longitudes.")
    radicando = max(0.0, radicando)
    return ((Fes + Fez) / (2.0 * H)) * (1.0 - sqrt(radicando))


def fe_flexotorsional_asimetrico(*, Fex: float, Fey: float, Fez: float,
                                  x0: float, y0: float, r0: float) -> float:
    """E4-4: devuelve la menor raíz positiva del polinomio cúbico."""
    import numpy as np

    for n, v in {"Fex": Fex, "Fey": Fey, "Fez": Fez, "r0": r0}.items():
        _positivo(n, v)
    ax = (x0 / r0) ** 2
    ay = (y0 / r0) ** 2
    # (F-Fex)(F-Fey)(F-Fez) - F²(F-Fey)ax - F²(F-Fex)ay = 0
    p = np.poly1d([1.0, -Fex]) * np.poly1d([1.0, -Fey]) * np.poly1d([1.0, -Fez])
    p -= ax * np.poly1d([1.0, 0.0, 0.0]) * np.poly1d([1.0, -Fey])
    p -= ay * np.poly1d([1.0, 0.0, 0.0]) * np.poly1d([1.0, -Fex])
    roots = np.roots(p)
    positivas = sorted(float(r.real) for r in roots if abs(r.imag) < 1e-7 and r.real > 0)
    if not positivas:
        raise ValueError("E4-4 no produjo raíces reales positivas.")
    return positivas[0]


def pandeo_torsional_o_flexotorsional(*, modo: str, Fe: float, Fy: float, Ag: float,
                                       eje: str = "z-z") -> ResultadoPandeo:
    """E4-1 combinado con E3-2/E3-3."""
    _positivo("Ag", Ag)
    Fn, ecuacion = esfuerzo_nominal_compresion(Fy, Fe)
    return ResultadoPandeo(
        modo=modo,
        eje=eje,
        Lc=float("nan"),
        esbeltez=float("nan"),
        Fe=Fe,
        Fn=Fn,
        Pn=Fn * Ag,
        ecuacion_fn=ecuacion,
        observacion="E4-1: Pn = Fn·Ag; Fn se obtiene con E3-2 o E3-3 usando Fe de E4.",
    )


def esbeltez_modificada_angulo(*, caso: str, L_sobre_ra: float, razon_patas: float = 1.0,
                               conexion_pata_corta: bool = False) -> float:
    """E5-1 a E5-4 para ángulos simples bajo las condiciones de E5."""
    _positivo("L/ra", L_sobre_ra)
    if caso == "cercha":
        valor = 72.0 + 0.75 * L_sobre_ra if L_sobre_ra <= 80.0 else 32.0 + 1.25 * L_sobre_ra
        limite = 0.95 * L_sobre_ra
    elif caso == "miembro de celosía":
        valor = 60.0 + 0.8 * L_sobre_ra if L_sobre_ra <= 75.0 else 45.0 + L_sobre_ra
        limite = 0.82 * L_sobre_ra
    else:
        raise ValueError("caso debe ser 'cercha' o 'miembro de celosía'.")

    if conexion_pata_corta:
        if razon_patas <= 0:
            raise ValueError("La razón de patas debe ser positiva.")
        valor += 4.0 * (razon_patas**2 - 1.0)
    return max(valor, limite)


def esbeltez_modificada_builtup(*, tipo_conector: str, esbeltez_global: float,
                                 a: float, ri: float, Ki: float = 0.50) -> tuple[float, str]:
    """E6-1, E6-2a y E6-2b."""
    for n, v in {"esbeltez_global": esbeltez_global, "a": a, "ri": ri, "Ki": Ki}.items():
        _positivo(n, v)
    local = a / ri
    if tipo_conector == "pernos snug-tight":
        return sqrt(esbeltez_global**2 + local**2), "E6-1"
    if tipo_conector == "soldado o pernos pretensionados":
        if local <= 40.0:
            return esbeltez_global, "E6-2a"
        return sqrt(esbeltez_global**2 + (Ki * local)**2), "E6-2b"
    raise ValueError("Tipo de conector no reconocido para E6.")


def factores_e7(tipo_elemento: str) -> tuple[float, float]:
    """Tabla E7.1."""
    mapa = {
        "rigidizado excepto pared de tubo": (0.18, 1.31),
        "pared de tubo cuadrado o rectangular": (0.20, 1.38),
        "otro elemento": (0.22, 1.49),
    }
    try:
        return mapa[tipo_elemento]
    except KeyError as exc:
        raise ValueError("Tipo de elemento no reconocido para Tabla E7.1.") from exc


def ancho_efectivo_e7(*, b: float, t: float, lambda_r: float, Fy: float, Fn: float,
                       tipo_elemento: str) -> tuple[float, float, float, str]:
    """E7-2 a E7-5. Devuelve be, Fel, c1, estado."""
    for n, v in {"b": b, "t": t, "lambda_r": lambda_r, "Fy": Fy, "Fn": Fn}.items():
        _positivo(n, v)
    lam = b / t
    c1, c2 = factores_e7(tipo_elemento)
    limite = lambda_r * sqrt(Fy / Fn)
    Fel = (c2 * lambda_r / lam) ** 2 * Fy
    if lam <= limite:
        return b, Fel, c1, "E7-2"
    q = sqrt(Fel / Fn)
    be = b * (1.0 - c1 * q) * q
    return max(0.0, min(b, be)), Fel, c1, "E7-3"


def area_efectiva_desde_elementos(*, Ag: float, elementos: Iterable[dict]) -> tuple[float, list[dict]]:
    """Resta de Ag las áreas inefectivas (b-be)t de cada elemento esbelto."""
    _positivo("Ag", Ag)
    Ae = Ag
    detalle: list[dict] = []
    for elemento in elementos:
        b = float(elemento["b"])
        t = float(elemento["t"])
        be = float(elemento["be"])
        multiplicidad = int(elemento.get("multiplicidad", 1))
        perdida = max(0.0, b - be) * t * multiplicidad
        Ae -= perdida
        detalle.append({**elemento, "area_inefectiva": perdida})
    if Ae <= 0:
        raise ValueError("El área efectiva calculada no es positiva.")
    return Ae, detalle


def area_efectiva_tubo_circular(*, D: float, t: float, E: float, Fy: float, Ag: float) -> tuple[float, str]:
    """E7-6 y E7-7 para tubos circulares."""
    for n, v in {"D": D, "t": t, "E": E, "Fy": Fy, "Ag": Ag}.items():
        _positivo(n, v)
    lam = D / t
    if lam <= 0.11 * E / Fy:
        return Ag, "E7-6"
    if lam >= 0.45 * E / Fy:
        raise ValueError("D/t está fuera del intervalo de aplicabilidad mostrado para E7-7.")
    Ae = ((0.038 * E) / (Fy * lam) + 2.0 / 3.0) * Ag
    return min(Ag, Ae), "E7-7"


def ruta_capitulo_e(*, perfil: str, resultados_locales: Iterable, simetria: str,
                     miembro_builtup_dos_componentes: bool = False) -> RutaCapituloE:
    """Implementa la lógica de la Tabla User Note E1.1 para perfiles del programa."""
    esbelto = any(getattr(r, "clasificacion", "") == "ESBELTO" for r in resultados_locales)

    if miembro_builtup_dos_componentes:
        if esbelto:
            return RutaCapituloE("Miembro armado por dos perfiles", ("E6", "E7"), ("LB", "FB", "FTB"), True, simetria,
                                 "Primero se modifica la esbeltez en E6 y luego se aplica E7.")
        return RutaCapituloE("Miembro armado por dos perfiles", ("E6", "E3", "E4"), ("FB", "FTB"), False, simetria,
                             "E6 modifica la esbeltez; la resistencia se obtiene con E3/E4.")

    if perfil == "Ángulo simple":
        if esbelto:
            return RutaCapituloE(perfil, ("E5", "E7"), ("LB", "FB"), True, simetria, "Ángulo simple con elemento esbelto.")
        return RutaCapituloE(perfil, ("E3", "E4", "E5"), ("FB", "FTB"), False, simetria, "Aplican E3/E4 o el método específico E5.")

    if perfil == "Ángulo doble con separadores":
        if esbelto:
            return RutaCapituloE(perfil, ("E6", "E7"), ("LB", "FB", "FTB"), True, simetria, "Ángulo doble tratado como miembro armado.")
        return RutaCapituloE(perfil, ("E6", "E3", "E4"), ("FB", "FTB"), False, simetria, "Ángulo doble tratado como miembro armado.")

    if perfil in {"Tubo cuadrado", "Tubo rectangular", "Tubo circular"}:
        if esbelto:
            return RutaCapituloE(perfil, ("E7",), ("LB", "FB"), True, simetria, "Sección tubular con elementos esbeltos.")
        return RutaCapituloE(perfil, ("E3",), ("FB",), False, simetria, "Sección tubular sin elementos esbeltos.")

    if perfil == "Tee":
        if esbelto:
            return RutaCapituloE(perfil, ("E7",), ("LB", "FB", "FTB"), True, simetria, "Tee con elemento esbelto.")
        return RutaCapituloE(perfil, ("E3", "E4"), ("FB", "FTB"), False, simetria, "Tee sin elementos esbeltos.")

    # Perfil I y canal
    if esbelto:
        estados = ("LB", "FB", "FTB") if simetria != "Doble simetría" or perfil == "Canal" else ("LB", "FB", "TB")
        return RutaCapituloE(perfil, ("E7",), estados, True, simetria, "Al menos un elemento excede lambda_r.")
    estados = ("FB", "TB") if perfil == "Perfil I" and simetria == "Doble simetría" else ("FB", "FTB")
    return RutaCapituloE(perfil, ("E3", "E4"), estados, False, simetria, "Todos los elementos cumplen lambda <= lambda_r.")
