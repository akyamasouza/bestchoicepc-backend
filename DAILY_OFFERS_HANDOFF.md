# Daily Offers Handoff

## Estado atual

- `daily_offers` agora separa identidade canonica e chave externa:
  - `entity_id`: ObjectId string do produto no MongoDB.
  - `entity_sku`: SKU/slug usado para busca e validacao contra o texto do Telegram.
- O listener do Telegram usa topicos do grupo para limitar o matching por categoria.
- `/daily-offers` continua retornando apenas ofertas do dia.
- `/matches` usa ofertas canonicas recentes com janela fixa de 90 dias.
- Ofertas rejeitadas (`status = "rejected"`) ficam fora das leituras canonicas.

## Limpeza aplicada no banco local

- A migracao `python -m app.scripts.migrate_daily_offers_entity_sku --apply` foi aplicada com sucesso.
- A auditoria `python -m app.scripts.audit_daily_offers_matches --apply` marcou 25 ofertas com match incorreto como `rejected`.
- Exemplo corrigido: uma oferta de RTX 5060 a R$ 2.600 estava vinculada incorretamente como RTX 5090.

## Validacao realizada

```text
pytest -> 106 passed
```

Tambem foi validado manualmente:

```text
canonical_rtx_5090=0
/matches com budget=5500 retornou combinacoes sem usar RTX 5090 falsa.
```

## Onde paramos

Discussao de produto pendente:

- Hoje o `budget` do `/matches` ainda representa o orcamento usado no filtro de CPU + GPU.
- Para usuario final, `budget=5500` normalmente significa PC inteiro.
- Proxima refatoracao recomendada:
  - interpretar `budget` como orcamento total do PC;
  - criar uma estimativa 80/20 para o restante da build;
  - derivar `cpu_gpu_budget = budget - platform_cost_estimate`;
  - usar `cpu_gpu_budget` no filtro atual de CPU/GPU;
  - retornar os campos de estimativa na resposta para transparencia.

Nao foi decidido implementar sugestao de resolucao ou modo `auto`.
