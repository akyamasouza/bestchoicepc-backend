# Análise SWOT + Plano de Ação 80/20 — BestChoice PC Backend

**Data:** 2026-06-09 | **Arquivos .py:** 148 | **Testes:** 46 arquivos | **LOC:** ~10k (app) + ~3k (tests)

---

## Diagnóstico Crítico (Antes da SWOT)

Antes da análise, identifiquei **problemas de integridade** que tornam qualquer plano de expansão prematuro:

| # | Problema | Severidade |
|---|----------|-----------|
| 1 | `CatalogCandidateEnricher` é importado em 3 arquivos mas **não existe** — a classe real é `CandidateEnricher`. Import quebra em runtime. | 🔴 Broken |
| 2 | Redis está no `docker-compose.yml`, `config.py` e `requirements.txt` mas **zero uso** no código. | 🟡 Peso morto |
| 3 | Modelos duplicados: `models/domain.py` (dataclasses) **vs** `schemas/` (Pydantic). Duas representações dos mesmos conceitos (`DailyOffer`, `EntityType`, `CandidateStatus`, `PendingDailyOfferEvidence`). | 🔴 Fragilidade |
| 4 | Dois parsers de Telegram com lógica duplicada: `OfferExtractor` (domain) e `TelegramOfferParser` (schemas). Regex de preço, loja, parcelas repetidos. | 🟡 Duplicação |
| 5 | Normalização de loja em **3 lugares diferentes** com aliases divergentes: `domain.py`, `offer_extractor.py`, `telegram_offer_parser.py`. | 🔴 Inconsistência |
| 6 | Dois orquestradores concorrentes: `DailyOfferSyncService` (funcional) e `DailyOfferPipeline` (placeholder async). | 🟡 Confusão |
| 7 | `FuzzySkuStrategy` sempre retorna `no_match()` — classe morta. | 🟢 Código zumbi |
| 8 | 14 `DomainEvent` definidos no `domain.py` — **nenhum é disparado** em lugar algum. DDD de fachada. | 🟡 Peso morto |
| 9 | `TelegramSearchService` (sync wrapper) quebra se chamado dentro do loop do FastAPI — retorna lista vazia silenciosamente. | 🟡 Armadilha |
| 10 | `EnrichmentStatus` duplicado: Enum no `domain.py` vs `Literal` no `schemas/catalog_candidate.py` com valores diferentes (`in_progress` vs `running`, `completed` vs `done`). | 🔴 Inconsistência |

---

## SWOT — Visão Realista

### Forças (Strengths)

- **Motor de matching sólido**: `MatchService` + `MatchScoringPolicy` + `MatchReasonBuilder` é o núcleo que entrega valor real. Ponderação multi-critério por use-case e resolução funciona.
- **Pipeline Telegram funcional**: `OfferExtractor` → `EntityMatcher` → `CatalogMatcher` → `DailyOfferRepository` funciona em produção (comandos manuais).
- **Estrutura de pastas saudável**: `routes/`, `services/`, `repositories/` bem definidos. Separação de responsabilidades visível.
- **Protocolos para MongoDB**: `CollectionProtocol`, `CursorProtocol` permitem testar sem banco real.
- **Cobertura de testes extensa**: 46 arquivos de teste.

### Fraquezas (Weaknesses)

- **Duplicação conceitual severa**: Domain (dataclass) e Schema (Pydantic) competem. Cada campo novo exige atualização em 2+ lugares. Fonte de bugs de sincronia.
- **Código morto e inacabado**: `DailyOfferPipeline`, `FuzzySkuStrategy`, Domain Events, `TelegramSyncAdapter`, Workers. Criados com intenção, nunca finalizados.
- **Complexidade desnecessária**: Para um MVP que faz "catalogar hardware + recomendar combos", há 20 services, 14 scripts, 2 pipelines concorrentes, 8 entidades de catálogo.
- **Zero segurança operacional**: Sem auth, sem rate limit, CORS wildcard. Implantável apenas em rede privada.
- **Dependência de IA sem fallback**: Se OpenRouter estiver offline/sem saldo, enriquecimento simplesmente falha. Sem path sem IA.

