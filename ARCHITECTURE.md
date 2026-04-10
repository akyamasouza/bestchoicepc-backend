# Arquitetura Desacoplada para Daily Offers e Enriquecimento

## Serviços Principais
- **telegram-sync-worker**: Busca mensagens do Telegram, cria candidatos temporários, publica evento "candidato_criado" na queue.
- **enricher-worker**: Consome eventos, enriquece candidatos com IA/OpenRouter, publica "candidato_enriquecido" ou "promovido".
- **api-service**: FastAPI para endpoints (ex.: trigger sync manual, consultar candidatos), recebe webhooks para eventos.

## Fluxo Event-Driven
1. Worker-sync roda diariamente (cron), busca Telegram, cria candidato, envia para queue.
2. Worker-enricher consome, chama IA, atualiza candidato, envia evento de sucesso/erro.
3. API expõe status e permite intervenção manual.

## Tecnologias
- **Message Queue**: Redis (simples, usar pub/sub ou listas).
- **Scheduler**: Cron no container ou Celery beat para jobs recorrentes.
- **Persistência**: MongoDB compartilhado entre containers.

## Benefícios (Pareto 80/20)
- Desacoplamento: Serviços independentes, escaláveis separadamente.
- Robustez: Falha em um não quebra outros (ex.: IA offline, sync continua).
- Automação: Pipelines CI/CD deployam containers automaticamente.