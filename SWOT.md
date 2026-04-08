# Analise SWOT — BestChoice PC Backend

## Contexto

Backend em FastAPI + MongoDB que cataloga componentes de hardware (CPU, GPU, SSD, RAM, Motherboard, PSU), monitora ofertas de canais do Telegram em tempo real e sugere combinacoes ideais de CPU+GPU com base em perfil de uso, resolucao e orcamento.

---

## Forcas (Strengths)

### Arquitetura limpa e organizada

- Estrutura bem separada por responsabilidade: `routes/`, `services/`, `repositories/`, `schemas/`, `scripts/`, `core/`.
- Uso do **Strategy Pattern** nos repositories (`PagedQueryStrategy`, `CandidateQueryStrategy`, `RankingQueryStrategy`), evitando repeticao de codigo de query/paginacao.
- Injecao de dependencias via `Depends()` do FastAPI, facilitando testes unitarios.

### Motor de matching sofisticado

- `MatchService` implementa scoring multi-criterio ponderado: equilibrio CPU/GPU, fit por resolucao, custo-beneficio, score de mercado (historico de precos), VRAM adequada.
- Pesos diferenciados por **use_case** (`competitive`, `aaa`, `hybrid`, `value`) e **resolucao** (`1080p`, `1440p`, `4k`), refletindo perfis reais de uso.
- Sistema de justificativas (reasons) explicado ao usuario final em linguagem natural.
- Suporte a reaproveitamento de pecas existentes (`owned_cpu_id`, `owned_gpu_id`).

### Pipeline de ingestao de ofertas

- **Duas vias de ingestao**: sync sob demanda (`DailyOfferSyncService`) + listener em tempo real (`telegram_listener.py` via Telethon push events).
- `EntityMatcher` com tokenizacao inteligente que separa sufixos de modelo (`4070 super` → `4070`, `super`), filtra stopwords e valida discriminadores conflitantes.
- `TelegramOfferParser` extrai preco, parcelas, loja, URL, historico (menor 90 dias, mediana) com normalizacao BRL e aliases de lojas.
- Repository com `upsert`Atomic + indices compostos para evitar duplicatas.

### Testing

- Cobertura de testes ampla: 31 arquivos de teste cobrindo todas as entidades, services, parsers, routes, seed scripts e ranking.
- Uso de `conftest.py` com fixtures reutilizaveis.

### Catelo de dados

