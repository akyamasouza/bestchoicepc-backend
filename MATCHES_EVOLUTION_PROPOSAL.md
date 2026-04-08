# Matches Evolution Proposal

## Objetivo

Evoluir o `/matches` de um recomendador de `CPU + GPU` baseado em percentil para um recomendador de build mais aderente ao mercado brasileiro de 2026.

A proposta abaixo busca corrigir tres distorcoes atuais:

1. `budget` ainda representa apenas o filtro de `CPU + GPU`.
2. Pecas sem oferta recente ainda podem aparecer bem ranqueadas.
3. O score nao incorpora custo de plataforma, saude de mercado e longevidade de forma explicita.

## Problema Atual

Hoje o endpoint `/matches`:

- usa apenas `CPU` e `GPU` na recomendacao;
- depende de `daily_offers` apenas para `CPU` e `GPU`;
- trata ausencia de oferta como falta de dado, nao como sinal de mercado;
- nao estima custo de plataforma (`motherboard`, `ram`, `ssd`, `psu`);
- nao separa "melhor custo agora" de "melhor caminho de upgrade".

Consequencias praticas:

- combos com alto percentil, mas baixa disponibilidade real, sobem demais;
- AM4 e DDR4 ficam subvalorizados quando `RAM` e `SSD` estao caros;
- GPUs fora de linha, como `RX 6800 XT`, podem seguir competitivas no score sem refletir o varejo novo;
- builds humanas boas para o Brasil distoam do ranking retornado.

## Principios da Solucao

1. Tratar ausencia de oferta como sinal de mercado.
2. Interpretar `budget` como orcamento total do PC.
3. Separar performance de componente de custo total de plataforma.
4. Tornar explicitos os conceitos de `value_now`, `market_health` e `longevity`.
5. Evoluir de forma incremental, sem reescrever todo o sistema de uma vez.

## Resultado Esperado

Ao final da evolucao, o `/matches` deve:

- priorizar combinacoes compraveis no mercado atual;
- estimar custo total da build, nao apenas `CPU + GPU`;
- penalizar ou excluir pecas sem oferta recente;
- capturar a vantagem economica de plataformas AM4 e DDR4 quando `RAM` e `SSD` estiverem pressionados;
- retornar explicacoes mais honestas sobre custo, mercado e longevidade.

## Proposta de Implementacao

### Fase 1 - Saude de mercado por SKU

Adicionar metricas derivadas de `daily_offers` para cada SKU:

- `offer_count_30d`
- `offer_count_90d`
- `days_since_last_offer`
- `store_count_30d`
- `last_seen_price`
- `median_price_30d`
- `median_price_90d`
- `lowest_price_90d`

Classificacao sugerida:

- `active`: 3 ou mais ofertas nos ultimos 30 dias
- `sparse`: 1 ou 2 ofertas nos ultimos 30 dias
- `stale`: 0 ofertas em 30 dias, mas ao menos 1 em 90 dias
- `dead_retail`: 0 ofertas em 90 dias

Regras de negocio:

- `dead_retail` deve sair do ranking padrao;
- `stale` deve receber penalidade forte;
- ausencia de preco recente nao pode ser neutra;
- uma peca sem observacao recente deve carregar explicacao visivel na resposta.

### Fase 2 - Budget como custo total do PC

Alterar a semantica de `budget`:

- hoje: teto para `CPU + GPU`
- alvo novo: teto para build completa

Nova formula:

`cpu_gpu_budget = budget - platform_cost_estimate`

Onde `platform_cost_estimate` e calculado a partir de componentes auxiliares:

- `motherboard`
- `ram`
- `ssd`
- `psu`

Observacoes:

- nao precisa recomendar cada peca individual logo na primeira entrega;
- basta estimar uma plataforma minima plausivel para sustentar a dupla `CPU + GPU`;
- a estimativa deve depender de socket, geracao de memoria e consumo energetico.

### Fase 3 - Custo de plataforma por perfil

Criar um estimador de plataforma com heuristicas simples e auditaveis.

Exemplo de saida interna:

```json
{
  "platform_cost_estimate": 2450.0,
  "platform_breakdown": {
    "motherboard": 850.0,
    "ram": 650.0,
    "ssd": 500.0,
    "psu": 450.0
  }
}
```

Heuristicas minimas:

- `motherboard`: baseada em `socket`, `chipset`, `wifi` opcional
- `ram`: baseline por plataforma, ex. 32 GB para gaming principal
- `ssd`: baseline por capacidade, ex. 1 TB
- `psu`: baseada no consumo estimado da GPU e margem operacional

Com isso, AM4 + DDR4 passa a ser corretamente valorizado quando a plataforma AM5 encarece demais.

### Fase 4 - Score composto por dimensoes explicitas

Separar o score final em blocos:

- `performance_now`
- `value_now`
- `market_health`
- `longevity_usage`
- `longevity_upgrade`

Modelo sugerido:

```text
final_score =
  0.30 * performance_now +
  0.25 * value_now +
  0.20 * market_health +
  0.15 * longevity_usage +
  0.10 * longevity_upgrade
```

Os pesos podem variar por modo:

- `value`: aumenta peso de `value_now`
- `competitive`: aumenta peso de `performance_now`
- `hybrid`: mantem equilibrio
- `longevity`: aumenta peso de longevidade

### Fase 5 - Modo padrao e modos futuros

Manter compatibilidade com os `use_case` atuais, mas preparar um segundo eixo de recomendacao.