### Oportunidades (Opportunities)

- **Consolidar em 1 serviço core**: O valor real está no match CPU+GPU. Todo o resto é suporte.
- **Cortar 60% do código**: Remover duplicatas, código morto e placeholders reduz superfície de manutenção.
- **Automatizar com cron (não Docker profiles)**: Um único cron job que roda sync → enriquece → promove em sequência.
- **Adicionar cache HTTP simples** (`Cache-Control` headers) em vez de Redis — para MVP, caching de 5min no cliente é suficiente.

### Ameaças (Threats)

- **Dependência do Telegram**: Se o canal mudar formato ou cair, o sync para. Sem fonte alternativa de ofertas.
- **MongoDB como único state**: Sem backup automatizado visível. Perda do volume = perda de todo histórico.
- **Manutenção insustentável**: Com 148 arquivos e duplicação generalizada, cada feature nova introduz bugs de sincronia. O projeto já mostra sinais de entropia: classes importadas que não existem, status enums divergentes.

---

## Plano de Ação 80/20 — Simplificação Radical

### Meta: MVP com 60-70 arquivos (cortar ~50%), zero duplicação, 100% funcional

### 🔴 Fase 1 — Cirurgia de Código Morto (Semana 1)

Estas ações **não alteram comportamento** — apenas removem peso morto.

| Ação | Arquivos afetados | Ganho |
|------|-------------------|-------|
| **Deletar `DailyOfferPipeline`** (async, placeholder) | `daily_offer_pipeline.py` + imports | -1 classe duplicada do sync |
| **Deletar `FuzzySkuStrategy`** (sempre retorna `no_match`) | `matching_strategies.py` (partial) | Clareza |
| **Deletar Domain Events não usados** | `domain.py` (linhas 629-700) | -70 linhas |
| **Deletar `TelegramSearchService`** (sync wrapper quebrado) | `telegram_sync_adapter.py` | -1 footgun |
| **Deletar Workers** (nunca integrados ao docker) | `workers/enrich_worker.py`, `workers/sync_worker.py` | -2 arquivos |
| **Deletar `CandidateFactory`** (placeholder) | `daily_offer_pipeline.py` | Morre junto |
| **Deletar `SearchStrategy`/`TelegramSearchStrategy`** (abstração prematura) | `daily_offer_pipeline.py` | Morre junto |
| **Remover Redis** do `docker-compose.yml`, `config.py`, `requirements.txt` | 3 arquivos | -1 dependência |
| **Deletar `kabum_catalog.py`** (script avulso) | 1 arquivo | Clareza |
| **Remover scripts de migração** já executados (`migrate_daily_offers_entity_sku.py`) | 1 arquivo | Clareza |

**Resultado esperado:** ~12 arquivos removidos, ~800 linhas eliminadas.

### 🟡 Fase 2 — Unificação de Modelos (Semana 2)

**Problema:** `models/domain.py` (dataclasses) e `schemas/` (Pydantic) definem os mesmos conceitos.

**Decisão arquitetural radical:** Escolher **UM** sistema de modelos.

→ **Recomendação: Ficar só com Pydantic v2.** Motivos:
1. Já é o sistema de validação do FastAPI (rotas esperam Pydantic)
2. `model_dump()` → dict para MongoDB é trivial
3. `model_validate(doc)` → objeto a partir do MongoDB é trivial
4. Elimina `to_dict()` / `from_dict()` manuais (hoje há ~300 linhas disso no `domain.py`)

| Ação | Descrição |
|------|-----------|
| Migrar `DailyOffer`, `ExtractedOffer`, `CatalogEntity`, `CatalogCandidate`, `MatchResult` para Pydantic em `schemas/` | Centralizar todos os modelos |
| Mover `EntityType`, `CandidateStatus`, `EnrichmentStatus` para `schemas/common.py` (manter só lá) | Única fonte da verdade |
| Mover funções utilitárias (`_normalize_sku`, `_normalize_store_name`, `_normalize_product_name`) para `app/core/normalization.py` | Reutilização sem duplicação |
| Deletar `models/domain.py` | -1 arquivo, -730 linhas |
| Atualizar todos os imports (services, repositories, routes) para usar `schemas/` | Consistência |

