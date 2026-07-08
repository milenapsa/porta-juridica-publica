import datetime
import os
import re
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import AliasChoices, BaseModel, Field, ConfigDict

app = FastAPI(title="Porta Jurídica Pública", version="0.1.1-a3")


class Search(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    q: str = Field(..., validation_alias=AliasChoices("q", "query"), min_length=1, max_length=500)
    limit: int = Field(10, ge=1, le=50)
    source_hint: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class Proc(BaseModel):
    numero_processo: str = Field(..., min_length=5, max_length=80)
    tribunal: str | None = None
    endpoint: str | None = None
    limit: int = Field(10, ge=1, le=50)


class Cit(BaseModel):
    title: str
    source: str
    url: str | None = None
    date: str | None = None


SOURCES = [
    {"id": "cnj_datajud", "name": "CNJ DataJud", "docs": "https://datajud-wiki.cnj.jus.br/api-publica/"},
    {"id": "lexml", "name": "LexML", "docs": "https://www12.senado.leg.br/dados-abertos/legislativo/legislacao/acervo-do-portal-lexml"},
    {"id": "camara", "name": "Câmara Dados Abertos", "docs": "https://dadosabertos.camara.leg.br/swagger/api.html"},
    {"id": "senado", "name": "Senado/Congresso Dados Abertos", "docs": "https://legis.senado.leg.br/dadosabertos/docs/index.html"},
    {"id": "stj_ckan", "name": "STJ CKAN", "docs": "https://dadosabertos.web.stj.jus.br/"},
    {"id": "tse_ckan", "name": "TSE CKAN", "docs": "https://dadosabertos.tse.jus.br/"},
    {"id": "dou_inlabs", "name": "INLABS/DOU", "docs": "https://www.gov.br/imprensanacional/pt-br/servicos/inlabs"},
    {"id": "stf_corte_aberta", "name": "STF Corte Aberta", "docs": "https://portal.stf.jus.br/transparencia/"},
]

BLOCK = [
    "pje", "projudi", "eproc", "e-saj", "esaj", "pdpj", "mni",
    "senha", "token", "pfx", "2fa", "certificado digital",
    "peticionar", "protocolar", "gov.br", "e-cac",
]


def meta(conf: str = "media") -> dict[str, Any]:
    return {
        "write_executed": False,
        "confidence": conf,
        "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "legal_warning": "Pesquisa pública auxiliar; revisar com a Dra. Milena.",
        "limits": [
            "Não protocola, não peticiona, não acessa sistema autenticado.",
            "Não afirma prazo final, trânsito em julgado ou tese definitiva.",
        ],
    }


def guard(q: str | None) -> None:
    hits = [x for x in BLOCK if x in (q or "").lower()]
    if hits:
        raise HTTPException(400, {"ok": False, "blocked": True, "hits": hits, **meta("baixa")})


def auth(authorization: str | None = Header(None)) -> None:
    expected = os.getenv("PORTA_ACTION_BEARER", "").strip()
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(401, "Bearer ausente ou inválido")


async def js(method: str, url: str, **kwargs: Any) -> Any:
    timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "25"))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()


def normalize(source: str, url: str, data: Any, conf: str = "media") -> dict[str, Any]:
    rows = []
    if isinstance(data, dict):
        rows = (
            data.get("dados")
            or data.get("result", {}).get("results")
            or data.get("hits", {}).get("hits")
            or []
        )

    out = []
    if isinstance(rows, list):
        for row in rows[:50]:
            raw = row.get("_source", row) if isinstance(row, dict) else row
            if isinstance(raw, dict):
                title = (
                    raw.get("titulo")
                    or raw.get("nome")
                    or raw.get("ementa")
                    or raw.get("title")
                    or raw.get("numeroProcesso")
                    or "Resultado"
                )
            else:
                title = "Resultado"
            out.append({"title": str(title)[:220], "source": source, "source_url": url, "raw": raw})

    if not out:
        out = [{"title": "Resultado bruto", "source": source, "source_url": url, "raw": data}]

    return {"ok": True, "source": source, "source_url": url, "results": out, "raw": data, **meta(conf)}


