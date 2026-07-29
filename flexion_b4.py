"""Clasificación local para flexión según Tabla B4.1b.

Sistema interno esperado: longitudes en mm y esfuerzos en MPa.
Este módulo solo clasifica elementos como compactos, no compactos o esbeltos.
No calcula resistencia del Capítulo F.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt


@dataclass(frozen=True)
class ResultadoFlexion:
    elemento: str
    caso: int
    condicion: str
    relacion: str
    formula_lp: str
    formula_lr: str
    lambda_real: float
    lambda_p: float
    lambda_r: float
    clasificacion: str
    observacion: str = ""

    def como_dict(self):
        return asdict(self)


def _pos(nombre: str, valor: float) -> None:
    if valor <= 0:
        raise ValueError(f"{nombre} debe ser mayor que cero.")


def _kc(h: float, tw: float) -> float:
    _pos("h", h); _pos("tw", tw)
    return max(0.35, min(0.76, 4.0 / sqrt(h / tw)))


def _clasificar(lam: float, lp: float, lr: float) -> str:
    if not (lp <= lr + 1e-12):
        raise ValueError("Se obtuvo λp > λr; revise geometría y propiedades.")
    if lam <= lp:
        return "COMPACTO"
    if lam <= lr:
        return "NO COMPACTO"
    return "ESBELTO"


def _res(elemento, caso, condicion, relacion, flp, flr, lam, lp, lr, obs=""):
    return ResultadoFlexion(
        elemento=elemento, caso=caso, condicion=condicion, relacion=relacion,
        formula_lp=flp, formula_lr=flr, lambda_real=lam,
        lambda_p=lp, lambda_r=lr, clasificacion=_clasificar(lam, lp, lr),
        observacion=obs,
    )


def _pna_y_perfil_i(bf, tf, h, tw, cubreplacas=None):
    """Eje neutro plástico y centroide de I con cubreplacas mediante rectángulos."""
    rects = [
        (-bf/2, 0.0, bf, tf),
        (-tw/2, tf, tw, h),
        (-bf/2, tf+h, bf, tf),
    ]
    cp = cubreplacas or {}
    d = h + 2*tf
    if cp.get("inferior"):
        q = cp["inferior"]; B = float(q["B"]); t = float(q["t"])
        rects.append((-B/2, -t, B, t))
    if cp.get("superior"):
        q = cp["superior"]; B = float(q["B"]); t = float(q["t"])
        rects.append((-B/2, d, B, t))
    A = sum(b*hh for _,_,b,hh in rects)
    ybar = sum(b*hh*(y+hh/2) for _,y,b,hh in rects)/A
    lo = min(y for _,y,_,_ in rects); hi = max(y+hh for _,y,_,hh in rects)
    def abajo(ycut):
        return sum(b*min(max(ycut-y,0.0),hh) for _,y,b,hh in rects)
    for _ in range(90):
        mid=(lo+hi)/2
        if abajo(mid)<A/2: lo=mid
        else: hi=mid
    return ybar, (lo+hi)/2, min(y for _,y,_,_ in rects), max(y+hh for _,y,_,hh in rects)


def evaluar_flexion(
    *, perfil: str, fabricacion: str, eje: str, sentido: str,
    geo: dict, E: float, Fy: float, propiedades=None,
    cubreplacas: dict | None = None,
) -> list[ResultadoFlexion]:
    """Selecciona automáticamente casos 10 a 21 de B4.1b."""
    _pos("E", E); _pos("Fy", Fy)
    raiz = sqrt(E/Fy)
    resultados: list[ResultadoFlexion] = []
    comp_sup = sentido == "Superior en compresión"

    if perfil == "Perfil I":
        bf, tf, h, tw = geo["bf"], geo["tf"], geo["h"], geo["tw"]
        for n,v in {"bf":bf,"tf":tf,"h":h,"tw":tw}.items(): _pos(n,v)
        cp = cubreplacas or {}
        asim = bool(cp.get("superior")) != bool(cp.get("inferior"))
        if cp.get("superior") and cp.get("inferior"):
            asim = abs(cp["superior"]["B"]-cp["inferior"]["B"])>1e-9 or abs(cp["superior"]["t"]-cp["inferior"]["t"])>1e-9

        if eje == "x-x":
            b = bf/2.0
            if fabricacion == "Rolled":
                lp=0.38*raiz; lr=1.0*raiz
                resultados.append(_res("Patín comprimido",10,"No rigidizado","bf/(2·tf)","0.38√(E/Fy)","1.0√(E/Fy)",b/tf,lp,lr))
            else:
                kc=_kc(h,tw)
                # FL según nota [b], usando módulos del lado comprimido/traccionado.
                if propiedades is None:
                    ratio_st=1.0
                elif comp_sup:
                    ratio_st=propiedades.Sx_inf/propiedades.Sx_sup
                else:
                    ratio_st=propiedades.Sx_sup/propiedades.Sx_inf
                FL = 0.7*Fy if ratio_st >= 0.7 else max(0.5*Fy, Fy*ratio_st)
                lp=0.38*raiz; lr=0.95*sqrt(kc*E/FL)
                resultados.append(_res("Patín comprimido",11,"No rigidizado","bf/(2·tf)","0.38√(E/Fy)","0.95√(kc·E/FL)",b/tf,lp,lr,f"kc={kc:.3f}; FL={FL:.3f}; Sxt/Sxc={ratio_st:.3f}."))

            if asim:
                if propiedades is None:
                    raise ValueError("El caso 16 requiere propiedades geométricas calculadas.")
                ybar, yp, ymin, ymax = _pna_y_perfil_i(bf,tf,h,tw,cp)
                cara = tf+h if comp_sup else tf
                hc = 2*abs(cara-ybar); hp = 2*abs(cara-yp)
                Sxc = propiedades.Sx_sup if comp_sup else propiedades.Sx_inf
                My = Fy*Sxc; Mp = Fy*propiedades.Zx
                den=(0.54*(Mp/My)-0.09)**2
                lp=(hc/hp)*raiz/den
                lr=5.70*raiz
                lp=min(lp,lr)
                resultados.append(_res("Alma monosimétrica",16,"Rigidizado","hc/tw","(hc/hp)√(E/Fy)/(0.54Mp/My−0.09)²","5.70√(E/Fy)",hc/tw,lp,lr,f"hc={hc:.3f}, hp={hp:.3f}, Mp/My={Mp/My:.3f}."))
            else:
                resultados.append(_res("Alma",15,"Rigidizado","h/tw","3.76√(E/Fy)","5.70√(E/Fy)",h/tw,3.76*raiz,5.70*raiz))
        else:
            resultados.append(_res("Patines en flexión respecto a eje menor",13,"No rigidizado","bf/(2·tf)","0.38√(E/Fy)","1.0√(E/Fy)",bf/(2*tf),0.38*raiz,1.0*raiz))

        cp_comp = cp.get("superior" if comp_sup else "inferior")
        if cp_comp:
            bcp = float(cp_comp.get("b", cp_comp["B"])); tcp=float(cp_comp["t"])
            resultados.append(_res("Cubreplaca del ala comprimida",18,"Rigidizado","b/t","1.12√(E/Fy)","1.40√(E/Fy)",bcp/tcp,1.12*raiz,1.40*raiz,"b es la distancia entre líneas de pernos o soldaduras."))

    elif perfil == "Canal":
        b,tf,h,tw=geo["b"],geo["tf"],geo["h"],geo["tw"]
        if eje=="x-x":
            resultados.append(_res("Patín comprimido",10,"No rigidizado","b/tf","0.38√(E/Fy)","1.0√(E/Fy)",b/tf,0.38*raiz,1.0*raiz))
            resultados.append(_res("Alma",15,"Rigidizado","h/tw","3.76√(E/Fy)","5.70√(E/Fy)",h/tw,3.76*raiz,5.70*raiz))
        else:
            resultados.append(_res("Patines en flexión respecto a eje menor",13,"No rigidizado","b/tf","0.38√(E/Fy)","1.0√(E/Fy)",b/tf,0.38*raiz,1.0*raiz))

    elif perfil == "Tee":
        b,tf,d,tw=geo["b"],geo["tf"],geo["d"],geo["tw"]
        if eje=="x-x":
            if comp_sup:
                resultados.append(_res("Patín comprimido",10,"No rigidizado","b/tf","0.38√(E/Fy)","1.0√(E/Fy)",b/tf,0.38*raiz,1.0*raiz))
            else:
                resultados.append(_res("Vástago comprimido",14,"No rigidizado","d/tw","0.84√(E/Fy)","1.52√(E/Fy)",d/tw,0.84*raiz,1.52*raiz))
        else:
            resultados.append(_res("Patín en flexión respecto a eje menor",13,"No rigidizado","b/tf","0.38√(E/Fy)","1.0√(E/Fy)",b/tf,0.38*raiz,1.0*raiz))

    elif perfil == "Ángulo simple":
        for nombre,b in (("Pata 1",geo["b1"]),("Pata 2",geo["b2"])):
            resultados.append(_res(nombre,12,"No rigidizado",f"{nombre}/t","0.54√(E/Fy)","0.91√(E/Fy)",b/geo["t"],0.54*raiz,0.91*raiz))

    elif perfil == "Ángulo doble con separadores":
        # La tabla mostrada no contiene una fila específica para ángulos dobles en flexión.
        raise ValueError("La Tabla B4.1b mostrada no define un caso directo para ángulos dobles en flexión. Evalúe cada ángulo según la disposición y el eje correspondiente.")

    elif perfil in {"Tubo cuadrado","Tubo rectangular"}:
        B,H,t=geo["B"],geo["H"],geo["t"]
        if eje=="x-x": b_flange=B-2*t; h_web=H-2*t
        else: b_flange=H-2*t; h_web=B-2*t
        if fabricacion=="Rolled":
            resultados.append(_res("Paredes que actúan como patines",17,"Rigidizado","b/t","1.12√(E/Fy)","1.40√(E/Fy)",b_flange/t,1.12*raiz,1.40*raiz,"Se usa dimensión exterior menos 2t; ajuste a la definición de ancho plano del producto si dispone del radio interior."))
        else:
            resultados.append(_res("Placas que actúan como patines",21,"Rigidizado","b/t","1.12√(E/Fy)","1.49√(E/Fy)",b_flange/t,1.12*raiz,1.49*raiz))
        resultados.append(_res("Paredes que actúan como almas",19,"Rigidizado","h/t","2.42√(E/Fy)","5.70√(E/Fy)",h_web/t,2.42*raiz,5.70*raiz))

    elif perfil == "Tubo circular":
        D,t=geo["D"],geo["t"]
        resultados.append(_res("Pared circular",20,"Caso circular","D/t","0.07E/Fy","0.31E/Fy",D/t,0.07*E/Fy,0.31*E/Fy))
    else:
        raise ValueError(f"Perfil no reconocido: {perfil}")

    return resultados


def clasificacion_global(resultados: list[ResultadoFlexion]) -> tuple[str, str]:
    orden={"COMPACTO":0,"NO COMPACTO":1,"ESBELTO":2}
    gob=max(resultados,key=lambda r:(orden[r.clasificacion], r.lambda_real/r.lambda_r))
    return gob.clasificacion, gob.elemento