**Resultado esperado:** Fim da duplicação Domain x Schema. Toda mudança de campo toca 1 arquivo.

### 🟢 Fase 3 — Unificação de Parsers (Semana 2-3)

**Problema:** `OfferExtractor` (retorna `ExtractedOffer`) e `TelegramOfferParser` (retorna `DailyOffer`) duplicam regex e normalização.

| Ação | Descrição |
|------|-----------|
| Manter **apenas** `TelegramOfferParser` — ele já é mais completo (lida com affiliate links, timezone, histórico) | Escolher o melhor |
| Fazer `TelegramOfferParser.parse()` retornar `ExtractedOffer` (intermediário) e adicionar `.to_daily_offer()` quando há match | Unificar pipeline |
| Deletar `OfferExtractor` | -1 arquivo |
| Atualizar `DailyOfferSyncService` para usar `TelegramOfferParser` | Consistência |

### 🔵 Fase 4 — Pipeline Único (Semana 3)

**Meta:** Um comando que faz tudo em sequência.

```
python -m app.scripts.daily_pipeline --entity-type cpu --limit 5
```

Fluxo: Telegram search → Parse → Match catalog → Save DailyOffer or create Candidate → Enrich candidates (AI) → Promote ready candidates

| Ação | Descrição |
|------|-----------|
| Consolidar `sync_daily_offers.py` + `enrich_catalog_candidates.py` + `promote_catalog_candidate.py` + `run_catalog_candidate_pipeline.py` em **1 script** | 4 scripts → 1 |
| Remover `docker-compose` profiles `sync-job`, `enrich-job`, `pipeline-job` — deixar só `api` e `daily-pipeline` | 5 services → 3 |
| Simplificar `docker-compose.yml` para: `mongo`, `api`, `pipeline-job` (cron) | Clareza operacional |

### 🟣 Fase 5 — Segurança Mínima Viável (Semana 4)

| Ação | Descrição |
|------|-----------|
| Adicionar middleware de API Key simples (header `X-API-Key`) | Proteção básica |
| Restringir CORS para origens específicas (via env var) | `CORS_ORIGINS=localhost,seufrontend.com` |
| Adicionar slow-rate rate limiting (100 req/min por IP) via `slowapi` | Proteção anti-abuso |

### ⚪ Fase 6 — Robustez (Semana 4+)

| Ação | Descrição |
|------|-----------|
| Adicionar `healthcheck` endpoint que verifica MongoDB (já existe `/health/ready`) | ✅ Já feito |
| Logging estruturado já configurado em `core/logging.py` | ✅ Já feito |
| Adicionar retry com backoff no OpenRouter (já trata 402/429 mas sem retry) | Resiliência |
| Adicionar cron real (dentro do container ou via `schedule` library) para rodar pipeline diariamente | Automação |

---

## Resultado Final Esperado

| Métrica | Antes | Depois |
|---------|-------|--------|
| Arquivos .py (app) | ~90 | ~50 |
| Models duplicados | 2 sistemas (domain + schemas) | 1 (schemas) |
| Parsers de Telegram | 2 | 1 |
| Orquestradores/Pipelines | 4 | 1 |
| Dependências (requirements.txt) | 10 | 8 |
| Docker services | 7 | 3 |
| Classes importadas que não existem | 1 (`CatalogCandidateEnricher`) | 0 |
| Normalização de loja duplicada | 3 lugares | 1 (`core/normalization.py`) |

---

## O Que NÃO Tocar

- **`MatchService` + `MatchScoringPolicy` + `MatchReasonBuilder`**: Funcionam, entregam valor, são testados. Só simplificar se houver demanda real.
- **Repositories com Strategy Pattern**: Bom design. Manter.
- **`EntityMatcher`**: Funciona, é testado, resolve um problema real (filtro de mensagens erradas).
- **Testes**: Só atualizar imports após unificação de modelos. Não reescrever lógica de teste.
- **Seed scripts**: Funcionam. Só remover se não forem mais usados.