@app.get("/health")
async def health():
    return {"ok": True, "service": "porta_juridica_publica", "version": "0.1.1-a3", **meta()}


@app.get("/sources", dependencies=[Depends(auth)])
async def sources():
    return {"ok": True, "sources": SOURCES, **meta()}


@app.post("/search/datajud/processo", dependencies=[Depends(auth)])
async def datajud(p: Proc):
    guard(p.numero_processo)
    number = re.sub(r"\D", "", p.numero_processo)
    endpoint = (p.endpoint or f"api_publica_{(p.tribunal or '').lower().replace('-', '').replace('_', '')}").strip()
    if not number or endpoint == "api_publica_":
        raise HTTPException(400, "Informe número e tribunal/endpoint.")

    headers = {"Content-Type": "application/json"}
    key = os.getenv("DATAJUD_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"APIKey {key}"

    data = await js(
        "POST",
        f"https://api-publica.datajud.cnj.jus.br/{endpoint}/_search",
        headers=headers,
        json={"size": p.limit, "query": {"match": {"numeroProcesso": number}}},
    )
    return normalize("CNJ DataJud", "https://datajud-wiki.cnj.jus.br/api-publica/", data)


@app.post("/search/legislacao", dependencies=[Depends(auth)])
async def lexml(s: Search):
    guard(s.q)
    data = await js(
        "GET",
        "https://www.lexml.gov.br/busca/SRU",
        params={
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": s.q,
            "maximumRecords": str(s.limit),
        },
    )
    return normalize("LexML", "https://www12.senado.leg.br/dados-abertos/legislativo/legislacao/acervo-do-portal-lexml", data)


@app.post("/search/proposicoes", dependencies=[Depends(auth)])
async def props(s: Search):
    guard(s.q)
    if (s.source_hint or "").lower() == "senado":
        data = await js(
            "GET",
            "https://legis.senado.leg.br/dadosabertos/materia/pesquisa/lista",
            params={"termo": s.q},
            headers={"Accept": "application/json"},
        )
        return normalize("Senado/Congresso Dados Abertos", "https://legis.senado.leg.br/dadosabertos/docs/index.html", data)

    data = await js(
        "GET",
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes",
        params={"keywords": s.q, "itens": s.limit},
        headers={"Accept": "application/json"},
    )
    return normalize("Câmara Dados Abertos", "https://dadosabertos.camara.leg.br/swagger/api.html", data)


@app.post("/search/datasets", dependencies=[Depends(auth)])
async def datasets(s: Search):
    guard(s.q)
    portal = (s.source_hint or s.filters.get("portal") or "stj").lower()
    base = {
        "stj": "https://dadosabertos.web.stj.jus.br/api/3/action",
        "tse": "https://dadosabertos.tse.jus.br/api/3/action",
    }.get(portal)
    if not base:
        raise HTTPException(400, "Portal aceito: stj ou tse.")
    data = await js("GET", f"{base}/package_search", params={"q": s.q, "rows": s.limit})
    return normalize(f"{portal.upper()} CKAN", base, data)


@app.post("/search/global", dependencies=[Depends(auth)])
async def global_search(s: Search):
    q = s.q.lower()
    guard(q)
    if s.filters.get("numero_processo") or "processo" in q:
        return await datajud(
            Proc(
                numero_processo=s.filters.get("numero_processo") or s.q,
                tribunal=s.filters.get("tribunal"),
                endpoint=s.filters.get("endpoint"),
                limit=s.limit,
            )
        )
    if any(x in q for x in ["pl ", "pec ", "projeto", "proposição", "proposicao"]):
        return await props(s)
    return await lexml(s)


@app.post("/search/dou", dependencies=[Depends(auth)])
async def dou(s: Search):
    guard(s.q)
    return {
        "ok": True,
        "source": "INLABS/DOU",
        "results": [
            {
                "title": "Conector protegido",
                "summary": "Depende de configuração segura no servidor; sem credenciais no GPT.",
            }
        ],
        **meta("baixa"),
    }


@app.post("/normalize/citation", dependencies=[Depends(auth)])
async def cit(c: Cit):
    parts = [x for x in [c.title, c.source, c.date, c.url] if x]
    return {"ok": True, "citation": ". ".join(parts) + ".", **meta()}
