"""Funciones de cálculo para la clasificación local de elementos de acero.

Implementa los casos de la Tabla B4.1a usados por la aplicación:
1, 2, 3, 4, 5, 6, 7, 8 y 9.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from typing import Literal

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


def evaluar_cubreplaca(
    *,
    perfil: str,
    nombre: str,
    b: float,
    t: float,
    E: float,
    Fy: float,
    conexion: str,
) -> ResultadoElemento:
    """Caso 7: cubreplaca de ala entre líneas de pernos o soldaduras."""
    for etiqueta, valor in {"b de cubreplaca": b, "t de cubreplaca": t, "E": E, "Fy": Fy}.items():
        validar_positivo(etiqueta, valor)
    return crear_resultado(
        perfil=perfil,
        elemento=nombre,
        condicion_borde="Rigidizado",
        caso_tabla="Caso 7",
        formula="1.40·√(E/Fy)",
        relacion="b_cp/t_cp",
        lambda_real=b / t,
        lambda_r=1.40 * sqrt(E / Fy),
        observacion=f"Cubreplaca entre líneas longitudinales de {conexion.lower()}.",
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
    cubreplacas: list[dict[str, object]] | None = None,
) -> list[ResultadoElemento]:
    for nombre, valor in {"bf": bf, "tf": tf, "h": h, "tw": tw, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    if fabricacion not in {"Rolled", "Built-up"}:
        raise ValueError("La fabricación del perfil I debe ser 'Rolled' o 'Built-up'.")

    raiz = sqrt(E / Fy)
    if fabricacion == "Rolled":
        lr_ala = 0.56 * raiz
        formula_ala = "0.56·√(E/Fy)"
        caso_ala = "Caso 1"
        obs_ala = "Ala de perfil I Rolled; se adopta b = bf/2."
    else:
        kc = calcular_kc(h, tw)
        lr_ala = 0.64 * sqrt(kc * E / Fy)
        formula_ala = "0.64·√(kc·E/Fy)"
        caso_ala = "Caso 2"
        obs_ala = f"Ala de perfil I Built-up; kc = {kc:.3f}; se adopta b = bf/2."

    resultados = [
        crear_resultado(
            perfil="Perfil I",
            elemento="Patín / ala",
            condicion_borde="No rigidizado",
            caso_tabla=caso_ala,
            formula=formula_ala,
            relacion="bf/(2·tf)",
            lambda_real=bf / (2.0 * tf),
            lambda_r=lr_ala,
            observacion=obs_ala,
        ),
        crear_resultado(
            perfil="Perfil I",
            elemento="Alma",
            condicion_borde="Rigidizado",
            caso_tabla="Caso 5",
            formula="1.49·√(E/Fy)",
            relacion="h/tw",
            lambda_real=h / tw,
            lambda_r=1.49 * raiz,
            observacion="El límite del alma es el mismo para Rolled y Built-up.",
        ),
    ]

    for cp in cubreplacas or []:
        resultados.append(
            evaluar_cubreplaca(
                perfil="Perfil I con cubreplaca",
                nombre=str(cp["nombre"]),
                b=float(cp["b"]),
                t=float(cp["t"]),
                E=E,
                Fy=Fy,
                conexion=str(cp["conexion"]),
            )
        )
    return resultados



def evaluar_perfil_i_asimetrico(
    *,
    fabricacion: str,
    bf_superior: float,
    tf_superior: float,
    bf_inferior: float,
    tf_inferior: float,
    h: float,
    tw: float,
    E: float,
    Fy: float,
    cubreplacas: list[dict[str, object]] | None = None,
) -> list[ResultadoElemento]:
    """Tabla B4.1a para una sección I monosimétrica con patines diferentes."""
    datos = {
        "bf superior": bf_superior, "tf superior": tf_superior,
        "bf inferior": bf_inferior, "tf inferior": tf_inferior,
        "h": h, "tw": tw, "E": E, "Fy": Fy,
    }
    for nombre, valor in datos.items():
        validar_positivo(nombre, valor)
    if fabricacion not in {"Rolled", "Built-up"}:
        raise ValueError("La fabricación debe ser 'Rolled' o 'Built-up'.")

    raiz = sqrt(E / Fy)
    if fabricacion == "Rolled":
        lr_ala = 0.56 * raiz
        formula = "0.56·√(E/Fy)"
        caso = "Caso 1"
        observacion = "Ala de perfil I Rolled."
    else:
        kc = calcular_kc(h, tw)
        lr_ala = 0.64 * sqrt(kc * E / Fy)
        formula = "0.64·√(kc·E/Fy)"
        caso = "Caso 2"
        observacion = f"Ala de perfil I Built-up; kc = {kc:.3f}."

    resultados = [
        crear_resultado(
            perfil="Perfil I asimétrico", elemento="Patín superior",
            condicion_borde="No rigidizado", caso_tabla=caso, formula=formula,
            relacion="bf_sup/(2·tf_sup)",
            lambda_real=bf_superior/(2.0*tf_superior), lambda_r=lr_ala,
            observacion=observacion,
        ),
        crear_resultado(
            perfil="Perfil I asimétrico", elemento="Patín inferior",
            condicion_borde="No rigidizado", caso_tabla=caso, formula=formula,
            relacion="bf_inf/(2·tf_inf)",
            lambda_real=bf_inferior/(2.0*tf_inferior), lambda_r=lr_ala,
            observacion=observacion,
        ),
        crear_resultado(
            perfil="Perfil I asimétrico", elemento="Alma",
            condicion_borde="Rigidizado", caso_tabla="Caso 5",
            formula="1.49·√(E/Fy)", relacion="h/tw",
            lambda_real=h/tw, lambda_r=1.49*raiz,
            observacion="El alma está rigidizada por ambos patines.",
        ),
    ]
    for cp in cubreplacas or []:
        resultados.append(evaluar_cubreplaca(
            perfil="Perfil I asimétrico con cubreplaca",
            nombre=str(cp["nombre"]), b=float(cp["b"]), t=float(cp["t"]),
            E=E, Fy=Fy, conexion=str(cp["conexion"]),
        ))
    return resultados


def evaluar_canal(*, b_ala: float, tf: float, h: float, tw: float, E: float, Fy: float) -> list[ResultadoElemento]:
    for nombre, valor in {"b_ala": b_ala, "tf": tf, "h": h, "tw": tw, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    raiz = sqrt(E / Fy)
    return [
        crear_resultado(
            perfil="Canal", elemento="Patín / ala saliente", condicion_borde="No rigidizado",
            caso_tabla="Caso 1", formula="0.56·√(E/Fy)", relacion="b/tf",
            lambda_real=b_ala / tf, lambda_r=0.56 * raiz,
        ),
        crear_resultado(
            perfil="Canal", elemento="Alma", condicion_borde="Rigidizado",
            caso_tabla="Caso 5", formula="1.49·√(E/Fy)", relacion="h/tw",
            lambda_real=h / tw, lambda_r=1.49 * raiz,
        ),
    ]


def evaluar_tee(*, b_ala: float, tf: float, d_vastago: float, tw: float, E: float, Fy: float) -> list[ResultadoElemento]:
    for nombre, valor in {"b_ala": b_ala, "tf": tf, "d_vastago": d_vastago, "tw": tw, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    raiz = sqrt(E / Fy)
    return [
        crear_resultado(
            perfil="Tee", elemento="Patín / ala saliente", condicion_borde="No rigidizado",
            caso_tabla="Caso 1", formula="0.56·√(E/Fy)", relacion="b/tf",
            lambda_real=b_ala / tf, lambda_r=0.56 * raiz,
        ),
        crear_resultado(
            perfil="Tee", elemento="Vástago", condicion_borde="No rigidizado",
            caso_tabla="Caso 4", formula="0.75·√(E/Fy)", relacion="d/tw",
            lambda_real=d_vastago / tw, lambda_r=0.75 * raiz,
        ),
    ]


def evaluar_angulo(*, tipo: str, b1: float, b2: float, t: float, E: float, Fy: float) -> list[ResultadoElemento]:
    for nombre, valor in {"b1": b1, "b2": b2, "t": t, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    limite = 0.45 * sqrt(E / Fy)
    return [
        crear_resultado(
            perfil=tipo, elemento="Pata 1", condicion_borde="No rigidizado",
            caso_tabla="Caso 3", formula="0.45·√(E/Fy)", relacion="b1/t",
            lambda_real=b1 / t, lambda_r=limite,
        ),
        crear_resultado(
            perfil=tipo, elemento="Pata 2", condicion_borde="No rigidizado",
            caso_tabla="Caso 3", formula="0.45·√(E/Fy)", relacion="b2/t",
            lambda_real=b2 / t, lambda_r=limite,
        ),
    ]


def evaluar_tubo_rectangular(
    *,
    B_plano: float,
    H_plano: float,
    t: float,
    E: float,
    Fy: float,
    perfil: str,
    fabricacion: str,
) -> list[ResultadoElemento]:
    """Tubo Rolled -> caso 6; cajón Built-up -> caso 8."""
    for nombre, valor in {"B_plano": B_plano, "H_plano": H_plano, "t": t, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    if fabricacion == "Rolled":
        coef = 1.40
        caso = "Caso 6"
        observacion = "Tubo comercial Rolled; usar el ancho plano definido por la especificación aplicable."
    elif fabricacion == "Built-up":
        coef = 1.49
        caso = "Caso 8"
        observacion = "Sección cajón Built-up formada por placas soldadas; cada placa está rigidizada en ambos bordes."
    else:
        raise ValueError("La fabricación del tubo debe ser 'Rolled' o 'Built-up'.")

    limite = coef * sqrt(E / Fy)
    return [
        crear_resultado(
            perfil=perfil, elemento="Pared horizontal", condicion_borde="Rigidizado",
            caso_tabla=caso, formula=f"{coef:.2f}·√(E/Fy)", relacion="B_plano/t",
            lambda_real=B_plano / t, lambda_r=limite, observacion=observacion,
        ),
        crear_resultado(
            perfil=perfil, elemento="Pared vertical", condicion_borde="Rigidizado",
            caso_tabla=caso, formula=f"{coef:.2f}·√(E/Fy)", relacion="H_plano/t",
            lambda_real=H_plano / t, lambda_r=limite, observacion=observacion,
        ),
    ]


def evaluar_tubo_circular(*, D: float, t: float, E: float, Fy: float) -> list[ResultadoElemento]:
    for nombre, valor in {"D": D, "t": t, "E": E, "Fy": Fy}.items():
        validar_positivo(nombre, valor)
    return [
        crear_resultado(
            perfil="Tubo circular", elemento="Pared circular", condicion_borde="Caso circular",
            caso_tabla="Caso 9", formula="0.11·E/Fy", relacion="D/t",
            lambda_real=D / t, lambda_r=0.11 * E / Fy,
        )
    ]
