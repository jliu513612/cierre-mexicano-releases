"""
inpc_feed_standalone.py — Publicador del INPC AUTOCONTENIDO (gemelo de tc_feed_standalone).

No depende del repo de código; solo stdlib. Pensado para vivir DENTRO del repo
público cierre-mexicano-releases y que un job de GitHub Actions lo corra (con el
secret BANXICO_TOKEN) y commitee inpc.json a sí mismo. Así NINGÚN cliente necesita
token de Banxico: el .exe solo baja inpc.json del repo (feeds._fetch_inpc).

Genera el INPC mensual (Banxico SIE serie SP1, ÍNDICE GENERAL, base 2a quincena
jul-2018 = 100), en el MISMO formato que VALIDA el cliente (scripts/inpc.py lee
_meta.serie — un payload sin _meta se rechaza entero):
    {"_meta": {"serie": "SP1", ...}, "datos": {"AAAA-MM": "valor", ...}}

Uso (lo invoca el workflow):
    BANXICO_TOKEN=xxxx python inpc_feed_standalone.py --out inpc.json
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone

# INPC ÍNDICE GENERAL. La serie anterior (la SUBYACENTE) está PROHIBIDA —
# CAL-53: la ley (LISR 44/31, CFF 17-A) solo reconoce el general y la
# subyacente corre ~1-1.5% por debajo; la advertencia canónica vive en
# scripts/inpc.py y el registro en constantes_legales.json (retirados).
SERIE = "SP1"
BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"


def _fetch(token, fini, ffin):
    url = f"{BASE}/{SERIE}/datos/{fini}/{ffin}"
    req = urllib.request.Request(url, headers={
        "Bmx-Token": token, "Accept": "application/json",
        "User-Agent": "CierreMexicano-inpc"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = {}
    for d in data["bmx"]["series"][0].get("datos", []):
        try:
            dd, mm, yy = d["fecha"].split("/")
            out[f"{int(yy):04d}-{int(mm):02d}"] = str(float(d["dato"]))
        except (ValueError, KeyError):
            continue
    return out


def payload_de(datos):
    """El payload EXACTO que el cliente valida: inpc._serie_valida lee
    data["_meta"]["serie"] — la serie va AQUÍ dentro o el archivo se rechaza
    entero, aunque los datos fueran correctos (el defecto medido el
    2026-08-10: la versión anterior escribía la serie en la raíz)."""
    return {
        "_meta": {
            "fuente": f"Banxico SIE serie {SERIE} (INPC índice general; "
                      f"replica INEGI/DOF)",
            "serie": SERIE,
            "nota": "INPC base 2a quincena julio 2018 = 100. Verificar contra DOF.",
            "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "datos": dict(sorted(datos.items())),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="inpc.json")
    ap.add_argument("--desde", default="2018-01-01")
    ap.add_argument("--token", default=os.environ.get("BANXICO_TOKEN", ""))
    args = ap.parse_args()
    if not args.token:
        print("ERROR: falta BANXICO_TOKEN (env o --token).", file=sys.stderr)
        return 1
    hoy = date.today()
    datos = _fetch(args.token, args.desde, hoy.isoformat())
    if not datos:
        print("ERROR: Banxico no devolvió datos.", file=sys.stderr)
        return 2
    payload = payload_de(datos)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(datos)} meses de INPC -> {args.out} (último {max(datos)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
