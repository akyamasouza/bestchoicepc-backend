# Handoff do pipeline de candidatos de catálogo

## Onde paramos

Foi implementada a base do pipeline multi-hardware para descoberta de itens vindos do Telegram:

- captura de candidatos em `catalog_candidates`
- enriquecimento via fetch da `product_url`
- promoção manual para coleção canônica
- persistência da oferta canônica após promoção

## O que já está funcionando

### Sync canônico + captura de candidatos
- `app/services/daily_offer_sync.py`
- `app/scripts/sync_daily_offers.py`

O sync continua persistindo ofertas canônicas válidas.
Quando há mismatch de identidade, o fluxo registra candidato em staging.

### Infra de staging
- `app/schemas/catalog_candidate.py`
- `app/repositories/catalog_candidate_repository.py`
- `app/services/hardware_registry.py`
- `app/services/catalog_candidate_pipeline.py`

### Enriquecimento
- `app/services/catalog_candidate_enricher.py`
- `app/scripts/enrich_catalog_candidates.py`

### Promoção
- `app/scripts/promote_catalog_candidate.py`

### Testes já adicionados
- `tests/test_catalog_candidate_pipeline.py`
- `tests/test_catalog_candidate_enricher.py`
- `tests/test_daily_offer_sync.py`

## Evidência validada manualmente

O usuário conseguiu:
1. rodar `sync_daily_offers`
2. verificar que `catalog_candidates` foi populada
3. rodar `enrich_catalog_candidates`
4. confirmar que vários candidatos ficaram com `status='enriched'`

Também apareceram problemas reais de qualidade no enriquecimento:
- páginas de captcha, ex.: `Captcha Magalu`
- posts compostos de configuração completa sendo tratados como candidato de produto
- candidatos enriquecidos que na prática já existem canonicamente
- `proposed_name` e `proposed_sku` ainda poluídos em alguns casos

## O que estava sendo endurecido agora

Foi iniciada uma rodada de endurecimento para:
- rejeitar captcha / páginas inválidas
- rejeitar posts compostos de configuração
- evitar candidato que já exista no catálogo canônico
- limpar `proposed_name` / `proposed_sku` antes da promoção

Arquivos mais impactados nessa etapa:
- `app/services/catalog_candidate_enricher.py`
- `app/services/catalog_candidate_pipeline.py`
- `app/repositories/catalog_candidate_repository.py`

## Próximo passo recomendado

Antes de usar promoção como fluxo normal, concluir e validar os filtros de qualidade.

Checklist objetivo:
- bloquear `captcha`, `access denied`, etc.
- bloquear textos com cara de "configuração completa"
- bloquear promoção quando o SKU canônico extraído já bater com item existente
- normalizar melhor nome e SKU promovidos
- rerodar os testes focados
- repetir o teste manual com `catalog_candidates`

## Comandos úteis

### Sync
```bash
python -m app.scripts.sync_daily_offers --entity-type cpu --limit 1
```

### Enriquecimento
```bash
python -m app.scripts.enrich_catalog_candidates --entity-type cpu
```

### Promoção manual
```bash
python -m app.scripts.promote_catalog_candidate --entity-type cpu --fingerprint "<fingerprint>"
```

### Inspeção rápida por Python
```bash
python -c "from pprint import pprint; from app.core.database import get_collection, close_mongo_client; c=get_collection('catalog_candidates'); docs=list(c.find({'entity_type':'cpu'}).sort([('last_seen',-1)]).limit(10)); [pprint(d) for d in docs]; close_mongo_client()"
```

## Observação

O fluxo estrutural está de pé. O ponto pendente agora é endurecer a qualidade antes de confiar na promoção para catálogo canônico.