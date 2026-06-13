"""
tc_feed_standalone.py — Publicador de tipo de cambio AUTOCONTENIDO.

No depende del repo de código (banxico_fix.py); solo usa la stdlib. Pensado
para vivir DENTRO del repo público cierre-mexicano-releases y que el job de
GitHub Actions lo corra y commitee tc_feed.json a sí mismo (sin PAT).

Genera el FIX de Banxico (= TC del DOF que el SAT exige):
  - tc_obligaciones: FIX del día hábil ANTERIOR (lo que el DOF publica hoy
    y el SAT exige, CFF 20).
  - fix_hoy: FIX de hoy si ya está publicado (informativo / caja).

Uso (lo invoca el workflow):
    BANXICO_TOKEN=xxxx python tc_feed_standalone.py --out tc_feed.json
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

SERIE = "SF43718"  # FIX USD/MXN
BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"


def _fetch_serie(token, fini, ffin):
    url = f"{BASE}/{SERIE}/datos/{fini}/{ffin}"
    req = urllib.request.Request(url, headers={
        "Bmx-Token": token, "Accept": "application/json",
        "User-Agent": "CierreMexicano-tc"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    datos = data["bmx"]["series"][0].get("datos", [])
    out = {}
    for d in datos:
        try:
            dd, mm, yy = d["fecha"].split("/")
            out[date(int(yy), int(mm), int(dd))] = float(d["dato"])
        except (ValueError, KeyError):
            continue
    return out


def construir_feed(token, hoy=None):
    hoy = hoy or date.today()
    fini = (hoy - timedelta(days=15)).strftime("%Y-%m-%d")
    ffin = hoy.strftime("%Y-%m-%d")
    serie = _fetch_serie(token, fini, ffin)
    if not serie:
        raise RuntimeError("Banxico no devolvió datos del FIX")

    fechas = sorted(serie)
    previas = [d for d in fechas if d < hoy]
    if not previas:
        raise RuntimeError("Sin FIX de día hábil anterior en el rango")
    fecha_dof = max(previas)                 # el FIX que el DOF publica HOY
    tc_obligaciones = serie[fecha_dof]
    fix_hoy = serie.get(hoy)                  # puede no estar publicado aún

    return {
        "fecha_dof": fecha_dof.isoformat(),
        "tc_obligaciones": round(tc_obligaciones, 4),
        "fix_hoy": round(fix_hoy, 4) if fix_hoy is not None else None,
        "fecha_fix_hoy": hoy.isoformat(),
        "fuente": "Banxico SIE SF43718 (FIX) / DOF",
        "actualizado_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "nota": "Publicado por job diario; el cliente lo lee sin token.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tc_feed.json")
    ap.add_argument("--token", default=os.environ.get("BANXICO_TOKEN", ""))
    args = ap.parse_args(argv)
    if not args.token:
        print("ERROR: falta BANXICO_TOKEN (env o --token)", file=sys.stderr)
        return 2
    feed = construir_feed(args.token)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"OK: {args.out} -> TC obligaciones {feed['tc_obligaciones']} "
          f"(DOF {feed['fecha_dof']}), FIX hoy {feed['fix_hoy']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
