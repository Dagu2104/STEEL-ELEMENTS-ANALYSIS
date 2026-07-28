"""Funciones de cálculo para clasificación de elementos en compresión uniforme.

La implementación reproduce los casos incluidos en la Tabla B4.1a mostrada por
el usuario. Las relaciones geométricas deben verificarse con las definiciones de
la edición de AISC aplicable al proyecto.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from typing import Literal


Fabricacion = Literal["Rolled", "Built-up", "No aplica"]
CondicionBorde = Literal["Rigidizado", "No rigidizado", "Caso circular"]


@dataclass(frozen=True)
class ResultadoElemento:
    perfil: str
    elemento: str
    condicion_borde: CondicionBorde
    caso_tabla: str
    formula: str
    relacion: str
    lambda_real: float
    lambda_r: float
    clasificacion: str
    observacion: str = ""

    def como_dict(self) -> dict[str, object]:
        return asdict(self)


def validar_positivo(nombre: str, valor: float) -> None:
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")


def limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(valor, maximo))


def calcular_kc(h: float, tw: float) -> float:
    """Calcula kc = 4/sqrt(h/tw), limitado a 0.35 <= kc <= 0.76."""
    validar_positivo("h", h)
    validar_positivo("tw", tw)
    return limitar(4.0 / sqrt(h / tw), 0.35, 0.76)


def clasificar(lambda_real: float, lambda_r: float) -> str:
    validar_positivo("lambda real", lambda_real)
    validar_positivo("lambda_r", lambda_r)
    return "NO ESBELTO" if lambda_real <= lambda_r else "ESBELTO"


def crear_resultado(
    *,
    perfil: str,
    elemento: str,
    condicion_borde: CondicionBorde,
    caso_tabla: str,
    formula: str,
    relacion: str,
    lambda_real: float,
    lambda_r: float,
    observacion: str = "",
) -> ResultadoElemento:
    return ResultadoElemento(
        perfil=perfil,
        elemento=elemento,
        condicion_borde=condicion_borde,
        caso_tabla=caso_tabla,
        formula=formula,
        relacion=relacion,
        lambda_real=lambda_real,
        lambda_r=lambda_r,
        clasificacion=clasificar(lambda_real, lambda_r),
        observacion=observacion,
    )


def evaluar_perfil_i(
    *,
    fabricacion: str,
    bf: float,
    tf: float,
    h: float,
    tw: float,
    E: float,
    Fy: float,
) -> list[ResultadoElemento]:
    """Evalúa ala y alma de una sección I con geometría convencional."""
    for nombre, valor in {"bf": bf, "tf": tf, "h": h, "tw": tw, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)

    if fabricacion not in {"Rolled", "Built-up"}:
        raise ValueError("Para un perfil I, la fabricación debe ser 'Rolled' o 'Built-up'.")

    raiz = sqrt(E / Fy)
    lambda_ala = bf / (2.0 * tf)
    lambda_alma = h / tw

    if fabricacion == "Rolled":
        lambda_r_ala = 0.56 * raiz
        formula_ala = "0.56·√(E/Fy)"
        caso_ala = "Caso 1"
        obs_ala = "Ala de perfil I laminado; se usa b = bf/2."
    else:
        kc = calcular_kc(h, tw)
        lambda_r_ala = 0.64 * sqrt(kc * E / Fy)
        formula_ala = "0.64·√(kc·E/Fy)"
        caso_ala = "Caso 2"
        obs_ala = f"Ala de perfil I armado; kc = {kc:.3f}. Se usa b = bf/2."

    return [
        crear_resultado(
            perfil="Perfil I",
            elemento="Ala",
            condicion_borde="No rigidizado",
            caso_tabla=caso_ala,
            formula=formula_ala,
            relacion="bf/(2·tf)",
            lambda_real=lambda_ala,
            lambda_r=lambda_r_ala,
            observacion=obs_ala,
        ),
        crear_resultado(
            perfil="Perfil I",
            elemento="Alma",
            condicion_borde="Rigidizado",
            caso_tabla="Caso 5",
            formula="1.49·√(E/Fy)",
            relacion="h/tw",
            lambda_real=lambda_alma,
            lambda_r=1.49 * raiz,
            observacion="El límite del alma no cambia entre Rolled y Built-up.",
        ),
    ]


def evaluar_canal(
    *,
    b_ala: float,
    tf: float,
    h: float,
    tw: float,
    E: float,
    Fy: float,
) -> list[ResultadoElemento]:
    """Evalúa el ala saliente y el alma de un canal laminado."""
    for nombre, valor in {"b_ala": b_ala, "tf": tf, "h": h, "tw": tw, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    raiz = sqrt(E / Fy)
    return [
        crear_resultado(
            perfil="Canal",
            elemento="Ala saliente",
            condicion_borde="No rigidizado",
            caso_tabla="Caso 1",
            formula="0.56·√(E/Fy)",
            relacion="b/tf",
            lambda_real=b_ala / tf,
            lambda_r=0.56 * raiz,
            observacion="b es el ancho saliente del ala conforme a la definición de la tabla.",
        ),
        crear_resultado(
            perfil="Canal",
            elemento="Alma",
            condicion_borde="Rigidizado",
            caso_tabla="Caso 5",
            formula="1.49·√(E/Fy)",
            relacion="h/tw",
            lambda_real=h / tw,
            lambda_r=1.49 * raiz,
        ),
    ]


def evaluar_tee(
    *,
    b_ala: float,
    tf: float,
    d_vastago: float,
    tw: float,
    E: float,
    Fy: float,
) -> list[ResultadoElemento]:
    """Evalúa ala y vástago de una sección Tee."""
    for nombre, valor in {
        "b_ala": b_ala,
        "tf": tf,
        "d_vastago": d_vastago,
        "tw": tw,
        "E": E,
        "Fy": Fy,
    }.items():
        validar_positivo(nombre, valor)
    raiz = sqrt(E / Fy)
    return [
        crear_resultado(
            perfil="Tee",
            elemento="Ala saliente",
            condicion_borde="No rigidizado",
            caso_tabla="Caso 1",
            formula="0.56·√(E/Fy)",
            relacion="b/tf",
            lambda_real=b_ala / tf,
            lambda_r=0.56 * raiz,
            observacion="b es el ancho saliente de una mitad del ala.",
        ),
        crear_resultado(
            perfil="Tee",
            elemento="Vástago",
            condicion_borde="No rigidizado",
            caso_tabla="Caso 4",
            formula="0.75·√(E/Fy)",
            relacion="d/tw",
            lambda_real=d_vastago / tw,
            lambda_r=0.75 * raiz,
        ),
    ]


def evaluar_angulo(
    *,
    tipo: str,
    b1: float,
    t: float,
    E: float,
    Fy: float,
    b2: float | None = None,
) -> list[ResultadoElemento]:
    """Evalúa una o dos patas de un ángulo simple o doble con separadores."""
    for nombre, valor in {"b1": b1, "t": t, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    if b2 is not None:
        validar_positivo("b2", b2)

    limite = 0.45 * sqrt(E / Fy)
    resultados = [
        crear_resultado(
            perfil=tipo,
            elemento="Pata 1",
            condicion_borde="No rigidizado",
            caso_tabla="Caso 3",
            formula="0.45·√(E/Fy)",
            relacion="b1/t",
            lambda_real=b1 / t,
            lambda_r=limite,
        )
    ]
    if b2 is not None:
        resultados.append(
            crear_resultado(
                perfil=tipo,
                elemento="Pata 2",
                condicion_borde="No rigidizado",
                caso_tabla="Caso 3",
                formula="0.45·√(E/Fy)",
                relacion="b2/t",
                lambda_real=b2 / t,
                lambda_r=limite,
            )
        )
    return resultados


def evaluar_hss_rectangular(
    *,
    B_plano: float,
    H_plano: float,
    t: float,
    E: float,
    Fy: float,
    perfil: str,
) -> list[ResultadoElemento]:
    """Evalúa las dos direcciones de pared plana de un HSS rectangular/cuadrado."""
    for nombre, valor in {"B_plano": B_plano, "H_plano": H_plano, "t": t, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    limite = 1.40 * sqrt(E / Fy)
    return [
        crear_resultado(
            perfil=perfil,
            elemento="Pared asociada a B",
            condicion_borde="Rigidizado",
            caso_tabla="Caso 6",
            formula="1.40·√(E/Fy)",
            relacion="B_plano/t",
            lambda_real=B_plano / t,
            lambda_r=limite,
            observacion="Ingrese el ancho plano definido por la especificación, no necesariamente la dimensión exterior.",
        ),
        crear_resultado(
            perfil=perfil,
            elemento="Pared asociada a H",
            condicion_borde="Rigidizado",
            caso_tabla="Caso 6",
            formula="1.40·√(E/Fy)",
            relacion="H_plano/t",
            lambda_real=H_plano / t,
            lambda_r=limite,
            observacion="Ingrese el ancho plano definido por la especificación, no necesariamente la dimensión exterior.",
        ),
    ]


def evaluar_hss_circular(
    *,
    D: float,
    t: float,
    E: float,
    Fy: float,
) -> list[ResultadoElemento]:
    for nombre, valor in {"D": D, "t": t, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    return [
        crear_resultado(
            perfil="HSS circular",
            elemento="Pared circular",
            condicion_borde="Caso circular",
            caso_tabla="Caso 9",
            formula="0.11·E/Fy",
            relacion="D/t",
            lambda_real=D / t,
            lambda_r=0.11 * E / Fy,
        )
    ]
