"""AISC 360-22 — Capítulo G: diseño de miembros a cortante.

El módulo trabaja exclusivamente con el sistema interno de la aplicación:
- longitudes en mm
- esfuerzos en MPa = N/mm²
- fuerzas en N

Alcance implementado:
- G2.1: perfiles I y canales, con o sin rigidizadores transversales.
- G2.2: paneles interiores con acción de campo de tracción.
- G2.3: no se calcula; se reporta la necesidad de análisis especializado.
- G2.4: necesidad y verificación geométrica/inercial de rigidizadores.
- G3: ángulos simples y tees.
- G4: HSS rectangulares, cajones y otras secciones simétricas.
- G5: HSS circulares.
- G6: cortante respecto al eje menor.
- G7: advertencia para aberturas en el alma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Iterable, Sequence


PHI_V_GENERAL = 0.90
OMEGA_V_GENERAL = 1.67
PHI_V_G21A = 1.00
OMEGA_V_G21A = 1.50


@dataclass(frozen=True)
class RutaCapituloG:
    seccion: str
    descripcion: str
    elemento_resistente: str
    ecuaciones_principales: tuple[str, ...]
    advertencias: tuple[str, ...] = ()


@dataclass(frozen=True)
class EstadoCortante:
    estado: str
    ecuacion: str
    Vn: float
    phi_v: float = PHI_V_GENERAL
    omega_v: float = OMEGA_V_GENERAL
    lambda_v: float | None = None
    kv: float | None = None
    Cv: float | None = None
    Fcr: float | None = None
    observacion: str = ""

    @property
    def phi_Vn(self) -> float:
        return self.phi_v * self.Vn

    @property
    def Vn_sobre_omega(self) -> float:
        return self.Vn / self.omega_v


@dataclass(frozen=True)
class ResultadoCortante:
    seccion: str
    estados: tuple[EstadoCortante, ...]
    adoptado: EstadoCortante
    observaciones: tuple[str, ...] = ()

    @property
    def Vn(self) -> float:
        return self.adoptado.Vn

    @property
    def phi_Vn(self) -> float:
        return self.adoptado.phi_Vn

    @property
    def Vn_sobre_omega(self) -> float:
        return self.adoptado.Vn_sobre_omega


@dataclass(frozen=True)
class ResultadoPanelG2:
    tipo_panel: str
    a: float
    a_sobre_h: float
    g21: EstadoCortante
    g22: EstadoCortante | None
    adoptado: EstadoCortante
    Cv2: float
    Vn_Cv2: float
    observaciones: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoRigidizadorG24:
    lambda_st: float
    lambda_limite: float
    cumple_esbeltez: bool
    Ist_proporcionado: float
    Ist_requerido: float
    cumple_inercia: bool
    Ist1: float
    Ist2: float
    rho_st: float
    rho_w: float
    demanda_supera_panel: bool
    observaciones: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoSeparacionG2:
    requiere_rigidizadores: bool
    es_posible: bool
    a_max: float | None
    estado_a_max: EstadoCortante | None
    estado_limite: EstadoCortante
    capacidad_sin_rigidizadores: float
    capacidad_maxima_panel: float
    observaciones: tuple[str, ...] = ()


def _positivo(nombre: str, valor: float) -> None:
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")


def _no_negativo(nombre: str, valor: float) -> None:
    if valor < 0:
        raise ValueError(f"{nombre} no puede ser negativo.")


def ruta_capitulo_g(perfil: str, eje: str) -> RutaCapituloG:
    """Selecciona automáticamente la sección del Capítulo G."""
    if eje not in {"x-x", "y-y"}:
        raise ValueError("El eje debe ser x-x o y-y.")

    if perfil in {"Perfil I", "Perfil I asimétrico", "Canal"}:
        if eje == "x-x":
            return RutaCapituloG(
                "G2",
                "Cortante paralelo al alma, asociado a flexión alrededor de x-x.",
                "Alma",
                ("G2-1", "G2-2 a G2-5", "G2-6 a G2-11", "G2-16 a G2-19"),
            )
        return RutaCapituloG(
            "G6",
            "Cortante respecto al eje menor; los patines son los elementos resistentes.",
            "Patines",
            ("G6-1",),
        )

    if perfil == "Tee":
        if eje == "x-x":
            return RutaCapituloG(
                "G3",
                "El cortante paralelo al vástago se verifica mediante G3.",
                "Vástago",
                ("G3-1",),
            )
        return RutaCapituloG(
            "G6",
            "Cortante respecto al eje menor; el patín de la Tee es el elemento resistente.",
            "Patín",
            ("G6-1",),
        )

    if perfil == "Ángulo simple":
        return RutaCapituloG(
            "G3",
            "La pata seleccionada que resiste el cortante se verifica mediante G3.",
            "Pata del ángulo",
            ("G3-1",),
        )

    if perfil == "Ángulo doble con separadores":
        if eje == "x-x":
            return RutaCapituloG(
                "G4",
                "Las patas paralelas al cortante se tratan como elementos resistentes de una sección doblemente simétrica.",
                "Dos patas paralelas al cortante",
                ("G4-1",),
                ("La transferencia de cortante entre ambos ángulos y sus separadores debe verificarse por separado.",),
            )
        return RutaCapituloG(
            "G6",
            "Cortante respecto al eje menor; se suman las patas que resisten el cortante.",
            "Patas horizontales",
            ("G6-1",),
            ("La conexión entre los ángulos debe ser capaz de desarrollar la resistencia calculada.",),
        )

    if perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        return RutaCapituloG(
            "G4",
            "Las dos paredes paralelas a la dirección del cortante resisten mediante G4.",
            "Dos paredes del tubo o cajón",
            ("G4-1",),
        )

    if perfil == "Tubo circular":
        return RutaCapituloG(
            "G5",
            "El HSS circular se verifica por fluencia y pandeo por cortante mediante G5.",
            "Sección circular completa",
            ("G5-1", "G5-2a", "G5-2b"),
        )

    raise ValueError(f"No existe una ruta de cortante implementada para {perfil}.")


def coeficiente_cv2(*, lambda_v: float, kv: float, E: float, Fy: float) -> tuple[float, str]:
    """Coeficiente C_v2 de G2.2, usado también por G3, G4 y G6."""
    for n, v in {"lambda_v": lambda_v, "kv": kv, "E": E, "Fy": Fy}.items():
        _positivo(n, v)
    limite_1 = 1.10 * sqrt(kv * E / Fy)
    limite_2 = 1.37 * sqrt(kv * E / Fy)
    if lambda_v <= limite_1:
        return 1.0, "G2-9"
    if lambda_v <= limite_2:
        return 1.10 * sqrt(kv * E / Fy) / lambda_v, "G2-10"
    return 1.51 * kv * E / (lambda_v**2 * Fy), "G2-11"


def kv_panel(*, a: float | None, h: float) -> tuple[float, str]:
    """k_v de G2.1(b)(2). Sin rigidizadores se adopta 5.34."""
    _positivo("h", h)
    if a is None:
        return 5.34, "Sin rigidizadores transversales: kv = 5.34."
    _positivo("a", a)
    razon = a / h
    if razon > 3.0:
        return 5.34, "a/h > 3.0; G2-5 limita kv a 5.34."
    return 5.0 + 5.0 / razon**2, "G2-5."


def _estado_g21(
    *, perfil: str, fabricacion: str | None, E: float, Fy: float,
    h: float, tw: float, d: float, a: float | None,
) -> EstadoCortante:
    for n, v in {"E": E, "Fy": Fy, "h": h, "tw": tw, "d": d}.items():
        _positivo(n, v)
    lambda_v = h / tw
    Aw = d * tw

    es_i_laminada = perfil in {"Perfil I", "Perfil I asimétrico"} and fabricacion == "Rolled"
    limite_g21a = 2.24 * sqrt(E / Fy)
    if es_i_laminada and lambda_v <= limite_g21a:
        return EstadoCortante(
            "Resistencia del alma sin acción de campo de tracción",
            "G2-1 / G2-2",
            0.6 * Fy * Aw,
            phi_v=PHI_V_G21A,
            omega_v=OMEGA_V_G21A,
            lambda_v=lambda_v,
            kv=None,
            Cv=1.0,
            observacion=(
                f"Perfil I laminado con h/tw={lambda_v:.3f} ≤ "
                f"2.24√(E/Fy)={limite_g21a:.3f}; Cv1=1.0, ϕv=1.00 y Ωv=1.50."
            ),
        )

    kv, obs_kv = kv_panel(a=a, h=h)
    limite = 1.10 * sqrt(kv * E / Fy)
    if lambda_v <= limite:
        Cv1 = 1.0
        eq = "G2-1 / G2-3"
    else:
        Cv1 = 1.10 * sqrt(kv * E / Fy) / lambda_v
        eq = "G2-1 / G2-4"
    return EstadoCortante(
        "Resistencia del alma sin acción de campo de tracción",
        eq,
        0.6 * Fy * Aw * Cv1,
        lambda_v=lambda_v,
        kv=kv,
        Cv=Cv1,
        observacion=f"{obs_kv} h/tw={lambda_v:.3f}; límite={limite:.3f}.",
    )


def calcular_g2_sin_rigidizadores(
    *, perfil: str, fabricacion: str | None, E: float, Fy: float,
    h: float, tw: float, d: float,
) -> ResultadoCortante:
    estado = _estado_g21(
        perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
        h=h, tw=tw, d=d, a=None,
    )
    return ResultadoCortante("G2.1", (estado,), estado, (
        "Cálculo base con kv=5.34 cuando no aplica la excepción G2.1(a).",
    ))


def calcular_g2_panel(
    *, perfil: str, fabricacion: str | None, tipo_panel: str,
    E: float, Fy: float, h: float, tw: float, d: float, a: float,
    Afc: float, Aft: float, bfc: float, bft: float,
    usar_campo_traccion: bool,
) -> ResultadoPanelG2:
    """Calcula un panel delimitado por rigidizadores.

    Para paneles extremos se usa G2.1 de forma conservadora. G2.3 no se
    implementa. Para paneles interiores puede activarse G2.2.
    """
    if tipo_panel not in {"Extremo", "Interior"}:
        raise ValueError("tipo_panel debe ser 'Extremo' o 'Interior'.")
    for n, v in {
        "E": E, "Fy": Fy, "h": h, "tw": tw, "d": d, "a": a,
        "Afc": Afc, "Aft": Aft, "bfc": bfc, "bft": bft,
    }.items():
        _positivo(n, v)

    g21 = _estado_g21(
        perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
        h=h, tw=tw, d=d, a=a,
    )
    kv, _ = kv_panel(a=a, h=h)
    lam = h / tw
    Cv2, eq_cv2 = coeficiente_cv2(lambda_v=lam, kv=kv, E=E, Fy=Fy)
    Aw = d * tw
    Vn_Cv2 = 0.6 * Fy * Aw * Cv2
    observaciones: list[str] = []

    if tipo_panel == "Extremo":
        observaciones.append(
            "El panel extremo se verifica conservadoramente mediante G2.1. "
            "La resistencia adicional de G2.3 no está implementada."
        )
        return ResultadoPanelG2(
            tipo_panel, a, a / h, g21, None, g21, Cv2, Vn_Cv2,
            tuple(observaciones),
        )

    if not usar_campo_traccion:
        observaciones.append("No se aprovechó la acción de campo de tracción de G2.2.")
        return ResultadoPanelG2(
            tipo_panel, a, a / h, g21, None, g21, Cv2, Vn_Cv2,
            tuple(observaciones),
        )

    if a / h > 3.0:
        raise ValueError("G2.2 requiere a/h ≤ 3.0 para considerar acción de campo de tracción.")

    limite_1 = 1.10 * sqrt(kv * E / Fy)
    if lam <= limite_1:
        Vn_tfa = 0.6 * Fy * Aw
        eq = "G2-6"
        obs = f"h/tw={lam:.3f} ≤ {limite_1:.3f}; no se requiere aporte postpandeo adicional."
    else:
        cumple_geometria = (
            2.0 * Aw / (Afc + Aft) <= 2.5
            and h / bfc <= 6.0
            and h / bft <= 6.0
        )
        if cumple_geometria:
            factor = Cv2 + (1.0 - Cv2) / (1.15 * sqrt(1.0 + (a / h) ** 2))
            Vn_tfa = 0.6 * Fy * Aw * factor
            eq = "G2-7"
            obs = "Cumple las tres condiciones geométricas de G2.2(b)(1)."
        else:
            factor = Cv2 + (1.0 - Cv2) / (1.15 * (a / h + sqrt(1.0 + (a / h) ** 2)))
            Vn_tfa = 0.6 * Fy * Aw * factor
            eq = "G2-8"
            obs = "No cumple al menos una condición geométrica de G2.2(b)(1); se usa G2-8."

    g22 = EstadoCortante(
        "Panel interior con acción de campo de tracción",
        f"{eq} / {eq_cv2}",
        Vn_tfa,
        lambda_v=lam,
        kv=kv,
        Cv=Cv2,
        observacion=(
            f"a/h={a/h:.3f}; Cv2={Cv2:.4f}. {obs} "
            "La norma permite tomar el mayor valor entre G2.1 y G2.2."
        ),
    )
    adoptado = g22 if g22.Vn >= g21.Vn else g21
    observaciones.append("Se adoptó el mayor Vn permitido entre G2.1 y G2.2.")
    return ResultadoPanelG2(
        tipo_panel, a, a / h, g21, g22, adoptado, Cv2, Vn_Cv2,
        tuple(observaciones),
    )


def calcular_separacion_maxima_g2(
    *, perfil: str, fabricacion: str | None, E: float, Fy: float,
    h: float, tw: float, d: float, cortante_requerido: float,
    metodo: str, tolerancia_relativa: float = 1e-8, iteraciones: int = 100,
) -> ResultadoSeparacionG2:
    """Calcula la mayor separación ``a`` que permite cumplir G2.1.

    El cálculo se realiza de manera conservadora para el panel extremo, sin
    aprovechar la resistencia postpandeo de G2.3. Por ello, el valor obtenido
    también puede emplearse como separación uniforme para los paneles de la
    zona próxima al apoyo.

    La búsqueda queda limitada a ``a/h <= 3``. Para ``a/h > 3`` la expresión
    de G2-5 deja de incrementar ``k_v`` y se adopta ``k_v = 5.34``.
    """
    for nombre, valor in {
        "E": E, "Fy": Fy, "h": h, "tw": tw, "d": d,
        "cortante requerido": cortante_requerido,
    }.items():
        _positivo(nombre, valor)
    if metodo not in {"LRFD", "ASD"}:
        raise ValueError("El método debe ser LRFD o ASD.")
    if tolerancia_relativa <= 0:
        raise ValueError("La tolerancia relativa debe ser mayor que cero.")
    if iteraciones < 10:
        raise ValueError("Se requieren al menos 10 iteraciones para la búsqueda.")

    estado_base = _estado_g21(
        perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
        h=h, tw=tw, d=d, a=None,
    )
    capacidad_base = capacidad_disponible(estado_base, metodo)

    # Se aproxima a a -> 0 para obtener el máximo de G2.1, que corresponde
    # a Cv=1.0 cuando la geometría y el material permiten alcanzarlo.
    a_min = max(h * 1e-7, 1e-7)
    estado_limite = _estado_g21(
        perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
        h=h, tw=tw, d=d, a=a_min,
    )
    capacidad_maxima = capacidad_disponible(estado_limite, metodo)

    if cortante_requerido <= capacidad_base * (1.0 + tolerancia_relativa):
        return ResultadoSeparacionG2(
            requiere_rigidizadores=False, es_posible=True, a_max=None,
            estado_a_max=None, estado_limite=estado_limite,
            capacidad_sin_rigidizadores=capacidad_base,
            capacidad_maxima_panel=capacidad_maxima,
            observaciones=(
                "La resistencia sin rigidizadores ya es suficiente para la demanda ingresada.",
            ),
        )

    if cortante_requerido > capacidad_maxima * (1.0 + tolerancia_relativa):
        return ResultadoSeparacionG2(
            requiere_rigidizadores=True, es_posible=False, a_max=None,
            estado_a_max=None, estado_limite=estado_limite,
            capacidad_sin_rigidizadores=capacidad_base,
            capacidad_maxima_panel=capacidad_maxima,
            observaciones=(
                "Ni llevando Cv a 1.00 mediante una separación muy pequeña el panel extremo "
                "alcanza la demanda. Debe aumentarse o reforzarse el alma, seleccionarse otra "
                "sección o estudiarse G2.3 mediante un análisis especializado.",
            ),
        )

    a_superior = 3.0 * h
    estado_superior = _estado_g21(
        perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
        h=h, tw=tw, d=d, a=a_superior,
    )
    capacidad_superior = capacidad_disponible(estado_superior, metodo)

    if capacidad_superior >= cortante_requerido:
        a_max = a_superior
        estado_a_max = estado_superior
    else:
        # En el intervalo (0, 3h] la capacidad disminuye al aumentar a.
        inferior = a_min       # cumple
        superior = a_superior  # no cumple
        estado_a_max = estado_limite
        for _ in range(iteraciones):
            medio = 0.5 * (inferior + superior)
            estado_medio = _estado_g21(
                perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
                h=h, tw=tw, d=d, a=medio,
            )
            capacidad_medio = capacidad_disponible(estado_medio, metodo)
            if capacidad_medio >= cortante_requerido:
                inferior = medio
                estado_a_max = estado_medio
            else:
                superior = medio
            if (superior - inferior) / max(h, 1.0) <= tolerancia_relativa:
                break
        a_max = inferior

    return ResultadoSeparacionG2(
        requiere_rigidizadores=True, es_posible=True, a_max=a_max,
        estado_a_max=estado_a_max, estado_limite=estado_limite,
        capacidad_sin_rigidizadores=capacidad_base,
        capacidad_maxima_panel=capacidad_maxima,
        observaciones=(
            "a_max se obtuvo con G2.1 para el panel extremo, sin aprovechar G2.3; "
            "la separación adoptada debe ser menor o igual que este valor.",
            "La cantidad de paneles no suma resistencias: cada panel se verifica con el "
            "cortante máximo adoptado para la zona.",
        ),
    )


def rigidizadores_requeridos_g24(
    *, E: float, Fy: float, h: float, tw: float,
    resistencia_disponible_sin_rigidizadores: float,
    cortante_requerido: float | None,
    Cv_sin_rigidizadores: float | None = None,
) -> tuple[bool | None, tuple[str, ...]]:
    """Diagnóstico de necesidad y utilidad de rigidizadores según G2.4(a).

    Devuelve:
    - False: no son exigidos por resistencia para la demanda ingresada.
    - True: la demanda excede la capacidad y Cv<1, por lo que pueden aumentar
      la resistencia al pandeo del alma.
    - None: falta demanda o la sección falla con Cv=1; en este último caso
      los rigidizadores no resuelven la insuficiencia de fluencia.
    """
    for n, v in {"E": E, "Fy": Fy, "h": h, "tw": tw}.items():
        _positivo(n, v)
    _positivo("resistencia disponible", resistencia_disponible_sin_rigidizadores)
    if Cv_sin_rigidizadores is not None:
        _positivo("Cv sin rigidizadores", Cv_sin_rigidizadores)

    lam = h / tw
    limite = 2.54 * sqrt(E / Fy)
    obs: list[str] = []

    if cortante_requerido is None:
        if lam <= limite:
            obs.append(
                f"h/tw={lam:.3f} ≤ 2.54√(E/Fy)={limite:.3f}; G2.4(a) no exige "
                "rigidizadores por el criterio geométrico."
            )
        else:
            obs.append(
                "h/tw supera el límite geométrico. Sin un cortante requerido no puede "
                "concluirse si la resistencia disponible sin rigidizadores es suficiente."
            )
        return None, tuple(obs)

    _no_negativo("cortante requerido", cortante_requerido)
    if resistencia_disponible_sin_rigidizadores >= cortante_requerido:
        if lam <= limite:
            obs.append(
                f"h/tw={lam:.3f} ≤ 2.54√(E/Fy)={limite:.3f} y la resistencia "
                "disponible supera la demanda; no se requieren rigidizadores por cortante."
            )
        else:
            obs.append(
                "Aunque h/tw supera el límite geométrico, la resistencia disponible sin "
                "rigidizadores es mayor o igual que el cortante requerido; G2.4(a) no los "
                "exige por resistencia."
            )
        return False, tuple(obs)

    if Cv_sin_rigidizadores is not None and Cv_sin_rigidizadores >= 1.0 - 1e-9:
        obs.append(
            "La demanda excede la resistencia, pero Cv=1.00: gobierna la fluencia del alma. "
            "Los rigidizadores transversales no aumentan el límite 0.6FyAw; debe modificarse "
            "el área resistente o la sección."
        )
        return None, tuple(obs)

    obs.append(
        "La resistencia disponible sin rigidizadores es menor que el cortante requerido y "
        "Cv<1.00; la resistencia está reducida por pandeo del alma. Los rigidizadores pueden "
        "aumentar kv y Cv, y los paneles interiores pueden aprovechar G2.2 cuando corresponda."
    )
    return True, tuple(obs)


def verificar_rigidizador_g24(
    *, E: float, Fyw: float, Fyst: float, h: float, tw: float, a: float,
    b_st: float, t_st: float, numero_placas: int,
    Vr: float, Vc1: float, Vc2: float,
) -> ResultadoRigidizadorG24:
    """Verifica esbeltez e inercia de rigidizadores mediante G2-16 a G2-19.

    Vc1 y Vc2 deben ser resistencias disponibles, no nominales, calculadas con
    el mismo método (LRFD o ASD) que Vr.
    """
    for n, v in {
        "E": E, "Fyw": Fyw, "Fyst": Fyst, "h": h, "tw": tw,
        "a": a, "b_st": b_st, "t_st": t_st, "Vc1": Vc1, "Vc2": Vc2,
    }.items():
        _positivo(n, v)
    _no_negativo("Vr", Vr)
    if numero_placas not in {1, 2}:
        raise ValueError("numero_placas debe ser 1 o 2.")

    lambda_st = b_st / t_st
    lambda_limite = 0.56 * sqrt(E / Fyst)
    cumple_esbeltez = lambda_st <= lambda_limite

    rho_st = max(Fyw / Fyst, 1.0)
    Ist1 = h**4 * rho_st**1.3 / 40.0 * (Fyw / E) ** 1.5
    bp = min(a, h)
    Ist2_base = (2.5 / (a / h) ** 2 - 2.0) * bp * tw**3
    Ist2 = max(Ist2_base, 0.5 * bp * tw**3)

    demanda_supera_panel = Vr > Vc1 + 1e-9
    if Vr <= Vc2:
        rho_w = 0.0
    elif Vc1 > Vc2 + 1e-12:
        rho_w = max((Vr - Vc2) / (Vc1 - Vc2), 0.0)
    else:
        rho_w = 1.0 if Vr > Vc2 else 0.0
    Ist_requerido = Ist2 + (Ist1 - Ist2) * rho_w

    if numero_placas == 1:
        # Eje en la cara de la placa que está en contacto con el alma.
        Ist_proporcionado = t_st * b_st**3 / 3.0
        descripcion_eje = "un rigidizador; I respecto a la cara en contacto con el alma"
    else:
        # Dos placas iguales, una a cada lado; eje en el plano medio del alma.
        distancia = tw / 2.0 + b_st / 2.0
        Ist_proporcionado = 2.0 * (
            t_st * b_st**3 / 12.0 + b_st * t_st * distancia**2
        )
        descripcion_eje = "par de rigidizadores; I respecto al plano medio del alma"

    obs = [descripcion_eje]
    if rho_w > 1.0:
        obs.append(
            "ρw > 1.0 porque Vr supera Vc1; aumentar únicamente la inercia del rigidizador "
            "no corrige la insuficiencia de resistencia del panel."
        )
    return ResultadoRigidizadorG24(
        lambda_st=lambda_st,
        lambda_limite=lambda_limite,
        cumple_esbeltez=cumple_esbeltez,
        Ist_proporcionado=Ist_proporcionado,
        Ist_requerido=Ist_requerido,
        cumple_inercia=Ist_proporcionado >= Ist_requerido,
        Ist1=Ist1,
        Ist2=Ist2,
        rho_st=rho_st,
        rho_w=rho_w,
        demanda_supera_panel=demanda_supera_panel,
        observaciones=tuple(obs),
    )


def calcular_g3(
    *, E: float, Fy: float, b: float, t: float, multiplicidad: int = 1,
    descripcion: str = "Elemento resistente",
) -> ResultadoCortante:
    for n, v in {"E": E, "Fy": Fy, "b": b, "t": t}.items():
        _positivo(n, v)
    if multiplicidad < 1:
        raise ValueError("multiplicidad debe ser al menos 1.")
    lam = b / t
    kv = 1.2
    Cv2, eq_cv = coeficiente_cv2(lambda_v=lam, kv=kv, E=E, Fy=Fy)
    Vn = multiplicidad * 0.6 * Fy * b * t * Cv2
    estado = EstadoCortante(
        f"Cortante en {descripcion}", f"G3-1 / {eq_cv}", Vn,
        lambda_v=lam, kv=kv, Cv=Cv2,
        observacion=f"Se consideraron {multiplicidad} elemento(s) iguales.",
    )
    return ResultadoCortante("G3", (estado,), estado)


def calcular_g4(
    *, E: float, Fy: float, h: float, t: float, numero_almas: int = 2,
    descripcion: str = "Paredes resistentes",
) -> ResultadoCortante:
    for n, v in {"E": E, "Fy": Fy, "h": h, "t": t}.items():
        _positivo(n, v)
    if numero_almas < 1:
        raise ValueError("numero_almas debe ser al menos 1.")
    lam = h / t
    kv = 5.0
    Cv2, eq_cv = coeficiente_cv2(lambda_v=lam, kv=kv, E=E, Fy=Fy)
    Aw = numero_almas * h * t
    estado = EstadoCortante(
        f"Cortante en {descripcion}", f"G4-1 / {eq_cv}", 0.6 * Fy * Aw * Cv2,
        lambda_v=lam, kv=kv, Cv=Cv2,
        observacion=f"Aw={numero_almas}·h·t; h={h:.3f} mm.",
    )
    return ResultadoCortante("G4", (estado,), estado)


def calcular_g5(
    *, E: float, Fy: float, Ag: float, D: float, t: float, Lv: float,
) -> ResultadoCortante:
    for n, v in {"E": E, "Fy": Fy, "Ag": Ag, "D": D, "t": t, "Lv": Lv}.items():
        _positivo(n, v)
    Dt = D / t
    Fcr_1 = 1.60 * E / (sqrt(Lv / D) * Dt ** (5.0 / 4.0))
    Fcr_2 = 0.78 * E / Dt ** (3.0 / 2.0)
    Fcr_sin_limite = max(Fcr_1, Fcr_2)
    Fcr = min(Fcr_sin_limite, 0.6 * Fy)
    estado = EstadoCortante(
        "Fluencia o pandeo por cortante", "G5-1 / G5-2a / G5-2b",
        Fcr * Ag / 2.0,
        Fcr=Fcr,
        observacion=(
            f"Fcr,G5-2a={Fcr_1:.4f} MPa; Fcr,G5-2b={Fcr_2:.4f} MPa; "
            f"se adopta el mayor y se limita a 0.6Fy={0.6*Fy:.4f} MPa."
        ),
    )
    return ResultadoCortante("G5", (estado,), estado)


def calcular_g6(
    *, E: float, Fy: float,
    elementos: Sequence[tuple[str, float, float, float]],
) -> ResultadoCortante:
    """G6 para una lista de elementos (nombre, bf, tf, divisor de lambda).

    lambda_v = bf/(divisor*tf). Para perfiles I y tees el divisor es 2;
    para canales se usa 1.
    """
    if not elementos:
        raise ValueError("Debe existir al menos un elemento resistente a cortante.")
    estados: list[EstadoCortante] = []
    Vn_total = 0.0
    for nombre, bf, tf, divisor in elementos:
        for n, v in {"bf": bf, "tf": tf, "divisor": divisor}.items():
            _positivo(f"{n} de {nombre}", v)
        lam = bf / (divisor * tf)
        kv = 1.2
        Cv2, eq_cv = coeficiente_cv2(lambda_v=lam, kv=kv, E=E, Fy=Fy)
        Vn = 0.6 * Fy * bf * tf * Cv2
        Vn_total += Vn
        estados.append(EstadoCortante(
            f"Cortante en {nombre}", f"G6-1 / {eq_cv}", Vn,
            lambda_v=lam, kv=kv, Cv=Cv2,
            observacion=f"λv=bf/({divisor:g}tf).",
        ))
    total = EstadoCortante(
        "Suma de elementos resistentes", "G6-1", Vn_total,
        observacion="La resistencia nominal es la suma de los elementos que resisten el cortante.",
    )
    return ResultadoCortante("G6", tuple(estados) + (total,), total)


def capacidad_disponible(estado: EstadoCortante, metodo: str) -> float:
    if metodo == "LRFD":
        return estado.phi_Vn
    if metodo == "ASD":
        return estado.Vn_sobre_omega
    raise ValueError("El método debe ser LRFD o ASD.")
