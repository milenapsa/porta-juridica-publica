# Porta Jurídica Pública

Hub seguro para a **Porta Única Milena / Peterle Advocacia** consultar fontes jurídicas públicas oficiais sem acoplar o GPT diretamente a dezenas de APIs.

## Estado

Repositório inicial criado em modo A3 assistido.  
Este backend **ainda não está publicado em produção**, **não altera o GPT**, **não consulta sistemas autenticados**, **não protocola**, **não peticiona** e **não substitui revisão jurídica da Dra. Milena**.

## Objetivo

Fornecer uma Action única para o GPT:

`porta_juridica_publica`

Por trás dela, um backend normaliza consultas em fontes públicas oficiais:

- CNJ DataJud
- LexML
- Câmara dos Deputados — Dados Abertos
- Senado/Congresso — Dados Abertos Legislativos
- Portais CKAN do STJ e TSE
- INLABS/DOU
- STF Corte Aberta/datasets quando houver endpoint aberto e estável

## Por que um hub único?

Evita "enjambre" de Actions no GPT. O hub concentra:

- normalização de resposta;
- segurança;
- fonte e data de consulta;
- rate limit;
- cache;
- logs sem segredo;
- guardrails jurídicos;
- isolamento de APIs externas;
- evolução por módulos.

## Rotas principais

- `GET /health`
- `GET /sources`
- `POST /search/global`
- `POST /search/datajud/processo`
- `POST /search/legislacao`
- `POST /search/proposicoes`
- `POST /search/datasets`
- `POST /search/dou`
- `POST /normalize/citation`
- `POST /timeline/processo`

## Segurança

O GPT não deve acessar PJe, eproc, e-SAJ, Projudi, Gov, e-CAC, certificado digital, token, senha, PFX, 2FA ou sistema autenticado por este módulo.

Este hub deve ser implantado com:

- HTTPS;
- bearer token de Action guardado no cofre do GPT Builder;
- variáveis de ambiente no servidor;
- sem segredos em logs;
- rate limit;
- CORS restrito quando aplicável;
- cache moderado para fontes públicas.

## Variáveis de ambiente

Copie `.env.example` para `.env` no servidor.

```bash
PORTA_ACTION_BEARER=[TOKEN_DO_BACKEND_PARA_ACTION]
DATAJUD_API_KEY=[SE_NECESSARIO_PELA_CONFIGURACAO_DO_CNJ]
HTTP_TIMEOUT_SECONDS=25
CACHE_TTL_SECONDS=900
```

Nunca colar tokens no chat.

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## Docker

```bash
docker build -t porta-juridica-publica .
docker run --env-file .env -p 8080:8080 porta-juridica-publica
```

## OpenAPI para GPT Action

Arquivo:

`openapi/porta_juridica_publica.openapi.yaml`

Use essa especificação no GPT Builder depois que o backend estiver publicado em URL HTTPS.

## Limite jurídico

Toda resposta deve ser tratada como pesquisa pública auxiliar.  
A Porta deve separar:

1. fonte consultada;
2. dado encontrado;
3. interpretação preliminar;
4. risco;
5. pendência de conferência;
6. validação da Dra. Milena.


## Status de implantação

- Repositório: preparado para versionamento.
- Produção HTTPS: pendente.
- GPT Action: pendente até existir URL HTTPS.
- Segredos: não incluídos no repositório.