Sugestao:

- `use_case`: continua representando tipo de uso
- `strategy`: novo campo opcional para a estrategia de compra

Valores iniciais para `strategy`:

- `best_value_now`
- `balanced`
- `upgrade_path`

Se `strategy` vier ausente, usar `balanced`.

## Mudancas Tecnicas Sugeridas

### 1. Repositorio de ofertas

Expandir o `DailyOfferRepository` com agregacoes para series temporais por SKU.

Novos metodos sugeridos:

- `summarize_recent_market(entity_type, entity_id, days=90)`
- `summarize_market_batch(entity_type, entity_ids, days=90)`
- `list_recent_by_entity_types(entity_types, max_age_days=90)`

### 2. Camada de servico

Criar servicos novos:

- `MarketHealthService`
- `PlatformCostEstimator`
- `LongevityPolicy`

Responsabilidades:

- `MarketHealthService`: derivar atividade comercial e confianca de mercado
- `PlatformCostEstimator`: estimar custo auxiliar da build
- `LongevityPolicy`: pontuar uso duravel e potencial de upgrade

### 3. Score do match

Refatorar `MatchScoringPolicy` para:

- aceitar dados de mercado agregados;
- penalizar itens sem oferta recente;
- usar `total_build_cost` no filtro de `budget`;
- gerar breakdown completo no resultado final.

### 4. Schema da resposta

Expandir a resposta de `/matches` com transparencia:

```json
{
  "score": 82.4,
  "label": "forte",
  "pair_price": 4300.0,
  "platform_cost_estimate": 2300.0,
  "total_build_cost_estimate": 6600.0,
  "market_status": {
    "cpu": "active",
    "gpu": "stale"
  },
  "score_breakdown": {
    "performance_now": 84.0,
    "value_now": 80.0,
    "market_health": 58.0,
    "longevity_usage": 76.0,
    "longevity_upgrade": 62.0
  }
}
```

## Regras de Negocio Importantes

### Pecas sem oferta recente

Regra recomendada:

- sem oferta em 90 dias: excluir do ranking padrao;
- sem oferta em 30 dias: penalizar fortemente;
- sem oferta recente, mas com score tecnico alto: marcar como `legacy_high_performance`.

Isso evita sugerir como padrao pecas boas no papel, mas fora da realidade do varejo novo.

### AM4 e DDR4

O sistema nao deve tratar AM4 como automaticamente inferior.

Em vez disso:

- penalizar AM4 no eixo `longevity_upgrade`;
- preservar ou ate premiar AM4 em `value_now` e `market_fit` quando RAM/SSD/placas AM5 estiverem caros.

### RAM e SSD

Quando `RAM` e `SSD` subirem:

- builds DDR4 devem ganhar competitividade em custo total;
- plataformas que exigem DDR5 devem refletir esse aumento no `platform_cost_estimate`;
- recomendacoes devem responder ao mercado, nao apenas ao benchmark.

## Ordem Recomendada de Entrega

### Entrega 1

- adicionar `market_health` por SKU;
- excluir `dead_retail` do ranking padrao;
- penalizar `stale`;
- retornar status de mercado na resposta.

### Entrega 2

- reinterpretar `budget` como custo total;
- introduzir `platform_cost_estimate`;
- retornar `total_build_cost_estimate`.

### Entrega 3

- incorporar `ram`, `ssd`, `motherboard` e `psu` na estimativa;
- calibrar heuristicas por plataforma.

### Entrega 4

- criar score composto por dimensoes explicitas;
- introduzir `strategy`;
- ajustar explicacoes retornadas ao cliente.

## Testes Necessarios

### Unitarios

- peca `dead_retail` nao aparece no ranking padrao;
- peca `stale` recebe penalidade;
- ausencia de oferta reduz confianca de mercado;
- AM4 pode vencer AM5 quando plataforma estiver muito mais barata;
- aumento de DDR5 afeta `platform_cost_estimate`;
- `budget` total barra combinacoes boas de `CPU + GPU`, mas ruins de build completa.

### Integracao

- `/matches` passa a devolver `platform_cost_estimate`;
- `/matches` exclui GPUs fora de linha sem oferta recente;
- `/matches` reordena ranking quando precos de RAM/SSD mudam.

## Riscos

- heuristicas de plataforma podem ficar opacas se crescerem sem disciplina;
- excesso de penalizacao pode esconder oportunidades reais;
- dependencia de dados de Telegram exige monitoramento da cobertura por categoria;
- `RAM` e `SSD` podem ter matching mais ruidoso do que `CPU` e `GPU`.

## Mitigacoes

- manter regras simples e auditiveis nas primeiras entregas;
- expor `score_breakdown` na resposta;
- registrar status de mercado por item;
- versionar calibracoes de peso;
- medir cobertura de ofertas por categoria.

## Metricas de Sucesso

- reducao de itens sem oferta recente no topo do ranking;
- maior aderencia entre ranking e builds consideradas boas no mercado brasileiro;
- melhora na interpretacao do `budget` pelo usuario final;
- explicacoes mais claras sobre porque uma build foi recomendada.

## Proximo Passo Recomendado

Comecar pela Entrega 1.

Ela resolve o erro mais visivel hoje: pecas com score alto e mercado morto ou quase morto ainda aparecendo no topo.

Depois disso, implementar a reinterpretacao de `budget` como custo total do PC, que e a mudanca de maior impacto de produto.
