"""Gráficos SVG con el estilo de Sensei.app (barras redondeadas, líneas de 2 px, rejilla suave)."""
from __future__ import annotations

from html import escape

AZUL = "#7590b0"      # sueño en Sensei
VERDE = "#9ab9a3"     # batería corporal
LINEA = "#315f4d"     # tendencias
BANDA = "#41715d"
TINTA_SUAVE = "#6c7a72"
REJILLA = "#e5e9e3"

W, H, IZQ, DER, ARR, ABA = 640, 240, 44, 10, 18, 26


def _escala(vals, cero=True):
    v = [x for x in vals if x is not None]
    if not v:
        return 0, 1
    lo, hi = (0 if cero else min(v)), max(v)
    if not cero:
        margen = (hi - lo) * 0.15 or 1
        lo, hi = lo - margen, hi + margen
    if hi == lo:
        hi = lo + 1
    return lo, hi * (1.05 if cero else 1)


def _ejes(lo, hi, unidad, etiquetas_x):
    g = []
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = ARR + (H - ARR - ABA) * (1 - k / 4)
        g.append(f'<line x1="{IZQ}" x2="{W - DER}" y1="{y:.1f}" y2="{y:.1f}" stroke="{REJILLA}"/>')
        g.append(f'<text x="{IZQ - 6}" y="{y + 4:.1f}" font-size="11" text-anchor="end" fill="{TINTA_SUAVE}">'
                 f'{_fmt(v)}</text>')
    if unidad:
        g.append(f'<text x="{IZQ}" y="11" font-size="10" fill="{TINTA_SUAVE}">{escape(unidad)}</text>')
    n = len(etiquetas_x)
    paso = max(1, n // 6)
    for i, t in enumerate(etiquetas_x):
        if i % paso == 0 or i == n - 1:
            x = IZQ + (W - IZQ - DER) * (i + 0.5) / n
            g.append(f'<text x="{x:.1f}" y="{H - 8}" font-size="10" text-anchor="middle" fill="{TINTA_SUAVE}">'
                     f'{escape(t)}</text>')
    return "".join(g)


def _fmt(v):
    return (f"{v:.1f}" if abs(v) < 20 and v != int(v) else f"{v:.0f}").replace(".", ",")


def _y(v, lo, hi):
    return ARR + (H - ARR - ABA) * (1 - (v - lo) / (hi - lo))


def barras(valores, etiquetas, color=AZUL, unidad="", titulos=None) -> str:
    lo, hi = _escala(valores)
    n = max(1, len(valores))
    ancho = (W - IZQ - DER) / n
    g = [_ejes(lo, hi, unidad, etiquetas)]
    for i, v in enumerate(valores):
        if v is None:
            continue
        x = IZQ + ancho * i + ancho * 0.18
        y = _y(v, lo, hi)
        alto = H - ABA - y
        t = escape((titulos or etiquetas)[i]) + f": {_fmt(v)} {escape(unidad)}"
        g.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{ancho * 0.64:.1f}" height="{max(alto, 1):.1f}" rx="4" '
                 f'fill="{color}"><title>{t}</title></rect>')
    return f'<svg viewBox="0 0 {W} {H}" role="img">{"".join(g)}</svg>'


def rangos(minimos, maximos, puntos, etiquetas, color=VERDE, unidad="") -> str:
    lo, hi = 0, 100
    n = max(1, len(maximos))
    ancho = (W - IZQ - DER) / n
    g = [_ejes(lo, hi, unidad, etiquetas)]
    for i, (a, b) in enumerate(zip(minimos, maximos)):
        if b is None:
            continue
        a = a if a is not None else b
        x = IZQ + ancho * i + ancho * 0.18
        y1, y2 = _y(b, lo, hi), _y(a, lo, hi)
        g.append(f'<rect x="{x:.1f}" y="{y1:.1f}" width="{ancho * 0.64:.1f}" height="{max(y2 - y1, 2):.1f}" rx="4" '
                 f'fill="{color}"><title>{escape(etiquetas[i])}: {_fmt(a)}–{_fmt(b)}</title></rect>')
        p = puntos[i] if puntos else None
        if p is not None:
            g.append(f'<circle cx="{x + ancho * 0.32:.1f}" cy="{_y(p, lo, hi):.1f}" r="3.5" fill="#29473a"/>')
    return f'<svg viewBox="0 0 {W} {H}" role="img">{"".join(g)}</svg>'


def linea(valores, etiquetas, unidad="", media=None, banda=None) -> str:
    """Línea de 2 px; `media` dibuja la media móvil punteada; `banda` (lo, hi) sombrea tu zona habitual."""
    todo = [v for v in valores if v is not None] + ([x for x in media if x is not None] if media else [])
    if banda:
        todo += list(banda)
    lo, hi = _escala(todo, cero=False)
    n = max(1, len(valores))
    g = [_ejes(lo, hi, unidad, etiquetas)]

    def x(i):
        return IZQ + (W - IZQ - DER) * (i + 0.5) / n
    if banda:
        y1, y2 = _y(banda[1], lo, hi), _y(banda[0], lo, hi)
        g.append(f'<rect x="{IZQ}" y="{y1:.1f}" width="{W - IZQ - DER}" height="{y2 - y1:.1f}" fill="{BANDA}" '
                 f'opacity=".1"/>')

    def tramo(serie, estilo):
        pts = [f"{x(i):.1f},{_y(v, lo, hi):.1f}" for i, v in enumerate(serie) if v is not None]
        return f'<polyline points="{" ".join(pts)}" fill="none" {estilo}/>' if len(pts) > 1 else ""
    if media:
        g.append(tramo(media, f'stroke="#9aa59f" stroke-width="2" stroke-dasharray="5 4"'))
    g.append(tramo(valores, f'stroke="{LINEA}" stroke-width="2" stroke-linejoin="round"'))
    for i, v in enumerate(valores):
        if v is not None:
            g.append(f'<circle cx="{x(i):.1f}" cy="{_y(v, lo, hi):.1f}" r="3" fill="{LINEA}">'
                     f'<title>{escape(etiquetas[i])}: {_fmt(v)} {escape(unidad)}</title></circle>')
    ult = max((i for i, v in enumerate(valores) if v is not None), default=None)
    if ult is not None:
        g.append(f'<circle cx="{x(ult):.1f}" cy="{_y(valores[ult], lo, hi):.1f}" r="6" fill="#1f3a2f"/>')
    return f'<svg viewBox="0 0 {W} {H}" role="img">{"".join(g)}</svg>'
