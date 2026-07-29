"""Clasificación local para miembros sometidos a flexión según la Tabla B4.1b.

La clasificación obtenida es COMPACTO, NO COMPACTO o ESBELTO. Este módulo no
calcula resistencia nominal a flexión ni aplica el Capítulo F.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt


@dataclass(frozen=True)
class ResultadoFlexionB4:
    perfil: str
    elemento: str
    caso_tabla: str
    relacion: str
    formula_lambda_p: str
    formula_lambda_r: str
    lambda_real: float
    lambda_p: float
    lambda_r: float
    clasificacion: str
    observacion: str = ""

    def como_dict(self) -> dict[str, object]:
        return asdict(self)


def _positivo(nombre: str, valor: float) -> None:
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(valor, maximo))


def calcular_kc(h: float, tw: float) -> float:
    _positivo("h", h)
    _positivo("tw", tw)
    return _limitar(4.0 / sqrt(h / tw), 0.35, 0.76)


def _dimensiones_i(geo: dict) -> tuple[float, float, float, float, float, float]:
    if "bf_superior" in geo:
        return (geo["bf_superior"], geo["tf_superior"],
                geo["bf_inferior"], geo["tf_inferior"], geo["h"], geo["tw"])
    return geo["bf"], geo["tf"], geo["bf"], geo["tf"], geo["h"], geo["tw"]


def clasificar_flexion(lambda_real: float, lambda_p: float, lambda_r: float) -> str:
    for nombre, valor in {
        "lambda real": lambda_real,
        "lambda_p": lambda_p,
        "lambda_r": lambda_r,
    }.items():
        _positivo(nombre, valor)
    if lambda_p > lambda_r:
        raise ValueError("lambda_p no puede ser mayor que lambda_r.")
    if lambda_real <= lambda_p:
        return "COMPACTO"
    if lambda_real <= lambda_r:
        return "NO COMPACTO"
    return "ESBELTO"


def _resultado(
    *, perfil: str, elemento: str, caso: int, relacion: str,
    formula_p: str, formula_r: str, lam: float, lp: float, lr: float,
    observacion: str = "",
) -> ResultadoFlexionB4:
    return ResultadoFlexionB4(
        perfil=perfil,
        elemento=elemento,
        caso_tabla=f"Caso {caso}",
        relacion=relacion,
        formula_lambda_p=formula_p,
        formula_lambda_r=formula_r,
        lambda_real=lam,
        lambda_p=lp,
        lambda_r=lr,
        clasificacion=clasificar_flexion(lam, lp, lr),
        observacion=observacion,
    )


def _pna_horizontal_perfil_i(geo: dict, cubreplacas: dict | None) -> float:
    """Eje neutro plástico horizontal medido desde la cara inferior extrema."""
    bf_sup, tf_sup, bf_inf, tf_inf, h, tw = _dimensiones_i(geo)
    cp = cubreplacas or {}
    t_inf = float(cp.get("inferior", {}).get("t", 0.0))
    t_sup = float(cp.get("superior", {}).get("t", 0.0))
    b_inf = float(cp.get("inferior", {}).get("B", cp.get("inferior", {}).get("b", 0.0)))
    b_sup = float(cp.get("superior", {}).get("B", cp.get("superior", {}).get("b", 0.0)))

    # Coordenadas desde la fibra extrema inferior, incluyendo cubreplaca inferior.
    rects: list[tuple[float, float, float]] = []  # y0, alto, ancho
    if t_inf > 0:
        rects.append((0.0, t_inf, b_inf))
    y0 = t_inf
    rects.extend([
        (y0, tf_inf, bf_inf),
        (y0 + tf_inf, h, tw),
        (y0 + tf_inf + h, tf_sup, bf_sup),
    ])
    if t_sup > 0:
        rects.append((y0 + tf_inf + h + tf_sup, t_sup, b_sup))

    area_total = sum(alto * ancho for _, alto, ancho in rects)
    objetivo = area_total / 2.0
    lo = min(y for y, _, _ in rects)
    hi = max(y + alto for y, alto, _ in rects)
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        area = 0.0
        for y, alto, ancho in rects:
            area += ancho * min(max(mid - y, 0.0), alto)
        if area < objetivo:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _limites_caso16(
    *, E: float, Fy: float, geo: dict, propiedades, cubreplacas: dict | None,
    lado_compresion: str,
) -> tuple[float, float, str]:
    """Caso 16 para alma de sección I monosimétrica en flexión mayor."""
    bf_sup, tf_sup, bf_inf, tf_inf, h, tw = _dimensiones_i(geo)
    cp = cubreplacas or {}
    t_inf = float(cp.get("inferior", {}).get("t", 0.0))
    t_sup = float(cp.get("superior", {}).get("t", 0.0))
    altura_total = h + tf_inf + tf_sup + t_inf + t_sup
    y_bar = propiedades.y_bar
    yp = _pna_horizontal_perfil_i(geo, cp)

    if lado_compresion == "Superior":
        cara_interior = t_inf + tf_inf + h
        c_comp = altura_total - y_bar
        Sxc = propiedades.Sx_sup
        Sxt = propiedades.Sx_inf
    else:
        cara_interior = t_inf + tf_inf
        c_comp = y_bar
        Sxc = propiedades.Sx_inf
        Sxt = propiedades.Sx_sup

    hc = 2.0 * abs(cara_interior - y_bar)
    hp = 2.0 * abs(cara_interior - yp)
    _positivo("hc", hc)
    _positivo("hp", hp)
    _positivo("Sxc", Sxc)
    _positivo("Sxt", Sxt)
    _positivo("c de compresión", c_comp)

    Mp = Fy * propiedades.Zx
    My = Fy * Sxc
    relacion_modulos = Sxt / Sxc
    FL = 0.7 * Fy if relacion_modulos >= 0.7 else max(0.5 * Fy, Fy * relacion_modulos)

    denominador = (0.54 * Mp / My - 0.09) ** 2
    _positivo("denominador del caso 16", denominador)
    lp = (hc / hp) * sqrt(E / Fy) / denominador
    lr = 5.70 * sqrt(E / Fy)
    lp = min(lp, lr)
    obs = (
        f"Sección I monosimétrica; hc={hc:.3f}, hp={hp:.3f}, "
        f"Mp/My={Mp/My:.3f}, Sxt/Sxc={relacion_modulos:.3f}, FL={FL:.3f}."
    )
    return lp, lr, obs


def evaluar_flexion_b4(
    *, perfil: str, fabricacion: str | None, eje: str, lado_compresion: str,
    geo: dict, E: float, Fy: float, propiedades,
    cubreplacas: dict | None = None,
) -> list[ResultadoFlexionB4]:
    """Evalúa automáticamente los casos aplicables de la Tabla B4.1b."""
    for nombre, valor in {"E": E, "Fy": Fy}.items():
        _positivo(nombre, valor)
    if eje not in {"x-x", "y-y"}:
        raise ValueError("El eje debe ser 'x-x' o 'y-y'.")
    if lado_compresion not in {"Superior", "Inferior", "Derecha", "Izquierda"}:
        raise ValueError("Lado de compresión no reconocido.")

    raiz = sqrt(E / Fy)
    resultados: list[ResultadoFlexionB4] = []
    cp = cubreplacas or {}

    if perfil in {"Perfil I", "Perfil I asimétrico"}:
        bf_sup, tf_sup, bf_inf, tf_inf, h, tw = _dimensiones_i(geo)
        if eje == "y-y":
            resultados.extend([
                _resultado(
                    perfil=perfil, elemento="Patín superior en flexión alrededor de y-y", caso=13,
                    relacion="bf_sup/(2·tf_sup)", formula_p="0.38·√(E/Fy)", formula_r="1.00·√(E/Fy)",
                    lam=bf_sup/(2.0*tf_sup), lp=0.38*raiz, lr=1.00*raiz,
                    observacion="Ala de perfil I en flexión respecto al eje menor.",
                ),
                _resultado(
                    perfil=perfil, elemento="Patín inferior en flexión alrededor de y-y", caso=13,
                    relacion="bf_inf/(2·tf_inf)", formula_p="0.38·√(E/Fy)", formula_r="1.00·√(E/Fy)",
                    lam=bf_inf/(2.0*tf_inf), lp=0.38*raiz, lr=1.00*raiz,
                    observacion="Ala de perfil I en flexión respecto al eje menor.",
                ),
            ])
            return resultados

        # Flexión mayor x-x: solo el patín del lado comprimido gobierna la clasificación del ala.
        bf_comp, tf_comp = ((bf_sup, tf_sup) if lado_compresion == "Superior" else (bf_inf, tf_inf))
        if fabricacion == "Built-up":
            kc = calcular_kc(h, tw)
            Sxc = propiedades.Sx_sup if lado_compresion == "Superior" else propiedades.Sx_inf
            Sxt = propiedades.Sx_inf if lado_compresion == "Superior" else propiedades.Sx_sup
            razon = Sxt / Sxc
            FL = 0.7 * Fy if razon >= 0.7 else max(0.5 * Fy, Fy * razon)
            resultados.append(_resultado(
                perfil=perfil, elemento=f"Patín {lado_compresion.lower()} comprimido", caso=11,
                relacion="bf_comp/(2·tf_comp)", formula_p="0.38·√(E/Fy)", formula_r="0.95·√(kc·E/FL)",
                lam=bf_comp/(2.0*tf_comp), lp=0.38*raiz, lr=0.95*sqrt(kc*E/FL),
                observacion=f"kc={kc:.3f}; FL={FL:.3f}; Sxt/Sxc={razon:.3f}.",
            ))
        else:
            resultados.append(_resultado(
                perfil=perfil, elemento=f"Patín {lado_compresion.lower()} comprimido", caso=10,
                relacion="bf_comp/(2·tf_comp)", formula_p="0.38·√(E/Fy)", formula_r="1.00·√(E/Fy)",
                lam=bf_comp/(2.0*tf_comp), lp=0.38*raiz, lr=1.00*raiz,
            ))

        # Se considera monosimétrico si las cubreplacas no son iguales y simétricas.
        sup = cp.get("superior")
        inf = cp.get("inferior")
        geometria_simetrica = abs(bf_sup-bf_inf) < 1e-9 and abs(tf_sup-tf_inf) < 1e-9
        doble_simetria = geometria_simetrica and ((
            not sup and not inf
        ) or (
            sup and inf
            and abs(float(sup.get("B", sup.get("b"))) - float(inf.get("B", inf.get("b")))) < 1e-9
            and abs(float(sup["t"]) - float(inf["t"])) < 1e-9
        ))
        if doble_simetria:
            resultados.append(_resultado(
                perfil=perfil, elemento="Alma", caso=15, relacion="h/tw",
                formula_p="3.76·√(E/Fy)", formula_r="5.70·√(E/Fy)",
                lam=h/tw, lp=3.76*raiz, lr=5.70*raiz,
            ))
        else:
            lp, lr, obs = _limites_caso16(
                E=E, Fy=Fy, geo=geo, propiedades=propiedades,
                cubreplacas=cp, lado_compresion=lado_compresion,
            )
            resultados.append(_resultado(
                perfil=perfil, elemento="Alma de sección I monosimétrica", caso=16,
                relacion="hc/tw", formula_p="(hc/hp)·√(E/Fy)/(0.54·Mp/My−0.09)²",
                formula_r="5.70·√(E/Fy)",
                lam=(2.0*abs(((tf_inf + h) if lado_compresion == "Superior" else tf_inf) - propiedades.y_bar))/tw,
                lp=lp, lr=lr, observacion=obs,
            ))

        clave_cp = "superior" if lado_compresion == "Superior" else "inferior"
        if cp.get(clave_cp):
            q = cp[clave_cp]
            resultados.append(_resultado(
                perfil=perfil, elemento=f"Cubreplaca {clave_cp}", caso=18,
                relacion="b/t", formula_p="1.12·√(E/Fy)", formula_r="1.40·√(E/Fy)",
                lam=float(q["b"])/float(q["t"]), lp=1.12*raiz, lr=1.40*raiz,
                observacion="Se evalúa únicamente la cubreplaca ubicada en el lado comprimido.",
            ))
        return resultados

    if perfil == "Canal":
        b, tf, h, tw = geo["b"], geo["tf"], geo["h"], geo["tw"]
        if eje == "x-x":
            resultados.extend([
                _resultado(perfil=perfil, elemento="Patín comprimido", caso=10, relacion="b/tf",
                           formula_p="0.38·√(E/Fy)", formula_r="1.00·√(E/Fy)",
                           lam=b/tf, lp=0.38*raiz, lr=1.00*raiz),
                _resultado(perfil=perfil, elemento="Alma", caso=15, relacion="h/tw",
                           formula_p="3.76·√(E/Fy)", formula_r="5.70·√(E/Fy)",
                           lam=h/tw, lp=3.76*raiz, lr=5.70*raiz),
            ])
        else:
            resultados.append(_resultado(
                perfil=perfil, elemento="Patines en flexión alrededor de y-y", caso=13,
                relacion="b/tf", formula_p="0.38·√(E/Fy)", formula_r="1.00·√(E/Fy)",
                lam=b/tf, lp=0.38*raiz, lr=1.00*raiz,
            ))
        return resultados

    if perfil == "Tee":
        b, tf, d, tw = geo["b"], geo["tf"], geo["d"], geo["tw"]
        resultados.append(_resultado(
            perfil=perfil, elemento="Patín", caso=10, relacion="b/tf",
            formula_p="0.38·√(E/Fy)", formula_r="1.00·√(E/Fy)",
            lam=b/tf, lp=0.38*raiz, lr=1.00*raiz,
        ))
        resultados.append(_resultado(
            perfil=perfil, elemento="Vástago", caso=14, relacion="d/tw",
            formula_p="0.84·√(E/Fy)", formula_r="1.52·√(E/Fy)",
            lam=d/tw, lp=0.84*raiz, lr=1.52*raiz,
            observacion=f"Lado indicado en compresión: {lado_compresion.lower()}.",
        ))
        return resultados

    if perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        b1, b2, t = geo["b1"], geo["b2"], geo["t"]
        resultados.extend([
            _resultado(perfil=perfil, elemento="Pata 1", caso=12, relacion="b1/t",
                       formula_p="0.54·√(E/Fy)", formula_r="0.91·√(E/Fy)",
                       lam=b1/t, lp=0.54*raiz, lr=0.91*raiz),
            _resultado(perfil=perfil, elemento="Pata 2", caso=12, relacion="b2/t",
                       formula_p="0.54·√(E/Fy)", formula_r="0.91·√(E/Fy)",
                       lam=b2/t, lp=0.54*raiz, lr=0.91*raiz),
        ])
        return resultados

    if perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        B, H, t = geo["B"], geo["H"], geo["t"]
        descuento = 3.0*t if fabricacion == "Rolled" else 2.0*t
        b_plano, h_plano = B-descuento, H-descuento
        if min(b_plano, h_plano) <= 0:
            raise ValueError("Las dimensiones planas del tubo deben ser positivas.")
        if eje == "x-x":
            b_pat, h_alma = b_plano, h_plano
            nom_pat, nom_alma = "Paredes horizontales (patines)", "Paredes verticales (almas)"
        else:
            b_pat, h_alma = h_plano, b_plano
            nom_pat, nom_alma = "Paredes verticales (patines)", "Paredes horizontales (almas)"
        caso_pat = 17 if fabricacion == "Rolled" else 21
        lr_pat = (1.40 if fabricacion == "Rolled" else 1.49)*raiz
        resultados.extend([
            _resultado(perfil=perfil, elemento=nom_pat, caso=caso_pat, relacion="b/t",
                       formula_p="1.12·√(E/Fy)",
                       formula_r=("1.40·√(E/Fy)" if fabricacion == "Rolled" else "1.49·√(E/Fy)"),
                       lam=b_pat/t, lp=1.12*raiz, lr=lr_pat),
            _resultado(perfil=perfil, elemento=nom_alma, caso=19, relacion="h/t",
                       formula_p="2.42·√(E/Fy)", formula_r="5.70·√(E/Fy)",
                       lam=h_alma/t, lp=2.42*raiz, lr=5.70*raiz),
        ])
        return resultados

    if perfil == "Tubo circular":
        D, t = geo["D"], geo["t"]
        resultados.append(_resultado(
            perfil=perfil, elemento="Pared circular", caso=20, relacion="D/t",
            formula_p="0.07·E/Fy", formula_r="0.31·E/Fy",
            lam=D/t, lp=0.07*E/Fy, lr=0.31*E/Fy,
        ))
        return resultados

    raise ValueError(f"Perfil no reconocido para Tabla B4.1b: {perfil}")


def clasificacion_global(resultados: list[ResultadoFlexionB4]) -> tuple[str, ResultadoFlexionB4]:
    if not resultados:
        raise ValueError("No existen resultados de flexión.")
    orden = {"COMPACTO": 0, "NO COMPACTO": 1, "ESBELTO": 2}
    gobierna = max(
        resultados,
        key=lambda r: (orden[r.clasificacion], r.lambda_real / r.lambda_r),
    )
    return gobierna.clasificacion, gobierna
