"""Cálculo de propiedades geométricas de perfiles estándar.

Las secciones abiertas se representan mediante rectángulos sin traslape.
Los tubos rectangulares/cuadrados se calculan como cajones de esquinas rectas;
para perfiles Rolled el resultado es una aproximación geométrica que no incluye
el radio real de las esquinas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import atan2, cos, pi, sin, sqrt
from typing import Iterable


@dataclass(frozen=True)
class Rectangulo:
    x: float
    y: float
    b: float
    h: float
    nombre: str = ""

    @property
    def area(self) -> float:
        return self.b * self.h

    @property
    def xc(self) -> float:
        return self.x + self.b / 2.0

    @property
    def yc(self) -> float:
        return self.y + self.h / 2.0


@dataclass(frozen=True)
class PropiedadesSeccion:
    perfil: str
    Ag: float
    x_bar: float
    y_bar: float
    Ix: float
    Iy: float
    Ixy: float
    rx: float
    ry: float
    I1: float
    I2: float
    r1: float
    r2: float
    theta_p_deg: float
    Sx_sup: float
    Sx_inf: float
    Sy_der: float
    Sy_izq: float
    Zx: float
    Zy: float
    J: float
    Cw: float | None
    ancho_total: float
    altura_total: float
    observacion: str = ""

    def como_dict(self) -> dict[str, object]:
        return asdict(self)


def _positivo(nombre: str, valor: float) -> None:
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")


def _validar_rectangulos(rects: Iterable[Rectangulo]) -> list[Rectangulo]:
    lista = list(rects)
    if not lista:
        raise ValueError("La sección debe contener al menos un rectángulo.")
    for r in lista:
        _positivo(f"ancho de {r.nombre or 'rectángulo'}", r.b)
        _positivo(f"alto de {r.nombre or 'rectángulo'}", r.h)
    return lista


def _area_debajo(rects: list[Rectangulo], y: float) -> float:
    total = 0.0
    for r in rects:
        alto = min(max(y - r.y, 0.0), r.h)
        total += r.b * alto
    return total


def _area_izquierda(rects: list[Rectangulo], x: float) -> float:
    total = 0.0
    for r in rects:
        ancho = min(max(x - r.x, 0.0), r.b)
        total += r.h * ancho
    return total


def _biseccion_area(rects: list[Rectangulo], direccion: str, objetivo: float) -> float:
    if direccion == "y":
        lo = min(r.y for r in rects)
        hi = max(r.y + r.h for r in rects)
        funcion = lambda v: _area_debajo(rects, v)
    else:
        lo = min(r.x for r in rects)
        hi = max(r.x + r.b for r in rects)
        funcion = lambda v: _area_izquierda(rects, v)
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if funcion(mid) < objetivo:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _integral_abs_interval(a: float, b: float, c: float) -> float:
    """Integral de |u-c| du entre a y b."""
    if c <= a:
        return 0.5 * ((b - c) ** 2 - (a - c) ** 2)
    if c >= b:
        return 0.5 * ((c - a) ** 2 - (c - b) ** 2)
    return 0.5 * ((c - a) ** 2 + (b - c) ** 2)


def _j_rectangulo(a: float, b: float) -> float:
    """Constante torsional de Saint-Venant aproximada de un rectángulo macizo."""
    largo, corto = max(a, b), min(a, b)
    beta = corto / largo
    return largo * corto**3 * (1.0 / 3.0 - 0.21 * beta * (1.0 - beta**4 / 12.0))


def propiedades_rectangulos(
    perfil: str,
    rectangulos: Iterable[Rectangulo],
    *,
    observacion: str = "",
    Cw: float | None = None,
    J_override: float | None = None,
) -> PropiedadesSeccion:
    rects = _validar_rectangulos(rectangulos)
    Ag = sum(r.area for r in rects)
    x_bar = sum(r.area * r.xc for r in rects) / Ag
    y_bar = sum(r.area * r.yc for r in rects) / Ag

    Ix = sum(r.b * r.h**3 / 12.0 + r.area * (r.yc - y_bar) ** 2 for r in rects)
    Iy = sum(r.h * r.b**3 / 12.0 + r.area * (r.xc - x_bar) ** 2 for r in rects)
    Ixy = sum(r.area * (r.xc - x_bar) * (r.yc - y_bar) for r in rects)

    promedio = 0.5 * (Ix + Iy)
    radio = sqrt((0.5 * (Ix - Iy)) ** 2 + Ixy**2)
    I1 = promedio + radio
    I2 = promedio - radio
    theta = 0.5 * atan2(-2.0 * Ixy, Ix - Iy)

    xmin = min(r.x for r in rects)
    xmax = max(r.x + r.b for r in rects)
    ymin = min(r.y for r in rects)
    ymax = max(r.y + r.h for r in rects)

    Sx_sup = Ix / (ymax - y_bar)
    Sx_inf = Ix / (y_bar - ymin)
    Sy_der = Iy / (xmax - x_bar)
    Sy_izq = Iy / (x_bar - xmin)

    yp = _biseccion_area(rects, "y", Ag / 2.0)
    xp = _biseccion_area(rects, "x", Ag / 2.0)
    Zx = sum(r.b * _integral_abs_interval(r.y, r.y + r.h, yp) for r in rects)
    Zy = sum(r.h * _integral_abs_interval(r.x, r.x + r.b, xp) for r in rects)

    J = J_override if J_override is not None else sum(_j_rectangulo(r.b, r.h) for r in rects)

    return PropiedadesSeccion(
        perfil=perfil,
        Ag=Ag,
        x_bar=x_bar,
        y_bar=y_bar,
        Ix=Ix,
        Iy=Iy,
        Ixy=Ixy,
        rx=sqrt(Ix / Ag),
        ry=sqrt(Iy / Ag),
        I1=I1,
        I2=I2,
        r1=sqrt(I1 / Ag),
        r2=sqrt(max(I2, 0.0) / Ag),
        theta_p_deg=theta * 180.0 / pi,
        Sx_sup=Sx_sup,
        Sx_inf=Sx_inf,
        Sy_der=Sy_der,
        Sy_izq=Sy_izq,
        Zx=Zx,
        Zy=Zy,
        J=J,
        Cw=Cw,
        ancho_total=xmax - xmin,
        altura_total=ymax - ymin,
        observacion=observacion,
    )


def propiedades_perfil_i(*, bf: float, tf: float, h: float, tw: float,
                          cubreplacas: dict | None = None) -> PropiedadesSeccion:
    for n, v in {"bf": bf, "tf": tf, "h": h, "tw": tw}.items():
        _positivo(n, v)
    if tw > bf:
        raise ValueError("tw no puede ser mayor que bf.")
    d = h + 2.0 * tf
    rects = [
        Rectangulo(-bf / 2, 0.0, bf, tf, "patín inferior"),
        Rectangulo(-tw / 2, tf, tw, h, "alma"),
        Rectangulo(-bf / 2, tf + h, bf, tf, "patín superior"),
    ]
    cp = cubreplacas or {}
    if cp.get("inferior"):
        q = cp["inferior"]
        Bcp = float(q.get("B", q.get("b", 0.0)))
        tcp = float(q["t"])
        rects.append(Rectangulo(-Bcp / 2, -tcp, Bcp, tcp, "cubreplaca inferior"))
    if cp.get("superior"):
        q = cp["superior"]
        Bcp = float(q.get("B", q.get("b", 0.0)))
        tcp = float(q["t"])
        rects.append(Rectangulo(-Bcp / 2, d, Bcp, tcp, "cubreplaca superior"))

    # Aproximación habitual para I doblemente simétrica sin cubreplacas asimétricas.
    Cw = None
    if not cp or (
        cp.get("superior") and cp.get("inferior")
        and abs(float(cp["superior"].get("B", cp["superior"].get("b"))) - float(cp["inferior"].get("B", cp["inferior"].get("b")))) < 1e-9
        and abs(float(cp["superior"]["t"]) - float(cp["inferior"]["t"])) < 1e-9
    ):
        # Cw ≈ Iy_flange_total * ho² / 4. Iy_flange_total includes both flanges/cubreplacas.
        ho = h + tf
        Iy_fl = 2.0 * tf * bf**3 / 12.0
        if cp.get("superior"):
            Bcp = float(cp["superior"].get("B", cp["superior"].get("b")))
            tcp = float(cp["superior"]["t"])
            Iy_fl += 2.0 * tcp * Bcp**3 / 12.0
            ho += tcp
        Cw = Iy_fl * ho**2 / 4.0

    return propiedades_rectangulos(
        "Perfil I", rects, Cw=Cw,
        observacion="Se ignoraron radios de filete. Cw es aproximado y solo se entrega para configuración doblemente simétrica.",
    )



def propiedades_perfil_i_asimetrico(
    *, bf_superior: float, tf_superior: float,
    bf_inferior: float, tf_inferior: float,
    h: float, tw: float, cubreplacas: dict | None = None,
) -> PropiedadesSeccion:
    """Propiedades de una I monosimétrica con patines centrados y diferentes."""
    for n, v in {
        "bf_superior": bf_superior, "tf_superior": tf_superior,
        "bf_inferior": bf_inferior, "tf_inferior": tf_inferior,
        "h": h, "tw": tw,
    }.items():
        _positivo(n, v)
    if tw > min(bf_superior, bf_inferior):
        raise ValueError("tw no puede ser mayor que el ancho de los patines.")

    d = tf_inferior + h + tf_superior
    rects = [
        Rectangulo(-bf_inferior/2, 0.0, bf_inferior, tf_inferior, "patín inferior"),
        Rectangulo(-tw/2, tf_inferior, tw, h, "alma"),
        Rectangulo(-bf_superior/2, tf_inferior+h, bf_superior, tf_superior, "patín superior"),
    ]
    cp = cubreplacas or {}
    if cp.get("inferior"):
        q=cp["inferior"]; B=float(q.get("B", q.get("b"))); t=float(q["t"])
        rects.append(Rectangulo(-B/2, -t, B, t, "cubreplaca inferior"))
    if cp.get("superior"):
        q=cp["superior"]; B=float(q.get("B", q.get("b"))); t=float(q["t"])
        rects.append(Rectangulo(-B/2, d, B, t, "cubreplaca superior"))

    return propiedades_rectangulos(
        "Perfil I asimétrico", rects, Cw=None,
        observacion=("Perfil I monosimétrico respecto al eje vertical. Se ignoraron radios de filete; "
                     "Cw y el centro de cortante deben ingresarse cuando E4 los requiera."),
    )


def propiedades_canal(*, b: float, tf: float, h: float, tw: float) -> PropiedadesSeccion:
    for n, v in {"b": b, "tf": tf, "h": h, "tw": tw}.items():
        _positivo(n, v)
    B = b + tw
    rects = [
        Rectangulo(0.0, 0.0, B, tf, "patín inferior"),
        Rectangulo(0.0, tf, tw, h, "alma"),
        Rectangulo(0.0, tf + h, B, tf, "patín superior"),
    ]
    return propiedades_rectangulos("Canal", rects, observacion="Se ignoraron radios de filete; Cw y centro de cortante no se calculan todavía.")


def propiedades_tee(*, b: float, tf: float, d: float, tw: float) -> PropiedadesSeccion:
    for n, v in {"b": b, "tf": tf, "d": d, "tw": tw}.items():
        _positivo(n, v)
    bf = 2.0 * b + tw
    rects = [
        Rectangulo(-tw / 2, 0.0, tw, d, "vástago"),
        Rectangulo(-bf / 2, d, bf, tf, "patín"),
    ]
    return propiedades_rectangulos("Tee", rects, observacion="Se ignoraron radios de filete; Cw y centro de cortante no se calculan todavía.")


def _rects_angulo(b1: float, b2: float, t: float, x0: float = 0.0, espejo: bool = False) -> list[Rectangulo]:
    if not espejo:
        return [
            Rectangulo(x0, 0.0, t, b1, "pata vertical"),
            Rectangulo(x0 + t, 0.0, b2 - t, t, "pata horizontal"),
        ]
    return [
        Rectangulo(x0 - t, 0.0, t, b1, "pata vertical"),
        Rectangulo(x0 - b2, 0.0, b2 - t, t, "pata horizontal"),
    ]


def propiedades_angulo_simple(*, b1: float, b2: float, t: float) -> PropiedadesSeccion:
    for n, v in {"b1": b1, "b2": b2, "t": t}.items():
        _positivo(n, v)
    if t >= min(b1, b2):
        raise ValueError("t debe ser menor que ambas patas.")
    return propiedades_rectangulos(
        "Ángulo simple", _rects_angulo(b1, b2, t),
        observacion="Propiedades respecto a ejes geométricos paralelos a las patas; usar I1, I2 y r2 para ejes principales.",
    )


def propiedades_angulo_doble(*, b1: float, b2: float, t: float, separacion: float) -> PropiedadesSeccion:
    for n, v in {"b1": b1, "b2": b2, "t": t}.items():
        _positivo(n, v)
    if separacion < 0:
        raise ValueError("La separación no puede ser negativa.")
    if t >= min(b1, b2):
        raise ValueError("t debe ser menor que ambas patas.")
    x_izq = -separacion / 2.0 - t
    x_der = separacion / 2.0 + t
    rects = _rects_angulo(b1, b2, t, x_izq, espejo=False)
    rects += _rects_angulo(b1, b2, t, x_der, espejo=True)
    return propiedades_rectangulos(
        "Ángulo doble con separadores", rects,
        observacion="Se modelan dos ángulos espejo con separación libre entre caras interiores; no se incluye el área de separadores.",
    )


def propiedades_tubo_rectangular(*, B: float, H: float, t: float, perfil: str, fabricacion: str) -> PropiedadesSeccion:
    for n, v in {"B": B, "H": H, "t": t}.items():
        _positivo(n, v)
    if 2.0 * t >= min(B, H):
        raise ValueError("El espesor debe ser menor que la mitad de B y H.")
    Bi, Hi = B - 2.0 * t, H - 2.0 * t
    Ag = B * H - Bi * Hi
    Ix = (B * H**3 - Bi * Hi**3) / 12.0
    Iy = (H * B**3 - Hi * Bi**3) / 12.0
    rx, ry = sqrt(Ix / Ag), sqrt(Iy / Ag)
    Sx = Ix / (H / 2.0)
    Sy = Iy / (B / 2.0)
    # Para secciones doblemente simétricas, PNA = centroide.
    Zx = (B * H**2 - Bi * Hi**2) / 4.0
    Zy = (H * B**2 - Hi * Bi**2) / 4.0
    Am = (B - t) * (H - t)
    sum_s_t = 2.0 * (B - t) / t + 2.0 * (H - t) / t
    J = 4.0 * Am**2 / sum_s_t
    obs = "Esquinas rectas. Para tubo Rolled, Ag e inercias son aproximados porque no se incluyen radios de esquina reales."
    return PropiedadesSeccion(
        perfil=perfil, Ag=Ag, x_bar=B/2.0, y_bar=H/2.0,
        Ix=Ix, Iy=Iy, Ixy=0.0, rx=rx, ry=ry,
        I1=max(Ix, Iy), I2=min(Ix, Iy), r1=max(rx, ry), r2=min(rx, ry),
        theta_p_deg=0.0 if Ix >= Iy else 90.0,
        Sx_sup=Sx, Sx_inf=Sx, Sy_der=Sy, Sy_izq=Sy,
        Zx=Zx, Zy=Zy, J=J, Cw=0.0,
        ancho_total=B, altura_total=H, observacion=obs,
    )


def propiedades_tubo_circular(*, D: float, t: float) -> PropiedadesSeccion:
    for n, v in {"D": D, "t": t}.items():
        _positivo(n, v)
    if 2.0 * t >= D:
        raise ValueError("El espesor debe ser menor que D/2.")
    Di = D - 2.0 * t
    Ag = pi / 4.0 * (D**2 - Di**2)
    I = pi / 64.0 * (D**4 - Di**4)
    r = sqrt(I / Ag)
    S = I / (D / 2.0)
    Z = (D**3 - Di**3) / 6.0
    J = 2.0 * I
    return PropiedadesSeccion(
        perfil="Tubo circular", Ag=Ag, x_bar=D/2.0, y_bar=D/2.0,
        Ix=I, Iy=I, Ixy=0.0, rx=r, ry=r, I1=I, I2=I, r1=r, r2=r,
        theta_p_deg=0.0, Sx_sup=S, Sx_inf=S, Sy_der=S, Sy_izq=S,
        Zx=Z, Zy=Z, J=J, Cw=0.0, ancho_total=D, altura_total=D,
        observacion="Propiedades exactas de un anillo circular concéntrico.",
    )


def calcular_propiedades(perfil: str, geo: dict, *, fabricacion: str | None = None,
                         cubreplacas: dict | None = None) -> PropiedadesSeccion:
    if perfil == "Perfil I":
        return propiedades_perfil_i(bf=geo["bf"], tf=geo["tf"], h=geo["h"], tw=geo["tw"], cubreplacas=cubreplacas)
    if perfil == "Perfil I asimétrico":
        return propiedades_perfil_i_asimetrico(
            bf_superior=geo["bf_superior"], tf_superior=geo["tf_superior"],
            bf_inferior=geo["bf_inferior"], tf_inferior=geo["tf_inferior"],
            h=geo["h"], tw=geo["tw"], cubreplacas=cubreplacas,
        )
    if perfil == "Canal":
        return propiedades_canal(b=geo["b"], tf=geo["tf"], h=geo["h"], tw=geo["tw"])
    if perfil == "Tee":
        return propiedades_tee(b=geo["b"], tf=geo["tf"], d=geo["d"], tw=geo["tw"])
    if perfil == "Ángulo simple":
        return propiedades_angulo_simple(b1=geo["b1"], b2=geo["b2"], t=geo["t"])
    if perfil == "Ángulo doble con separadores":
        return propiedades_angulo_doble(b1=geo["b1"], b2=geo["b2"], t=geo["t"], separacion=geo.get("separacion", 0.0))
    if perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        return propiedades_tubo_rectangular(B=geo["B"], H=geo["H"], t=geo["t"], perfil=perfil, fabricacion=fabricacion or "Rolled")
    if perfil == "Tubo circular":
        return propiedades_tubo_circular(D=geo["D"], t=geo["t"])
    raise ValueError(f"Perfil no reconocido: {perfil}")