- Dados de benchmark reais importados de fontes externas (TechPowerup, Tom's Hardware).
- Sistema de ranking percentile para CPUs e GPUs com tiers de performance.

---

## Fraquezas (Weaknesses)

### Falta de autenticacao e autorizacao

- Nenhuma middleware de auth (API keys, JWT, OAuth). Qualquer cliente externo pode acessar todas as rotas.
- CORS configurado com `allow_origins=["*"]` — aceita requisiçoes de qualquer origem, o que e inseguro para producao.

### Acoplamento direto ao MongoDB

- Repositories recebem `Collection` do PyMongo diretamente em vez de uma interface abstrata. Trocar de banco (Postgres, SQLite) exigiria reescrita em todas as camadas.
- Database module usa `lru_cache` como singleton do `MongoClient` — funcional, mas nao segue o padrao de lifecycle de conexao recomendado (start/end events).

### `MatchService` com complexidade crescent

- 650+ linhas com muitos magic numbers (pesos, thresholds, ranges de fit). Embora bem comentados, a manutencao de todas essas constantss e fragil — uma alteracao em `_FINAL_SCORE_WEIGHTS` pode impactar resultados de forma nao intuitiva.
- O loop nested `for cpu in available_cpus: for gpu in available_gpus` tem complexidade **O(n*m)**, que pode degradar conforme o catalogo cresce.

### Validacao e tratamento de erros

- Rotas nao possuem tratamento global de excecoes (sem `@app.exception_handler`). Errors nao mapeados retornam 500 generico.
- `MatchService._normalize_use_case` e `_normalize_resolution` com fallbacks silenciosos (`"value"` e `"1080p"`) — inputs invalidos nao sao rejeitados, mascarados como defaults.
- `EntityMatcher` nao lida com GPUs que nao tem variantes de sufixo (ex: `RTX 4060` sem `Ti` ou `Super`) de forma potencialmente muito restritiva.

### Data/seed pipeline manual

- Scripts de seed (`seed_cpus.py`, `seed_gpus.py`, etc.) sao executados manualmente via CLI. Nao ha pipeline automatizado de atualizacao do catalogo de hardware.
- Scripts de build para SSDs, RAMs, PSUs, Motherboards parecem ser one-off — nao ha indicacao de automacao continua.

### Sem logging estruturado

- `main.py` nao configura logging da aplicacao. O listenerTelegram tem logging basico, mas a API em si nao loga requests, latencia, ou errors de forma estruturada.

### Sem rate limiting ou throttling

- Nenhuma protecao contra abuso nas rotas da API. Um cliente pode fazer milhoes de requests no endpoint `/matches` sem qualquer limitacao.

---

## Oportunidades (Opportunities)

### Expansao de entidades

- Adicionar monitores, gabinetes, coolers, water coolers e perifercos ao catalogo, ampliando o escopo de matches para builds completas.

### Integracao com mais fontes de ofertas

- Conectar a APIs de afiliados (Kabum, Amazon, Pichau, Terabyte) para alem do Telegram, aumentando o volume de ofertas e a qualidade dos dados de historico de precos.

### Cache com Redis

- Implementar cache de respostas para rotas de listagem (CPUs, GPUs, ofertas do dia) e matches, reduzindo carga no MongoDB e diminuindo latencia.

### Sistema de usuarios e favoritos

- Autenticacao permitiriam salvar configs de build, historico de matches, alertas de preco e notificacoes quando uma oferta desejada aparecer.

### Pipeline de CI/CD

- GitHub Actions para rodar testes automaticamente em PRs, linting (ruff, mypy), e deploy automatizado.

### Documentacao da API

- O FastAPI ja gera Swagger automaticamente (`/docs`), mas adicionar exemplos de request/response nos schemas melhoraria a experiencia de consumo da API pelo frontend.

### ML para previsao de precos

- O historico de 90 dias armazenado em `DailyOffer` pode alimentar um modelo simples de previsao, sugerindo o melhor momento para comprar.

### Internacionalizacao

- Suporte a ofertas em dolares/euros, conversao automatica de moeda, e catalogo expandido para mercados internacionais.

---

## Ameacas (Threats)

### Dependencia critica do Telegram

- Toda a ingestao de ofertas depende de canais nao-oficiais do Telegram se esses canais forem desativados, mudarem de formato ou o Telegram restringir acesso via API, o pipeline de ofertas para completamente.
- A Telethon requer credenciais de API do Telegram que podem ser revogadas ou ter rate limits impostos.

### Mudancas no formato das mensagens

- O `TelegramOfferParser` usa regex hardcoded para extrair dados. Se o formato das postagens do canal mudar (ex: nova estrutura de texto, sem "Loja:", sem "em X parcelas"), o parser falha silenciosamente ou gera dados incorretos.

### Precos desatualizados

- Ofertas sao snapshot de um momento. Se o sync nao rodar frequentemente ou o listener cair, o frontend pode exibir precos que ja mudaram, gerando frustracao no usuario e perda de confianca.

### Escalabilidade do MongoDB

- Conforme o catalogo e historico de ofertas crescsem, queries nao otimizadas podem degradar. Indices compostos estao presentes, mas consultas de texto e agregacoes complexas podem exigir optimizacoes adicionais.

### Concorrentes diretos

- Ferramentas como **Zoom**, **Buscape**, e **Pelando** ja fazem monitoramento de precos com escala e confiabilidade superiores. Se a proposta de valor (recomendacao de combo CPU+GPU inteligente) nao for claramente diferenciada, a adocao pode ser lenta.

### Legislacao e LGPD

- Se o sistema comecar a coletar dados de usuarios (contas, favoritos, historico), precisara estar em conformidade com a LGPD, exigindo politicas de privacidade, consentimento e mecanismos de exclusao de dados.

---

## Resumo Visual

| | Positivo | Negativo |
|---|---|---|
| **Interno** | **Forcas**: Arquitetura limpa, motor de scoring multi-criterio, ingestao real-time, testes abrangentes | **Fraquezas**: Sem auth, sem rate limit, complexidade acumulada no MatchService, seeds manuais, sem logging estruturado |
| **Externo** | **Oportunidades**: Mais entidades, cache Redis, ML de precos, CI/CD, APIs de afiliados, sistema de usuarios | **Ameacas**: Dependencia do Telegram, formatos de mensagem volateis, precos desatualizados, concorrentes consolidados |
