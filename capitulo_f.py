"""Selección y cálculo de resistencia a flexión según AISC 360-22, Capítulo F.

El módulo trabaja con el sistema interno de la aplicación: mm, MPa, N y N·mm.
Incluye las rutas y ecuaciones aplicables a los perfiles estándar que actualmente
admite la interfaz: perfiles I, canales, tees, ángulos simples y dobles, y tubos
rectangulares/cuadrados/circulares.

Las secciones F11 y F12 se identifican en la ruta, pero la interfaz actual no
crea barras macizas ni secciones completamente asimétricas personalizadas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import pi, sqrt
from typing import Iterable, Sequence

PHI_B = 0.90
OMEGA_B = 1.67


@dataclass(frozen=True)
class RutaCapituloF:
    seccion: str
    categoria: str
    estados_limite: tuple[str, ...]
    clasificacion_patin: str
    clasificacion_alma: str
    eje: str
    simetria: str
    aplicable: bool
    explicacion: str
    advertencias: tuple[str, ...] = ()

    def como_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EstadoLimiteMomento:
    estado: str
    Mn: float
    ecuacion: str
    observacion: str = ""
    Fcr: float | None = None
    descripcion_Fcr: str = ""

    def como_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResultadoCapituloF:
    seccion: str
    estados: tuple[EstadoLimiteMomento, ...]
    gobernante: EstadoLimiteMomento
    phi_b: float = PHI_B
    omega_b: float = OMEGA_B
    observaciones: tuple[str, ...] = ()

    @property
    def Mn(self) -> float:
        return self.gobernante.Mn

    @property
    def phi_Mn(self) -> float:
        return self.phi_b * self.Mn

    @property
    def Mn_sobre_omega(self) -> float:
        return self.Mn / self.omega_b

    def como_dict(self) -> dict[str, object]:
        return {
            "seccion": self.seccion,
            "estados": [e.como_dict() for e in self.estados],
            "gobernante": self.gobernante.como_dict(),
            "Mn": self.Mn,
            "phi_Mn": self.phi_Mn,
            "Mn_sobre_omega": self.Mn_sobre_omega,
            "phi_b": self.phi_b,
            "omega_b": self.omega_b,
            "observaciones": self.observaciones,
        }


def _positivo(nombre: str, valor: float, *, permite_cero: bool = False) -> None:
    if (valor < 0 if permite_cero else valor <= 0):
        operador = "no negativo" if permite_cero else "mayor que cero"
        raise ValueError(f"{nombre} debe ser {operador}.")


def _resolver(seccion: str, estados: Sequence[EstadoLimiteMomento], *observaciones: str) -> ResultadoCapituloF:
    if not estados:
        raise ValueError(f"No se generaron estados límite para {seccion}.")
    for estado in estados:
        _positivo(f"Mn de {estado.estado}", estado.Mn)
    gobernante = min(estados, key=lambda e: e.Mn)
    return ResultadoCapituloF(
        seccion=seccion,
        estados=tuple(estados),
        gobernante=gobernante,
        observaciones=tuple(o for o in observaciones if o),
    )


def calcular_cb(Mmax: float, MA: float, MB: float, MC: float) -> float:
    """F1-1: factor Cb para diagrama de momento no uniforme.

    Los cuatro valores se interpretan como valores absolutos. Si todos son cero,
    la ecuación no está definida.
    """
    valores = [abs(float(v)) for v in (Mmax, MA, MB, MC)]
    mmax, ma, mb, mc = valores
    denominador = 2.5 * mmax + 3.0 * ma + 4.0 * mb + 3.0 * mc
    if denominador <= 0:
        raise ValueError("F1-1 requiere al menos un momento distinto de cero.")
    cb = 12.5 * mmax / denominador
    _positivo("Cb", cb)
    return cb


def _peor_clasificacion(valores: Iterable[str]) -> str:
    orden = {"NA": -1, "COMPACTO": 0, "NO COMPACTO": 1, "ESBELTO": 2}
    lista = [v for v in valores if v in orden]
    if not lista:
        return "NA"
    return max(lista, key=lambda v: orden[v])


def _resultados_que_contienen(resultados: Iterable, palabras: Sequence[str]) -> list:
    encontrados = []
    for r in resultados:
        elemento = str(getattr(r, "elemento", "")).lower()
        if any(p.lower() in elemento for p in palabras):
            encontrados.append(r)
    return encontrados


def clasificaciones_patin_alma(perfil: str, resultados_b4: Iterable) -> tuple[str, str]:
    """Extrae la clasificación de patín y alma conservando resultados separados."""
    resultados = list(resultados_b4)
    if perfil in {"Perfil I", "Perfil I asimétrico"}:
        patines = _resultados_que_contienen(resultados, ("patín", "cubreplaca"))
        almas = _resultados_que_contienen(resultados, ("alma",))
    elif perfil == "Canal":
        patines = _resultados_que_contienen(resultados, ("patín",))
        almas = _resultados_que_contienen(resultados, ("alma",))
    elif perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        patines = _resultados_que_contienen(resultados, ("patines",))
        almas = _resultados_que_contienen(resultados, ("almas",))
    elif perfil == "Tee":
        patines = _resultados_que_contienen(resultados, ("patín",))
        almas = _resultados_que_contienen(resultados, ("vástago",))
    else:
        return "NA", "NA"
    return (
        _peor_clasificacion(getattr(r, "clasificacion", "NA") for r in patines),
        _peor_clasificacion(getattr(r, "clasificacion", "NA") for r in almas),
    )


def ruta_capitulo_f(
    *, perfil: str, eje: str, simetria: str, resultados_b4: Iterable,
) -> RutaCapituloF:
    """Implementa la Tabla User Note F1.1 para los perfiles de la aplicación."""
    if eje not in {"x-x", "y-y"}:
        raise ValueError("El eje debe ser 'x-x' o 'y-y'.")
    patin, alma = clasificaciones_patin_alma(perfil, resultados_b4)

    if perfil in {"Perfil I", "Perfil I asimétrico"}:
        if eje == "y-y":
            return RutaCapituloF(
                "F6", "Perfiles I flexionados respecto al eje menor",
                ("Y", "FLB"), patin, "NA", eje, simetria, True,
                "Los perfiles I flexionados alrededor del eje menor se diseñan con F6.",
            )
        if alma == "ESBELTO":
            return RutaCapituloF(
                "F5", "Perfiles I con alma esbelta flexionados respecto al eje mayor",
                ("CFY", "LTB", "FLB", "TFY"), patin, alma, eje, simetria, True,
                "El alma es esbelta; corresponde F5, sin importar que el patín sea C, NC o S.",
            )
        if simetria == "Doble simetría" and alma == "COMPACTO" and patin == "COMPACTO":
            return RutaCapituloF(
                "F2", "Perfil I doblemente simétrico compacto flexionado respecto al eje mayor",
                ("Y", "LTB"), patin, alma, eje, simetria, True,
                "Patín y alma compactos en una I doblemente simétrica: corresponde F2.",
            )
        if simetria == "Doble simetría" and alma == "COMPACTO" and patin in {"NO COMPACTO", "ESBELTO"}:
            return RutaCapituloF(
                "F3", "Perfil I doblemente simétrico con alma compacta y patín NC o esbelto",
                ("LTB", "FLB"), patin, alma, eje, simetria, True,
                "El alma es compacta, pero el patín no es compacto; corresponde F3.",
            )
        if alma in {"COMPACTO", "NO COMPACTO"}:
            return RutaCapituloF(
                "F4", "Otros perfiles I con alma compacta o no compacta",
                ("CFY", "LTB", "FLB", "TFY"), patin, alma, eje, simetria, True,
                "La sección es I monosimétrica o posee alma no compacta; corresponde F4.",
            )

    if perfil == "Canal":
        if eje == "y-y":
            return RutaCapituloF(
                "F6", "Canales flexionados respecto al eje menor",
                ("Y", "FLB"), patin, "NA", eje, simetria, True,
                "Los canales flexionados alrededor del eje menor se diseñan con F6.",
            )
        if patin == "COMPACTO" and alma == "COMPACTO":
            return RutaCapituloF(
                "F2", "Canal compacto flexionado respecto al eje mayor",
                ("Y", "LTB"), patin, alma, eje, simetria, True,
                "F2 exige patín y alma compactos para canales en flexión mayor.",
            )
        return RutaCapituloF(
            "SIN RUTA DIRECTA", "Canal no compacto/esbelto flexionado respecto al eje mayor",
            (), patin, alma, eje, simetria, False,
            "La Tabla F1.1 solo dirige a F2 los canales con patín y alma compactos en flexión mayor.",
            ("La resistencia debe determinarse mediante una disposición aplicable o análisis racional; no se asignó F4/F5 automáticamente.",),
        )

    if perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        return RutaCapituloF(
            "F7", "Tubo cuadrado/rectangular o sección cajón",
            ("Y", "FLB", "WLB", "LTB"), patin, alma, eje, simetria, True,
            "F7 aplica alrededor de cualquiera de los ejes de flexión.",
        )

    if perfil == "Tubo circular":
        return RutaCapituloF(
            "F8", "Tubo circular",
            ("Y", "LB"), "NA", "NA", eje, simetria, True,
            "F8 aplica a tubos circulares dentro del límite de D/t indicado.",
        )

    if perfil in {"Tee", "Ángulo doble con separadores"}:
        if eje == "x-x":
            return RutaCapituloF(
                "F9", "Tee o ángulo doble cargado en el plano de simetría",
                ("Y", "LTB", "FLB", "WLB"), patin, alma, eje, simetria, True,
                "La orientación modelada se encuentra cargada en su plano de simetría.",
            )
        return RutaCapituloF(
            "FUERA DE F9", "Tee o ángulo doble fuera del plano de simetría",
            (), patin, alma, eje, simetria, False,
            "F9 aplica únicamente cuando la carga produce flexión en el plano de simetría.",
            ("La flexión fuera del plano de simetría requiere una evaluación específica de flexión-torsión.",),
        )

    if perfil == "Ángulo simple":
        return RutaCapituloF(
            "F10", "Ángulo simple",
            ("Y", "LTB", "LLB"), "NA", "NA", eje, simetria, True,
            "F10 aplica a ángulos simples con o sin restricción lateral continua.",
        )

    if perfil in {"Barra rectangular", "Barra circular maciza"}:
        return RutaCapituloF(
            "F11", "Barra rectangular o circular maciza",
            ("Y", "LTB"), "NA", "NA", eje, simetria, True,
            "F11 aplica a barras macizas; estos perfiles todavía no se generan en la interfaz.",
        )

    return RutaCapituloF(
        "F12", "Sección asimétrica no cubierta por otra sección",
        ("Y", "LTB", "LB"), "NA", "NA", eje, simetria, False,
        "F12 requiere esfuerzos críticos de pandeo lateral-torsional y local determinados por análisis.",
        ("La aplicación no crea secciones personalizadas completamente asimétricas.",),
    )


def _buscar_resultado(resultados: Iterable, palabras: Sequence[str], *, requerido: bool = True):
    candidatos = _resultados_que_contienen(resultados, palabras)
    if not candidatos:
        if requerido:
            raise ValueError(f"No se encontró en B4.1b el elemento: {', '.join(palabras)}.")
        return None
    orden = {"COMPACTO": 0, "NO COMPACTO": 1, "ESBELTO": 2}
    return max(candidatos, key=lambda r: (orden.get(r.clasificacion, -1), r.lambda_real / r.lambda_r))


def _datos_eje(prop, eje: str, lado_compresion: str) -> tuple[float, float, float, float, float]:
    """Devuelve I, S_comp, S_tens, Z y radio lateral al eje de flexión."""
    if eje == "x-x":
        Scomp = prop.Sx_sup if lado_compresion == "Superior" else prop.Sx_inf
        Stens = prop.Sx_inf if lado_compresion == "Superior" else prop.Sx_sup
        return prop.Ix, Scomp, Stens, prop.Zx, prop.ry
    Scomp = prop.Sy_der if lado_compresion == "Derecha" else prop.Sy_izq
    Stens = prop.Sy_izq if lado_compresion == "Derecha" else prop.Sy_der
    return prop.Iy, Scomp, Stens, prop.Zy, prop.rx


def _limite_mp(Fy: float, Z: float, S: float, factor: float = 1.6) -> float:
    return min(Fy * Z, factor * Fy * S)


def _ho_perfil_i(geo: dict, cubreplacas: dict | None = None) -> float:
    """Distancia entre centroides de los conjuntos de patín superior e inferior."""
    cp = cubreplacas or {}
    if "bf_superior" in geo:
        bfs, tfs = geo["bf_superior"], geo["tf_superior"]
        bfi, tfi = geo["bf_inferior"], geo["tf_inferior"]
    else:
        bfs = bfi = geo["bf"]
        tfs = tfi = geo["tf"]
    h = geo["h"]
    ts_cp = float(cp.get("superior", {}).get("t", 0.0))
    bs_cp = float(cp.get("superior", {}).get("B", cp.get("superior", {}).get("b", 0.0)))
    ti_cp = float(cp.get("inferior", {}).get("t", 0.0))
    bi_cp = float(cp.get("inferior", {}).get("B", cp.get("inferior", {}).get("b", 0.0)))

    y_base_inf = ti_cp
    Ainf = bfi * tfi + bi_cp * ti_cp
    yinf = (
        bfi * tfi * (y_base_inf + tfi / 2.0)
        + bi_cp * ti_cp * (ti_cp / 2.0)
    ) / Ainf

    y_base_sup = ti_cp + tfi + h
    Asup = bfs * tfs + bs_cp * ts_cp
    ysup = (
        bfs * tfs * (y_base_sup + tfs / 2.0)
        + bs_cp * ts_cp * (y_base_sup + tfs + ts_cp / 2.0)
    ) / Asup
    return ysup - yinf


def _datos_patines_i(geo: dict, cubreplacas: dict | None, lado_compresion: str) -> dict[str, float]:
    cp = cubreplacas or {}
    if "bf_superior" in geo:
        bfs, tfs = geo["bf_superior"], geo["tf_superior"]
        bfi, tfi = geo["bf_inferior"], geo["tf_inferior"]
    else:
        bfs = bfi = geo["bf"]
        tfs = tfi = geo["tf"]
    if lado_compresion == "Superior":
        bfc, tfc, clave_c = bfs, tfs, "superior"
        bft, tft, clave_t = bfi, tfi, "inferior"
    else:
        bfc, tfc, clave_c = bfi, tfi, "inferior"
        bft, tft, clave_t = bfs, tfs, "superior"
    qc = cp.get(clave_c, {})
    qt = cp.get(clave_t, {})
    Bcc = float(qc.get("B", qc.get("b", 0.0)))
    tcc = float(qc.get("t", 0.0))
    Bct = float(qt.get("B", qt.get("b", 0.0)))
    tct = float(qt.get("t", 0.0))
    Afc = bfc * tfc + Bcc * tcc
    Aft = bft * tft + Bct * tct
    Iyc = tfc * bfc**3 / 12.0 + tcc * Bcc**3 / 12.0
    Iyt = tft * bft**3 / 12.0 + tct * Bct**3 / 12.0
    return {
        "bfc": bfc, "tfc": tfc, "bft": bft, "tft": tft,
        "Bcp_c": Bcc, "tcp_c": tcc, "Bcp_t": Bct, "tcp_t": tct,
        "Afc": Afc, "Aft": Aft, "Iyc": Iyc, "Iyt": Iyt,
    }


def _hc_perfil_i(prop, geo: dict, cubreplacas: dict | None, lado_compresion: str) -> float:
    cp = cubreplacas or {}
    if "tf_inferior" in geo:
        tfi = geo["tf_inferior"]
    else:
        tfi = geo["tf"]
    t_cp_inf = float(cp.get("inferior", {}).get("t", 0.0))
    if lado_compresion == "Superior":
        cara_interior = t_cp_inf + tfi + geo["h"]
    else:
        cara_interior = t_cp_inf + tfi
    return 2.0 * abs(cara_interior - prop.y_bar)


def _rt_perfil_i(prop, geo: dict, cubreplacas: dict | None, lado_compresion: str) -> tuple[float, float, float]:
    """F4-11 o definición equivalente para patín compuesto/cubreplaca."""
    datos = _datos_patines_i(geo, cubreplacas, lado_compresion)
    hc = _hc_perfil_i(prop, geo, cubreplacas, lado_compresion)
    tw = geo["tw"]
    if datos["tcp_c"] <= 0:
        aw = hc * tw / max(datos["bfc"] * datos["tfc"], 1e-12)
        rt = datos["bfc"] / sqrt(12.0 * (1.0 + aw / 6.0))
    else:
        # Patín y cubreplaca más un tercio del área de alma en compresión.
        Aweb = hc * tw / 3.0
        Iyweb = (hc / 3.0) * tw**3 / 12.0
        A = datos["Afc"] + Aweb
        Iy = datos["Iyc"] + Iyweb
        rt = sqrt(Iy / A)
        aw = hc * tw / max(datos["Afc"], 1e-12)
    return rt, aw, hc


def calcular_f2(
    *, perfil: str, E: float, Fy: float, prop, geo: dict, Lb: float, Cb: float,
    Cw: float | None = None, cubreplacas: dict | None = None,
) -> ResultadoCapituloF:
    """F2: I doblemente simétrica compacta o canal compacto, eje mayor."""
    for n, v in {"E": E, "Fy": Fy, "Lb": Lb, "Cb": Cb}.items():
        _positivo(n, v)
    Sx = min(prop.Sx_sup, prop.Sx_inf)
    Mp = Fy * prop.Zx
    estados = [EstadoLimiteMomento("Y — Fluencia", Mp, "F2-1", "Mn = Mp = Fy·Zx")]
    cw = prop.Cw if Cw is None else Cw
    if cw is None or cw <= 0:
        raise ValueError("F2 requiere Cw > 0 para calcular pandeo lateral-torsional.")
    if perfil == "Canal":
        ho = geo["h"] + geo["tf"]
        c = ho / 2.0 * sqrt(prop.Iy / cw)
    else:
        ho = _ho_perfil_i(geo, cubreplacas)
        c = 1.0
    rts2 = sqrt(prop.Iy * cw) / Sx
    _positivo("rts²", rts2)
    rts = sqrt(rts2)
    Lp = 1.76 * prop.ry * sqrt(E / Fy)
    termino = prop.J * c / (Sx * ho)
    Lr = 1.95 * rts * E / (0.7 * Fy) * sqrt(
        termino + sqrt(termino**2 + 6.76 * (0.7 * Fy / E) ** 2)
    )
    Fcr_ltb = None
    descripcion_fcr = ""
    if Lb <= Lp:
        Mn_ltb, eq, obs = Mp, "F2-2(a)", f"Lb={Lb:.3f} ≤ Lp={Lp:.3f}; LTB no aplica."
    elif Lb <= Lr:
        Mn_ltb = Cb * (Mp - (Mp - 0.7 * Fy * Sx) * (Lb - Lp) / (Lr - Lp))
        Mn_ltb = min(Mn_ltb, Mp)
        Fcr_ltb = Mn_ltb / Sx
        descripcion_fcr = "Fcr equivalente = Mn/Sx; F2-2 calcula Mn directamente."
        eq, obs = (
            "F2-2",
            f"Lp={Lp:.3f} < Lb={Lb:.3f} ≤ Lr={Lr:.3f}; "
            f"Fcr equivalente=Mn/Sx={Fcr_ltb:.3f} MPa.",
        )
    else:
        Fcr_ltb = Cb * pi**2 * E / (Lb / rts) ** 2 * sqrt(
            1.0 + 0.078 * termino * (Lb / rts) ** 2
        )
        Mn_ltb = min(Fcr_ltb * Sx, Mp)
        descripcion_fcr = "Fcr calculado con F2-4."
        eq, obs = "F2-3 / F2-4", f"Lb={Lb:.3f} > Lr={Lr:.3f}; Fcr={Fcr_ltb:.3f} MPa."
    estados.append(EstadoLimiteMomento(
        "LTB — Pandeo lateral-torsional", Mn_ltb, eq, obs,
        Fcr=Fcr_ltb, descripcion_Fcr=descripcion_fcr,
    ))
    return _resolver("F2", estados, f"Lp={Lp:.3f}; Lr={Lr:.3f}; rts={rts:.3f}; c={c:.3f}.")


def calcular_f3(
    *, E: float, Fy: float, prop, geo: dict, Lb: float, Cb: float,
    resultados_b4: Iterable, Cw: float | None = None,
    cubreplacas: dict | None = None,
) -> ResultadoCapituloF:
    """F3: I doblemente simétrica, alma compacta y patín NC o esbelto."""
    base = calcular_f2(
        perfil="Perfil I", E=E, Fy=Fy, prop=prop, geo=geo, Lb=Lb, Cb=Cb, Cw=Cw,
        cubreplacas=cubreplacas,
    )
    patin = _buscar_resultado(resultados_b4, ("patín", "cubreplaca"))
    Sx = min(prop.Sx_sup, prop.Sx_inf)
    Mp = Fy * prop.Zx
    lam, lp, lr = patin.lambda_real, patin.lambda_p, patin.lambda_r
    if patin.clasificacion == "NO COMPACTO":
        Mn_flb = Mp - (Mp - 0.7 * Fy * Sx) * (lam - lp) / (lr - lp)
        eq = "F3-1"
    elif patin.clasificacion == "ESBELTO":
        kc = max(0.35, min(0.76, 4.0 / sqrt(geo["h"] / geo["tw"])))
        Mn_flb = 0.9 * E * kc * Sx / lam**2
        eq = "F3-2"
    else:
        Mn_flb, eq = Mp, "F3 — patín compacto"
    estados = [
        next(e for e in base.estados if e.estado.startswith("LTB")),
        EstadoLimiteMomento("FLB — Pandeo local del patín comprimido", min(Mn_flb, Mp), eq,
                            f"λ={lam:.3f}; λp={lp:.3f}; λr={lr:.3f}."),
    ]
    return _resolver("F3", estados, *base.observaciones)


def _rpc_rpt(
    *, Mp: float, My: float, web, relacion_iyc: float,
) -> float:
    if relacion_iyc <= 0.23:
        return 1.0
    limite = Mp / My
    if web.lambda_real <= web.lambda_p:
        return limite
    valor = limite - (limite - 1.0) * (
        (web.lambda_real - web.lambda_p) / (web.lambda_r - web.lambda_p)
    )
    return min(valor, limite)


def calcular_f4(
    *, E: float, Fy: float, prop, geo: dict, lado_compresion: str,
    Lb: float, Cb: float, resultados_b4: Iterable,
    cubreplacas: dict | None = None,
) -> ResultadoCapituloF:
    """F4: otras I con alma compacta/no compacta, eje mayor."""
    for n, v in {"E": E, "Fy": Fy, "Lb": Lb, "Cb": Cb}.items():
        _positivo(n, v)
    _, Sxc, Sxt, Zx, _ = _datos_eje(prop, "x-x", lado_compresion)
    Sxmin = min(prop.Sx_sup, prop.Sx_inf)
    Mp = min(Fy * Zx, 1.6 * Fy * Sxmin)
    Myc, Myt = Fy * Sxc, Fy * Sxt
    web = _buscar_resultado(resultados_b4, ("alma",))
    flange = _buscar_resultado(resultados_b4, ("patín", "cubreplaca"))
    datos = _datos_patines_i(geo, cubreplacas, lado_compresion)
    relacion_iyc = datos["Iyc"] / prop.Iy
    Rpc = _rpc_rpt(Mp=Mp, My=Myc, web=web, relacion_iyc=relacion_iyc)
    Mn_cfy = Rpc * Myc
    estados = [EstadoLimiteMomento("CFY — Fluencia del patín comprimido", Mn_cfy, "F4-1",
                                    f"Rpc={Rpc:.4f}; Myc={Myc:.3f}.")]

    rt, aw, hc = _rt_perfil_i(prop, geo, cubreplacas, lado_compresion)
    ho = _ho_perfil_i(geo, cubreplacas)
    razon_mod = Sxt / Sxc
    FL = 0.7 * Fy if razon_mod >= 0.7 else max(Fy * razon_mod, 0.5 * Fy)
    Lp = 1.1 * rt * sqrt(E / Fy)
    Jef = 0.0 if relacion_iyc <= 0.23 else prop.J
    termino = Jef / (Sxc * ho)
    Lr = 1.95 * rt * E / FL * sqrt(
        termino + sqrt(termino**2 + 6.76 * (FL / E) ** 2)
    )
    Fcr_ltb = None
    descripcion_fcr = ""
    if Lb <= Lp:
        Mn_ltb, eq_ltb = Mn_cfy, "F4-2(a)"
        regimen_ltb = f"Lb={Lb:.3f} ≤ Lp={Lp:.3f}; LTB no reduce la resistencia."
    elif Lb <= Lr:
        Mn_ltb = Cb * (Mn_cfy - (Mn_cfy - FL * Sxc) * (Lb - Lp) / (Lr - Lp))
        Mn_ltb, eq_ltb = min(Mn_ltb, Mn_cfy), "F4-2"
        Fcr_ltb = Mn_ltb / Sxc
        descripcion_fcr = "Fcr equivalente = Mn/Sxc; F4-2 calcula Mn directamente."
        regimen_ltb = f"Lp={Lp:.3f} < Lb={Lb:.3f} ≤ Lr={Lr:.3f}."
    else:
        Fcr_ltb = Cb * pi**2 * E / (Lb / rt) ** 2 * sqrt(
            1.0 + 0.078 * termino * (Lb / rt) ** 2
        )
        Mn_ltb, eq_ltb = min(Fcr_ltb * Sxc, Mn_cfy), "F4-3 / F4-5"
        descripcion_fcr = "Fcr calculado con F4-5."
        regimen_ltb = f"Lb={Lb:.3f} > Lr={Lr:.3f}."
    estados.append(EstadoLimiteMomento(
        "LTB — Pandeo lateral-torsional", Mn_ltb, eq_ltb,
        f"{regimen_ltb} Lp={Lp:.3f}; Lr={Lr:.3f}; rt={rt:.3f}; FL={FL:.3f}."
        + (f" Fcr={Fcr_ltb:.3f} MPa." if Fcr_ltb is not None else ""),
        Fcr=Fcr_ltb, descripcion_Fcr=descripcion_fcr,
    ))

    lam, lp, lr = flange.lambda_real, flange.lambda_p, flange.lambda_r
    if flange.clasificacion == "COMPACTO":
        Mn_flb, eq_flb = Mn_cfy, "F4-13(a)"
    elif flange.clasificacion == "NO COMPACTO":
        Mn_flb = Mn_cfy - (Mn_cfy - FL * Sxc) * (lam - lp) / (lr - lp)
        Mn_flb, eq_flb = min(Mn_flb, Mn_cfy), "F4-13"
    else:
        kc = max(0.35, min(0.76, 4.0 / sqrt(geo["h"] / geo["tw"])))
        Mn_flb, eq_flb = 0.9 * E * kc * Sxc / lam**2, "F4-14"
    estados.append(EstadoLimiteMomento("FLB — Pandeo local del patín comprimido", Mn_flb, eq_flb,
                                       f"λ={lam:.3f}; λp={lp:.3f}; λr={lr:.3f}."))

    if Sxt < Sxc:
        Rpt = _rpc_rpt(Mp=Mp, My=Myt, web=web, relacion_iyc=relacion_iyc)
        Mn_tfy = Rpt * Myt
        estados.append(EstadoLimiteMomento("TFY — Fluencia del patín traccionado", Mn_tfy, "F4-15 a F4-17",
                                           f"Rpt={Rpt:.4f}; Myt={Myt:.3f}."))
    return _resolver("F4", estados, f"Iyc/Iy={relacion_iyc:.4f}; hc={hc:.3f}; aw={aw:.3f}.")


def calcular_f5(
    *, E: float, Fy: float, prop, geo: dict, lado_compresion: str,
    Lb: float, Cb: float, resultados_b4: Iterable,
    cubreplacas: dict | None = None,
) -> ResultadoCapituloF:
    """F5: I con alma esbelta, eje mayor."""
    for n, v in {"E": E, "Fy": Fy, "Lb": Lb, "Cb": Cb}.items():
        _positivo(n, v)
    _, Sxc, Sxt, _, _ = _datos_eje(prop, "x-x", lado_compresion)
    flange = _buscar_resultado(resultados_b4, ("patín", "cubreplaca"))
    rt, aw_f4, hc = _rt_perfil_i(prop, geo, cubreplacas, lado_compresion)
    aw = min(10.0, aw_f4)
    Rpg = 1.0 - aw / (1200.0 + 300.0 * aw) * (
        hc / geo["tw"] - 5.7 * sqrt(E / Fy)
    )
    Rpg = min(1.0, max(0.0, Rpg))
    Mn_cfy = Rpg * Fy * Sxc
    estados = [EstadoLimiteMomento("CFY — Fluencia del patín comprimido", Mn_cfy, "F5-1",
                                    f"Rpg={Rpg:.4f}; aw={aw:.3f}.")]

    Lp = 1.1 * rt * sqrt(E / Fy)
    Lr = pi * rt * sqrt(E / (0.7 * Fy))
    if Lb <= Lp:
        Fcr, eq = Fy, "F5-3(a)"
    elif Lb <= Lr:
        Fcr = Cb * (Fy - 0.3 * Fy * (Lb - Lp) / (Lr - Lp))
        Fcr, eq = min(Fcr, Fy), "F5-3"
    else:
        Fcr = min(Cb * pi**2 * E / (Lb / rt) ** 2, Fy)
        eq = "F5-4"
    Mn_ltb = Rpg * Fcr * Sxc
    estados.append(EstadoLimiteMomento(
        "LTB — Pandeo lateral-torsional", Mn_ltb, "F5-2 / " + eq,
        f"Lp={Lp:.3f}; Lr={Lr:.3f}; rt={rt:.3f}; Fcr={Fcr:.3f} MPa.",
        Fcr=Fcr, descripcion_Fcr=f"Fcr calculado con {eq}.",
    ))

    lam, lp, lr = flange.lambda_real, flange.lambda_p, flange.lambda_r
    if flange.clasificacion == "COMPACTO":
        Fcr_flb, eq_flb = Fy, "F5-7(a)"
    elif flange.clasificacion == "NO COMPACTO":
        Fcr_flb = Fy - 0.3 * Fy * (lam - lp) / (lr - lp)
        eq_flb = "F5-8"
    else:
        kc = max(0.35, min(0.76, 4.0 / sqrt(geo["h"] / geo["tw"])))
        Fcr_flb, eq_flb = 0.9 * E * kc / lam**2, "F5-9"
    Mn_flb = Rpg * Fcr_flb * Sxc
    estados.append(EstadoLimiteMomento(
        "FLB — Pandeo local del patín comprimido", Mn_flb, "F5-7 / " + eq_flb,
        f"Fcr={Fcr_flb:.3f} MPa; λ={lam:.3f}.",
        Fcr=Fcr_flb, descripcion_Fcr=f"Fcr calculado con {eq_flb}.",
    ))
    if Sxt < Sxc:
        estados.append(EstadoLimiteMomento("TFY — Fluencia del patín traccionado", Fy * Sxt, "F5-10"))
    return _resolver("F5", estados, f"Rpg={Rpg:.4f}; hc={hc:.3f}; aw(F4)={aw_f4:.3f}.")


def calcular_f6(
    *, E: float, Fy: float, prop, lado_compresion: str,
    resultados_b4: Iterable,
) -> ResultadoCapituloF:
    """F6: perfiles I y canales flexionados respecto al eje menor."""
    _, Sy, _, Zy, _ = _datos_eje(prop, "y-y", lado_compresion)
    Mp = _limite_mp(Fy, Zy, Sy, 1.6)
    flange = _buscar_resultado(resultados_b4, ("patín",))
    estados = [EstadoLimiteMomento("Y — Fluencia", Mp, "F6-1")]
    lam, lp, lr = flange.lambda_real, flange.lambda_p, flange.lambda_r
    Fcr_flb = None
    if flange.clasificacion == "COMPACTO":
        Mn_flb, eq = Mp, "F6-2(a)"
    elif flange.clasificacion == "NO COMPACTO":
        Mn_flb = Mp - (Mp - 0.7 * Fy * Sy) * (lam - lp) / (lr - lp)
        eq = "F6-2"
        Fcr_flb = min(Mn_flb, Mp) / Sy
    else:
        Fcr_flb = 0.69 * E / lam**2
        Mn_flb, eq = Fcr_flb * Sy, "F6-3 / F6-4"
    estados.append(EstadoLimiteMomento(
        "FLB — Pandeo local del patín", min(Mn_flb, Mp), eq,
        f"λ={lam:.3f}; λp={lp:.3f}; λr={lr:.3f}."
        + (f" Fcr={Fcr_flb:.3f} MPa." if Fcr_flb is not None else ""),
        Fcr=Fcr_flb,
        descripcion_Fcr=("Fcr calculado con F6-4." if flange.clasificacion == "ESBELTO"
                         else "Fcr equivalente = Mn/Sy; F6-2 calcula Mn directamente."
                         if flange.clasificacion == "NO COMPACTO" else ""),
    ))
    return _resolver("F6", estados)


def _propiedades_rectangulos(rects: Sequence[tuple[float, float, float, float]]) -> tuple[float, float, float, float, float]:
    """Área, xbar, ybar, Ix e Iy de rectángulos (x, y, b, h)."""
    area = sum(b * h for x, y, b, h in rects)
    _positivo("área efectiva", area)
    xbar = sum(b * h * (x + b / 2.0) for x, y, b, h in rects) / area
    ybar = sum(b * h * (y + h / 2.0) for x, y, b, h in rects) / area
    Ix = sum(b * h**3 / 12.0 + b * h * (y + h / 2.0 - ybar) ** 2 for x, y, b, h in rects)
    Iy = sum(h * b**3 / 12.0 + b * h * (x + b / 2.0 - xbar) ** 2 for x, y, b, h in rects)
    return area, xbar, ybar, Ix, Iy


def modulo_efectivo_cajon(*, B: float, H: float, t: float, eje: str, lado_compresion: str, be: float) -> float:
    """Módulo elástico efectivo de una caja con ancho efectivo en la pared comprimida."""
    for n, v in {"B": B, "H": H, "t": t, "be": be}.items():
        _positivo(n, v)
    if 2 * t >= min(B, H):
        raise ValueError("El espesor no puede alcanzar la mitad de B o H.")
    rects: list[tuple[float, float, float, float]] = []
    if eje == "x-x":
        b_sup = be if lado_compresion == "Superior" else B
        b_inf = be if lado_compresion == "Inferior" else B
        rects.extend([
            ((B - b_inf) / 2.0, 0.0, b_inf, t),
            ((B - b_sup) / 2.0, H - t, b_sup, t),
            (0.0, t, t, H - 2 * t),
            (B - t, t, t, H - 2 * t),
        ])
        _, _, ybar, Ix, _ = _propiedades_rectangulos(rects)
        c = H - ybar if lado_compresion == "Superior" else ybar
        return Ix / c
    h_der = be if lado_compresion == "Derecha" else H - 2 * t
    h_izq = be if lado_compresion == "Izquierda" else H - 2 * t
    rects.extend([
        (0.0, 0.0, B, t),
        (0.0, H - t, B, t),
        (0.0, t + ((H - 2 * t) - h_izq) / 2.0, t, h_izq),
        (B - t, t + ((H - 2 * t) - h_der) / 2.0, t, h_der),
    ])
    _, xbar, _, _, Iy = _propiedades_rectangulos(rects)
    c = B - xbar if lado_compresion == "Derecha" else xbar
    return Iy / c


def calcular_f7(
    *, E: float, Fy: float, prop, geo: dict, fabricacion: str,
    eje: str, lado_compresion: str, resultados_b4: Iterable,
    Lb: float | None = None, Cb: float = 1.0,
) -> ResultadoCapituloF:
    """F7: HSS rectangular/cuadrado y secciones cajón."""
    _, S, _, Z, r_lateral = _datos_eje(prop, eje, lado_compresion)
    Mp = Fy * Z
    flange = _buscar_resultado(resultados_b4, ("patines",))
    web = _buscar_resultado(resultados_b4, ("almas",))
    estados = [EstadoLimiteMomento("Y — Fluencia", Mp, "F7-1")]

    lam, lp, lr = flange.lambda_real, flange.lambda_p, flange.lambda_r
    if flange.clasificacion == "COMPACTO":
        Mn_flb, eq_flb = Mp, "F7-2(a)"
    elif flange.clasificacion == "NO COMPACTO":
        Mn_flb = Mp - (Mp - Fy * S) * (lam - lp) / (lr - lp)
        Mn_flb, eq_flb = min(Mn_flb, Mp), "F7-2"
    else:
        raiz = sqrt(E / Fy)
        coef = 0.38 if fabricacion == "Rolled" else 0.34
        b = lam * geo["t"]
        be = 1.92 * geo["t"] * raiz * (1.0 - coef / lam * raiz)
        be = min(b, max(1e-9, be))
        Se = modulo_efectivo_cajon(
            B=geo["B"], H=geo["H"], t=geo["t"], eje=eje,
            lado_compresion=lado_compresion, be=be,
        )
        Mn_flb, eq_flb = Fy * Se, "F7-3 / " + ("F7-4" if fabricacion == "Rolled" else "F7-5")
    estados.append(EstadoLimiteMomento("FLB — Pandeo local del patín", Mn_flb, eq_flb,
                                       f"λ={lam:.3f}; λp={lp:.3f}; λr={lr:.3f}."))

    lamw, lpw, lrw = web.lambda_real, web.lambda_p, web.lambda_r
    if web.clasificacion == "ESBELTO" and fabricacion == "Rolled":
        raise ValueError(
            "F7 indica que no existen HSS con almas esbeltas; revise las dimensiones o trate la sección como cajón Built-up."
        )
    if web.clasificacion == "COMPACTO":
        Mn_wlb, eq_wlb = Mp, "F7-6(a)"
    elif web.clasificacion == "NO COMPACTO":
        Mn_wlb = Mp - (Mp - Fy * S) * (lamw - lpw) / (lrw - lpw)
        Mn_wlb, eq_wlb = min(Mn_wlb, Mp), "F7-6"
    else:
        if flange.clasificacion == "ESBELTO" and fabricacion == "Built-up":
            raise ValueError("F7 no aborda secciones cajón con almas y patines simultáneamente esbeltos.")
        # F7-7 con Rpg de F5-6 y aw = 2h tw/(b tf).
        b = flange.lambda_real * geo["t"]
        h = web.lambda_real * geo["t"]
        aw = min(10.0, 2.0 * h / max(b, 1e-12))
        Rpg = 1.0 - aw / (1200.0 + 300.0 * aw) * (lamw - 5.7 * sqrt(E / Fy))
        Rpg = min(1.0, max(0.0, Rpg))
        Mn_wlb, eq_wlb = Rpg * Fy * S, "F7-7 / F5-6"
    estados.append(EstadoLimiteMomento("WLB — Pandeo local del alma", Mn_wlb, eq_wlb,
                                       f"λw={lamw:.3f}; λpw={lpw:.3f}; λrw={lrw:.3f}."))

    es_cuadrada = abs(geo["B"] - geo["H"]) <= 1e-9
    eje_mayor = "x-x" if prop.Ix >= prop.Iy else "y-y"
    aplica_ltb = (not es_cuadrada) and eje == eje_mayor
    if aplica_ltb:
        if Lb is None:
            raise ValueError("F7 requiere Lb cuando se verifica LTB sobre el eje mayor.")
        _positivo("Lb", Lb)
        _positivo("Cb", Cb)
        Lp = 0.13 * E * r_lateral * sqrt(prop.J * prop.Ag) / Mp
        Lr = 2.0 * E * r_lateral * sqrt(prop.J * prop.Ag) / (0.7 * Fy * S)
        Fcr_ltb = None
        descripcion_fcr = ""
        if Lb <= Lp:
            Mn_ltb, eq = Mp, "F7-8(a)"
            obs_ltb = f"Lb={Lb:.3f} ≤ Lp={Lp:.3f}; LTB no reduce Mn."
        elif Lb <= Lr:
            Mn_ltb = Cb * (Mp - (Mp - 0.7 * Fy * S) * (Lb - Lp) / (Lr - Lp))
            Mn_ltb, eq = min(Mn_ltb, Mp), "F7-8"
            Fcr_ltb = Mn_ltb / S
            descripcion_fcr = "Fcr equivalente = Mn/S; F7-8 calcula Mn directamente."
            obs_ltb = (
                f"Lp={Lp:.3f} < Lb={Lb:.3f} ≤ Lr={Lr:.3f}; "
                f"Fcr equivalente=Mn/S={Fcr_ltb:.3f} MPa."
            )
        else:
            Fcr_ltb = 2.0 * E * Cb * sqrt(prop.J * prop.Ag) / (Lb / r_lateral) / S
            Mn_ltb = min(Fcr_ltb * S, Mp)
            eq = "F7-9"
            descripcion_fcr = "Fcr equivalente obtenido al expresar F7-9 como Mn=Fcr·S."
            obs_ltb = f"Lb={Lb:.3f} > Lr={Lr:.3f}; Fcr={Fcr_ltb:.3f} MPa."
        estados.append(EstadoLimiteMomento(
            "LTB — Pandeo lateral-torsional", Mn_ltb, eq,
            f"{obs_ltb} Lp={Lp:.3f}; Lr={Lr:.3f}.",
            Fcr=Fcr_ltb, descripcion_Fcr=descripcion_fcr,
        ))
        obs = "LTB evaluado porque la sección es rectangular y se flexiona sobre su eje mayor."
    else:
        obs = "LTB no aplica a una sección cuadrada ni a flexión sobre el eje menor (nota de F7)."
    return _resolver("F7", estados, obs)


def calcular_f8(*, E: float, Fy: float, prop, geo: dict, resultados_b4: Iterable) -> ResultadoCapituloF:
    """F8: tubo circular."""
    lam = geo["D"] / geo["t"]
    if lam >= 0.45 * E / Fy:
        raise ValueError("F8 solo aplica cuando D/t < 0.45·E/Fy.")
    pared = _buscar_resultado(resultados_b4, ("pared circular",))
    S = min(prop.Sx_sup, prop.Sx_inf)
    Mp = Fy * prop.Zx
    estados = [EstadoLimiteMomento("Y — Fluencia", Mp, "F8-1")]
    Fcr_lb = None
    descripcion_fcr = ""
    if pared.clasificacion == "COMPACTO":
        Mn_lb, eq = Mp, "F8-2(a)"
    elif pared.clasificacion == "NO COMPACTO":
        Mn_lb = (0.021 * E / lam + Fy) * S
        Mn_lb, eq = min(Mn_lb, Mp), "F8-2"
        Fcr_lb = Mn_lb / S
        descripcion_fcr = "Fcr equivalente = Mn/S; F8-2 calcula Mn directamente."
    else:
        Fcr_lb = 0.33 * E / lam
        Mn_lb, eq = Fcr_lb * S, "F8-3 / F8-4"
        descripcion_fcr = "Fcr calculado con F8-4."
    estados.append(EstadoLimiteMomento(
        "LB — Pandeo local", Mn_lb, eq,
        f"D/t={lam:.3f}; clasificación={pared.clasificacion}."
        + (f" Fcr={Fcr_lb:.3f} MPa." if Fcr_lb is not None else ""),
        Fcr=Fcr_lb, descripcion_Fcr=descripcion_fcr,
    ))
    return _resolver("F8", estados)


def _curva_f10_ltb(My: float, Mcr: float) -> tuple[float, str]:
    _positivo("My", My)
    _positivo("Mcr", Mcr)
    razon = My / Mcr
    if razon <= 1.0:
        Mn = (1.92 - 1.17 * sqrt(razon)) * My
        return min(Mn, 1.5 * My), "F10-2"
    Mn = (0.92 - 0.17 * Mcr / My) * Mcr
    return Mn, "F10-3"


def _local_pata_angulo(*, E: float, Fy: float, Sc: float, resultado_pata) -> tuple[float, str]:
    lam = resultado_pata.lambda_real
    if resultado_pata.clasificacion == "COMPACTO":
        return float("inf"), "F10-6(a)"
    if resultado_pata.clasificacion == "NO COMPACTO":
        Mn = Fy * Sc * (2.43 - 1.72 * lam * sqrt(Fy / E))
        return Mn, "F10-6"
    Fcr = 0.71 * E / lam**2
    return Fcr * Sc, "F10-7 / F10-8"


def calcular_f9(
    *, perfil: str, E: float, Fy: float, prop, geo: dict,
    lado_compresion: str, Lb: float, resultados_b4: Iterable,
) -> ResultadoCapituloF:
    """F9: tees y ángulos dobles cargados en el plano de simetría."""
    for n, v in {"E": E, "Fy": Fy, "Lb": Lb}.items():
        _positivo(n, v)
    Sx = min(prop.Sx_sup, prop.Sx_inf)
    My = Fy * Sx
    stem_comp = lado_compresion == "Inferior" if perfil == "Tee" else lado_compresion == "Superior"
    if perfil == "Tee":
        if stem_comp:
            Mp = My
            eq_y = "F9-4"
        else:
            Mp = min(Fy * prop.Zx, 1.6 * My)
            eq_y = "F9-2 / F9-3"
        d = geo["d"]
    else:
        if stem_comp:
            Mp = 1.5 * My
            eq_y = "F9-5"
        else:
            Mp = min(Fy * prop.Zx, 1.6 * My)
            eq_y = "F9-2 / F9-3"
        d = geo["b1"]
    estados = [EstadoLimiteMomento("Y — Fluencia", Mp, "F9-1 / " + eq_y)]

    raiz_iyj = sqrt(prop.Iy * prop.J)
    signo = -1.0 if stem_comp else 1.0
    B = signo * 2.3 * (d / Lb) * sqrt(prop.Iy / prop.J)
    Mcr = 1.95 * E / Lb * raiz_iyj * (B + sqrt(1.0 + B**2))
    if stem_comp:
        if perfil == "Tee":
            Mn_ltb, eq_ltb = min(Mcr, My), "F9-10 / F9-12 / F9-13"
        else:
            Mn_ltb, eq_ltb = _curva_f10_ltb(My, Mcr)
            eq_ltb = "F9-10 / F9-12 / " + eq_ltb
    else:
        Lp = 1.76 * prop.ry * sqrt(E / Fy)
        Lr = 1.95 * E / Fy * raiz_iyj / Sx * sqrt(2.36 * (Fy / E) * d * Sx / prop.J + 1.0)
        if Lb <= Lp:
            Mn_ltb, eq_ltb = Mp, "F9-6(a)"
        elif Lb <= Lr:
            Mn_ltb = Mp - (Mp - My) * (Lb - Lp) / (Lr - Lp)
            eq_ltb = "F9-6"
        else:
            Mn_ltb, eq_ltb = Mcr, "F9-7 / F9-10 / F9-11"
    estados.append(EstadoLimiteMomento("LTB — Pandeo lateral-torsional", Mn_ltb, eq_ltb,
                                       f"B={B:.4f}; Mcr={Mcr:.3f}."))

    if perfil == "Tee":
        if not stem_comp:
            flange = _buscar_resultado(resultados_b4, ("patín",))
            Sxc = prop.Sx_sup
            if flange.clasificacion == "COMPACTO":
                Mn_flb, eq = float("inf"), "F9-14(a)"
            elif flange.clasificacion == "NO COMPACTO":
                Mn_flb = Mp - (Mp - 0.7 * Fy * Sxc) * (
                    (flange.lambda_real - flange.lambda_p) / (flange.lambda_r - flange.lambda_p)
                )
                Mn_flb, eq = min(Mn_flb, 1.6 * My), "F9-14"
            else:
                Mn_flb, eq = 0.7 * E * Sxc / flange.lambda_real**2, "F9-15"
            if Mn_flb != float("inf"):
                estados.append(EstadoLimiteMomento("FLB — Pandeo local del patín", Mn_flb, eq))
        else:
            stem = _buscar_resultado(resultados_b4, ("vástago",))
            lam = stem.lambda_real
            raiz = sqrt(E / Fy)
            if lam <= 0.84 * raiz:
                Fcr, eq = Fy, "F9-17"
            elif lam <= 1.52 * raiz:
                Fcr = (1.43 - 0.515 * lam * sqrt(Fy / E)) * Fy
                eq = "F9-18"
            else:
                Fcr, eq = 1.52 * E / lam**2, "F9-19"
            estados.append(EstadoLimiteMomento(
                "WLB — Pandeo local del vástago", Fcr * prop.Sx_inf,
                "F9-16 / " + eq, f"Fcr={Fcr:.3f} MPa.",
                Fcr=Fcr, descripcion_Fcr=f"Fcr calculado con {eq}.",
            ))
    else:
        # Pata horizontal = ala (Pata 2); pata vertical = alma (Pata 1).
        if stem_comp:
            pata = _buscar_resultado(resultados_b4, ("pata 1",))
            Mn_llb, eq = _local_pata_angulo(E=E, Fy=Fy, Sc=prop.Sx_sup, resultado_pata=pata)
            if Mn_llb != float("inf"):
                estados.append(EstadoLimiteMomento("WLB — Pandeo local de patas de alma", Mn_llb, "F9.4(b) / " + eq))
        else:
            pata = _buscar_resultado(resultados_b4, ("pata 2",))
            Mn_llb, eq = _local_pata_angulo(E=E, Fy=Fy, Sc=prop.Sx_inf, resultado_pata=pata)
            if Mn_llb != float("inf"):
                estados.append(EstadoLimiteMomento("FLB — Pandeo local de patas de ala", Mn_llb, "F9.3(b) / " + eq))
    return _resolver("F9", estados)


def _rectangulos_angulo(geo: dict) -> list[tuple[float, float, float, float]]:
    b1, b2, t = geo["b1"], geo["b2"], geo["t"]
    return [(0.0, 0.0, t, b1), (t, 0.0, b2 - t, t)]


def modulos_principales_angulo(prop, geo: dict) -> tuple[float, float, float, float]:
    """S1+, S1-, S2+, S2- de un ángulo a partir de sus vértices."""
    from math import cos, radians, sin
    theta = radians(prop.theta_p_deg)
    puntos: list[tuple[float, float]] = []
    for x, y, b, h in _rectangulos_angulo(geo):
        puntos.extend([(x, y), (x + b, y), (x, y + h), (x + b, y + h)])
    def modulos(I: float, angulo: float) -> tuple[float, float]:
        s, c = sin(angulo), cos(angulo)
        coords = [-s * (x - prop.x_bar) + c * (y - prop.y_bar) for x, y in puntos]
        cpos = max(coords)
        cneg = -min(coords)
        return I / cpos, I / cneg
    S1p, S1n = modulos(prop.I1, theta)
    S2p, S2n = modulos(prop.I2, theta + pi / 2.0)
    return S1p, S1n, S2p, S2n


def calcular_f10(
    *, E: float, Fy: float, prop, geo: dict, resultados_b4: Iterable,
    Lb: float, Cb: float, modo_eje: str, eje_geometrico: str,
    lado_compresion: str, restriccion_continua: bool,
    restriccion_solo_mmax: bool, extremo_libre: str,
    pata_comprimida: str, beta_w: float = 0.0,
) -> ResultadoCapituloF:
    """F10 para ángulos simples.

    ``modo_eje``: ``Geométrico``, ``Principal mayor`` o ``Principal menor``.
    ``extremo_libre``: ``Compresión`` o ``Tracción``.
    """
    for n, v in {"E": E, "Fy": Fy, "Lb": Lb, "Cb": Cb}.items():
        _positivo(n, v)
    igual = abs(geo["b1"] - geo["b2"]) <= 1e-9
    Cb_f10 = min(Cb, 1.5)
    if modo_eje == "Geométrico":
        if not igual and not restriccion_continua:
            raise ValueError("F10 permite ejes geométricos sin restricción continua solo para ángulos de patas iguales.")
        if eje_geometrico == "x-x":
            Scomp = prop.Sx_sup if lado_compresion == "Superior" else prop.Sx_inf
        else:
            Scomp = prop.Sy_der if lado_compresion == "Derecha" else prop.Sy_izq
        factor_s = 1.0 if (restriccion_continua or restriccion_solo_mmax) else 0.80
        Sdis = factor_s * Scomp
        My = Fy * Sdis
        if restriccion_continua:
            Mcr = None
        else:
            b = max(geo["b1"], geo["b2"])
            term = sqrt(1.0 + 0.88 * (Lb * geo["t"] / b**2) ** 2)
            signo = -1.0 if extremo_libre == "Compresión" else 1.0
            Mcr = 0.58 * E * b**4 * geo["t"] * Cb_f10 / Lb**2 * (term + signo)
            if restriccion_solo_mmax:
                Mcr *= 1.25
    else:
        S1p, S1n, S2p, S2n = modulos_principales_angulo(prop, geo)
        if modo_eje == "Principal mayor":
            Sdis = min(S1p, S1n)
            My = Fy * Sdis
            Mcr = 9.0 * E * prop.Ag * prop.r2 * geo["t"] * Cb_f10 / (8.0 * Lb) * (
                sqrt(1.0 + (4.4 * beta_w * prop.r2 / (Lb * geo["t"])) ** 2)
                + 4.4 * beta_w * prop.r2 / (Lb * geo["t"])
            ) if not restriccion_continua else None
        elif modo_eje == "Principal menor":
            Sdis = min(S2p, S2n)
            My = Fy * Sdis
            Mcr = None
        else:
            raise ValueError("Modo de eje F10 no reconocido.")

    estados = [EstadoLimiteMomento("Y — Fluencia", 1.5 * My, "F10-1", f"My={My:.3f}.")]
    if Mcr is not None:
        Mn_ltb, eq = _curva_f10_ltb(My, Mcr)
        estados.append(EstadoLimiteMomento("LTB — Pandeo lateral-torsional", Mn_ltb, eq,
                                           f"Mcr={Mcr:.3f}; Cb limitado a {Cb_f10:.3f}."))

    if extremo_libre == "Compresión":
        palabra = "pata 1" if pata_comprimida == "Pata 1" else "pata 2"
        pata = _buscar_resultado(resultados_b4, (palabra,))
        Sc = Sdis
        Mn_llb, eq_llb = _local_pata_angulo(E=E, Fy=Fy, Sc=Sc, resultado_pata=pata)
        if Mn_llb != float("inf"):
            estados.append(EstadoLimiteMomento("LLB — Pandeo local de la pata", Mn_llb, eq_llb,
                                               f"Pata evaluada: {pata_comprimida}; Sc={Sc:.3f}."))
    return _resolver("F10", estados)


def calcular_f11_barra_rectangular(
    *, E: float, Fy: float, Z: float, S: float, Lb: float, d: float, t: float, Cb: float,
) -> ResultadoCapituloF:
    """F11 para barras rectangulares; disponible para futuras geometrías."""
    Mp = min(Fy * Z, 1.5 * Fy * S)
    estados = [EstadoLimiteMomento("Y — Fluencia", Mp, "F11-1")]
    parametro = Lb * d / t**2
    Fcr_ltb = None
    descripcion_fcr = ""
    if parametro <= 0.08 * E / Fy:
        Mn_ltb, eq = Mp, "F11-2(a)"
    elif parametro <= 1.9 * E / Fy:
        Mn_ltb = Cb * (1.52 - 0.274 * parametro * Fy / E) * Fy * S
        Mn_ltb, eq = min(Mn_ltb, Mp), "F11-3"
        Fcr_ltb = Mn_ltb / S
        descripcion_fcr = "Fcr equivalente = Mn/S; F11-3 calcula Mn directamente."
    else:
        Fcr_ltb = 1.9 * E * Cb / parametro
        Mn_ltb, eq = min(Fcr_ltb * S, Mp), "F11-4 / F11-5"
        descripcion_fcr = "Fcr calculado con F11-5."
    estados.append(EstadoLimiteMomento(
        "LTB — Pandeo lateral-torsional", Mn_ltb, eq,
        (f"Fcr={Fcr_ltb:.3f} MPa." if Fcr_ltb is not None else ""),
        Fcr=Fcr_ltb, descripcion_Fcr=descripcion_fcr,
    ))
    return _resolver("F11", estados)


def agregar_estados(resultado: ResultadoCapituloF, estados_adicionales: Iterable[EstadoLimiteMomento]) -> ResultadoCapituloF:
    """Recalcula el estado gobernante al añadir verificaciones como F13-1."""
    extras = list(estados_adicionales)
    if not extras:
        return resultado
    return _resolver(resultado.seccion, [*resultado.estados, *extras], *resultado.observaciones)



# -----------------------------------------------------------------------------
# Agujeros de pernos para F13.1
# -----------------------------------------------------------------------------
# Dimensiones máximas nominales de agujeros según AISC 360-22, Tabla J3.3.
# Todas las dimensiones se almacenan internamente en milímetros. Para el cálculo
# del área neta, B4.3b exige aumentar la dimensión nominal del agujero en 2 mm
# para la serie métrica o 1/16 in para la serie imperial.
_PERNOS_METRICOS_MM: dict[str, float] = {
    "M12": 12.0,
    "M16": 16.0,
    "M20": 20.0,
    "M22": 22.0,
    "M24": 24.0,
    "M27": 27.0,
    "M30": 30.0,
    "M36": 36.0,
}

_PERNOS_IMPERIALES_IN: dict[str, float] = {
    '1/2 in': 0.5,
    '5/8 in': 0.625,
    '3/4 in': 0.75,
    '7/8 in': 0.875,
    '1 in': 1.0,
    '1 1/8 in': 1.125,
    '1 1/4 in': 1.25,
    '1 3/8 in': 1.375,
    '1 1/2 in': 1.5,
}

# (ancho, longitud) nominales del agujero, en mm. En agujeros circulares ambas
# dimensiones son iguales. La longitud de la ranura se usa cuando la ranura es
# perpendicular a la fuerza que produce la sección neta.
_AGUJEROS_METRICOS_J33: dict[float, dict[str, tuple[float, float]]] = {
    12.0: {"Estándar": (14.0, 14.0), "Sobredimensionado": (16.0, 16.0), "Ranura corta": (14.0, 18.0), "Ranura larga": (14.0, 32.0)},
    16.0: {"Estándar": (18.0, 18.0), "Sobredimensionado": (20.0, 20.0), "Ranura corta": (18.0, 22.0), "Ranura larga": (18.0, 40.0)},
    20.0: {"Estándar": (22.0, 22.0), "Sobredimensionado": (24.0, 24.0), "Ranura corta": (22.0, 26.0), "Ranura larga": (22.0, 50.0)},
    22.0: {"Estándar": (24.0, 24.0), "Sobredimensionado": (28.0, 28.0), "Ranura corta": (24.0, 30.0), "Ranura larga": (24.0, 55.0)},
    24.0: {"Estándar": (27.0, 27.0), "Sobredimensionado": (30.0, 30.0), "Ranura corta": (27.0, 32.0), "Ranura larga": (27.0, 60.0)},
    27.0: {"Estándar": (30.0, 30.0), "Sobredimensionado": (35.0, 35.0), "Ranura corta": (30.0, 37.0), "Ranura larga": (30.0, 67.0)},
    30.0: {"Estándar": (33.0, 33.0), "Sobredimensionado": (38.0, 38.0), "Ranura corta": (33.0, 40.0), "Ranura larga": (33.0, 75.0)},
    36.0: {"Estándar": (39.0, 39.0), "Sobredimensionado": (44.0, 44.0), "Ranura corta": (39.0, 46.0), "Ranura larga": (39.0, 90.0)},
}


def opciones_pernos_comerciales(serie: str) -> tuple[str, ...]:
    """Devuelve las etiquetas comerciales disponibles para la serie elegida."""
    if serie == "Métrica":
        return tuple(_PERNOS_METRICOS_MM)
    if serie == "Imperial":
        return tuple(_PERNOS_IMPERIALES_IN)
    raise ValueError("La serie de pernos debe ser 'Métrica' o 'Imperial'.")


def _dimensiones_agujero_imperial(db_in: float, tipo: str) -> tuple[float, float]:
    """Tabla J3.3 en pulgadas; devuelve ancho y longitud nominales."""
    if db_in <= 0:
        raise ValueError("El diámetro nominal del perno debe ser mayor que cero.")
    ancho = db_in + 1.0 / 16.0
    if tipo == "Estándar":
        largo = ancho
    elif tipo == "Sobredimensionado":
        if db_in <= 7.0 / 8.0:
            largo = db_in + 3.0 / 16.0
        elif db_in <= 1.0:
            largo = db_in + 1.0 / 4.0
        else:
            largo = db_in + 5.0 / 16.0
        ancho = largo
    elif tipo == "Ranura corta":
        if db_in <= 7.0 / 8.0:
            largo = db_in + 1.0 / 4.0
        elif db_in <= 1.0:
            largo = db_in + 5.0 / 16.0
        else:
            largo = db_in + 3.0 / 8.0
    elif tipo == "Ranura larga":
        largo = 2.5 * db_in
    else:
        raise ValueError(f"Tipo de agujero no reconocido: {tipo}.")
    return ancho * 25.4, largo * 25.4


def dimensiones_agujero_j33(
    *, serie: str, perno: str, tipo: str,
    orientacion_ranura: str = "Paralela a la fuerza",
) -> tuple[float, float, float, float]:
    """Devuelve ``(db, ancho, largo, d_neta)`` en mm.

    ``d_neta`` es la dimensión que se descuenta perpendicularmente a la fuerza,
    incluida la adición exigida por B4.3b. Para ranuras paralelas a la fuerza se
    descuenta el ancho; para ranuras perpendiculares, la longitud.
    """
    tipos = {"Estándar", "Sobredimensionado", "Ranura corta", "Ranura larga"}
    if tipo not in tipos:
        raise ValueError(f"Tipo de agujero no reconocido: {tipo}.")

    if serie == "Métrica":
        try:
            db = _PERNOS_METRICOS_MM[perno]
            ancho, largo = _AGUJEROS_METRICOS_J33[db][tipo]
        except KeyError as exc:
            raise ValueError(f"Perno métrico no reconocido: {perno}.") from exc
        incremento_neto = 2.0
    elif serie == "Imperial":
        try:
            db_in = _PERNOS_IMPERIALES_IN[perno]
        except KeyError as exc:
            raise ValueError(f"Perno imperial no reconocido: {perno}.") from exc
        db = db_in * 25.4
        ancho, largo = _dimensiones_agujero_imperial(db_in, tipo)
        incremento_neto = 25.4 / 16.0
    else:
        raise ValueError("La serie de pernos debe ser 'Métrica' o 'Imperial'.")

    if tipo.startswith("Ranura"):
        if orientacion_ranura == "Paralela a la fuerza":
            dimension_transversal = ancho
        elif orientacion_ranura == "Perpendicular a la fuerza":
            dimension_transversal = largo
        else:
            raise ValueError("Orientación de ranura no reconocida.")
    else:
        dimension_transversal = ancho

    d_neta = dimension_transversal + incremento_neto
    return db, ancho, largo, d_neta


def deduccion_ancho_seccion_neta(
    *, numero_agujeros: int, d_neta: float, disposicion: str,
    numero_diagonales: int = 0, s: float | None = None, g: float | None = None,
) -> float:
    """Deducción total de ancho para una trayectoria neta crítica.

    Para agujeros alineados devuelve ``n·d_neta``. Para una trayectoria
    escalonada aplica la adición ``Σs²/(4g)`` indicada para agujeros alternados.
    """
    if numero_agujeros < 1:
        raise ValueError("La sección neta crítica debe atravesar al menos un agujero.")
    _positivo("d_neta", d_neta)
    deduccion = numero_agujeros * d_neta
    if disposicion == "Alineados":
        return deduccion
    if disposicion != "Escalonados":
        raise ValueError("La disposición debe ser 'Alineados' o 'Escalonados'.")
    if numero_diagonales < 1:
        raise ValueError("Una trayectoria escalonada debe incluir al menos un tramo diagonal.")
    if s is None or g is None:
        raise ValueError("Para agujeros escalonados se requieren s y g.")
    _positivo("s", s)
    _positivo("g", g)
    deduccion -= numero_diagonales * s**2 / (4.0 * g)
    if deduccion <= 0:
        raise ValueError(
            "La deducción neta resultó no positiva. Revise el número de agujeros, "
            "los tramos diagonales y las separaciones s y g."
        )
    return deduccion


def verificar_agujeros_ala_tension(
    *, Fu: float, Fy: float, Afg: float, Afn: float, Sx: float,
) -> tuple[bool, float | None, float, str]:
    """F13.1: verifica la reducción por agujeros en el ala de tensión.

    Devuelve ``(requiere_reduccion, Mn, Yt, explicación)``. Cuando la ruptura no
    aplica, ``Mn`` es ``None``.
    """
    for n, v in {"Fu": Fu, "Fy": Fy, "Afg": Afg, "Afn": Afn, "Sx": Sx}.items():
        _positivo(n, v)
    if Afn > Afg:
        raise ValueError("Afn no puede ser mayor que Afg.")
    Yt = 1.0 if Fy / Fu <= 0.8 else 1.1
    izquierda = Fu * Afn
    derecha = Yt * Fy * Afg
    if izquierda >= derecha:
        return False, None, Yt, (
            f"Fu·Afn={izquierda:.3f} ≥ Yt·Fy·Afg={derecha:.3f}; "
            "la ruptura del ala de tensión no aplica."
        )
    Mn = Fu * Afn / Afg * Sx
    return True, Mn, Yt, (
        f"Fu·Afn={izquierda:.3f} < Yt·Fy·Afg={derecha:.3f}; "
        "se aplica F13-1."
    )


def verificaciones_proporcion_i_f13(
    *, E: float, Fy: float, prop, geo: dict, cubreplacas: dict | None,
    lado_compresion: str, simetria: str, alma_esbelta: bool,
    separacion_rigidizadores_a: float | None = None,
) -> list[tuple[str, float, float, bool, str]]:
    """F13.2: devuelve verificaciones numéricas de proporciones para perfiles I.

    Cada tupla contiene ``(verificación, valor, límite, cumple, ecuación)``.
    """
    revisiones: list[tuple[str, float, float, bool, str]] = []
    datos = _datos_patines_i(geo, cubreplacas, lado_compresion)
    relacion_iyc = datos["Iyc"] / prop.Iy
    if simetria == "Monosimétrica":
        # Se reportan ambos límites de F13-2 como dos verificaciones.
        revisiones.append(("Iyc/Iy — límite inferior", relacion_iyc, 0.10, relacion_iyc >= 0.10, "F13-2"))
        revisiones.append(("Iyc/Iy — límite superior", relacion_iyc, 0.90, relacion_iyc <= 0.90, "F13-2"))

    hc = _hc_perfil_i(prop, geo, cubreplacas, lado_compresion)
    aw = hc * geo["tw"] / max(datos["Afc"], 1e-12)
    revisiones.append(("aw", aw, 10.0, aw <= 10.0, "F13.2"))

    if alma_esbelta:
        lam = geo["h"] / geo["tw"]
        if separacion_rigidizadores_a is None:
            # Para una viga no rigidizada se verifica el límite explícito h/tw <= 260.
            revisiones.append(("h/tw — viga no rigidizada", lam, 260.0, lam <= 260.0, "F13.2"))
        else:
            _positivo("separación a", separacion_rigidizadores_a)
            razon = separacion_rigidizadores_a / geo["h"]
            limite = 12.0 * sqrt(E / Fy) if razon <= 1.5 else 0.40 * E / Fy
            ecuacion = "F13-3" if razon <= 1.5 else "F13-4"
            revisiones.append(("h/tw — alma esbelta", lam, limite, lam <= limite, ecuacion))
    return revisiones
