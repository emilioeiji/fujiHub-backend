# FujiHub - Runbook Operacional e Técnico Pós-Deploy

Este documento cobre operação diária e suporte pós-deploy do FujiHub, com foco em:
1. Deploy e rollback
2. Backup MySQL
3. Migrações
4. Logs Apache
5. Smoke tests
6. Uso da Escala Operacional
7. Uso do Hikitsugui
8. Uso do Dashboard de Presença
9. Permissões atuais e melhorias sugeridas

---

## 1) Deploy e Rollback

### 1.1 Deploy padrão (safe)
No servidor (repositório backend):

```bash
cd /caminho/backend
./deploy/deploy_all.sh safe
```

Comportamento esperado:
- valida worktree
- atualiza backend e web
- instala dependências
- executa migrate
- gera build web
- recarrega serviço web (Apache)

### 1.2 Deploy forçado (force)
Usar somente quando necessário:

```bash
./deploy/deploy_all.sh force
```

### 1.3 Rollback rápido
Estratégia recomendada:
1. Identificar último commit estável (`git log --oneline`).
2. Voltar backend e web para esse commit.
3. Reexecutar deploy em modo `safe`.

Exemplo (não destrutivo):

```bash
cd /caminho/backend
git checkout <commit_estavel>
cd /caminho/web
git checkout <commit_estavel>
cd /caminho/backend
./deploy/deploy_all.sh safe
```

Observação:
- Evitar rollback de schema sem plano (migrations reversas podem causar perda de dados em alguns cenários).

---

## 2) Backup MySQL

### 2.1 Backup lógico completo

```bash
mysqldump -h <host> -u <user> -p --single-transaction --routines --triggers <database> > fujihub_$(date +%F_%H%M).sql
```

### 2.2 Backup compactado

```bash
mysqldump -h <host> -u <user> -p --single-transaction <database> | gzip > fujihub_$(date +%F_%H%M).sql.gz
```

### 2.3 Restore

```bash
mysql -h <host> -u <user> -p <database> < fujihub_YYYY-MM-DD_HHMM.sql
```

### 2.4 Política mínima sugerida
- diário: últimos 7 dias
- semanal: últimas 4 semanas
- mensal: últimos 6-12 meses
- armazenar cópia fora do servidor principal

---

## 3) Migrações

### 3.1 Antes do deploy

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

### 3.2 Aplicar migrações

```bash
python manage.py migrate
```

### 3.3 Verificar migrações pendentes

```bash
python manage.py migrate --check
```

### 3.4 Boas práticas
- nunca editar migration já aplicada em produção
- criar migration nova para ajustes
- validar em staging/homologação antes de produção

---

## 4) Logs Apache

### 4.1 Caminhos comuns

```bash
/var/log/apache2/error.log
/var/log/apache2/access.log
```

### 4.2 Comandos úteis

```bash
sudo tail -n 200 /var/log/apache2/error.log
sudo tail -n 200 /var/log/apache2/access.log
sudo tail -f /var/log/apache2/error.log
```

### 4.3 Sinais de atenção
- 500 recorrente em `/api/operations/...`
- timeout de WSGI
- erro de permissão em arquivos estáticos
- falha de conexão com MySQL

---

## 5) Smoke Tests Pós-Deploy

### 5.1 Saúde geral

```bash
python manage.py check
python manage.py migrate --check
```

### 5.2 API mínima

```bash
curl -i https://<dominio>/api/token/
curl -i https://<dominio>/api/operations/calendars/
curl -i https://<dominio>/api/operations/hikitsugui-reports/
curl -i https://<dominio>/api/operations/attendance-dashboard/
```

### 5.3 Frontend mínimo
- login com usuário real
- abrir Escala Operacional
- abrir Hikitsugui
- abrir Dashboard de Presença
- validar ausência de erro visual/bloqueio

---

## 6) Uso da Escala Operacional (resumo)

Rota principal:
- `/operations/calendars/:id/grid`

Fluxo operacional típico:
1. abrir calendário do mês
2. importar funcionários compatíveis
3. ajustar linhas e assignments
4. preencher células (inline, quick apply, range, paste)
5. validar totais/consistência
6. exportar Excel e/ou imprimir PDF

Recursos já disponíveis:
- edição inline
- range e fill handle
- copy/paste
- undo/redo de sessão
- 4x2 e presets
- duplicar mês e gerar próximo
- templates
- histórico de alterações

---

## 7) Uso do Hikitsugui (resumo)

Rota principal:
- `/operations/hikitsugui`

Fluxo operacional típico:
1. aplicar filtro por período/turno/processo
2. registrar passagem rápida ou completa
3. classificar por categoria/prioridade
4. atualizar status (aberto, andamento, pendente, resolvido)
5. acompanhar pendências por turno
6. imprimir/PDF quando necessário

Dica operacional:
- usar presets de filtro (`Hoje`, `Ontem`, `Últimos 7 dias`, `Pendentes`, `Críticos`) para triagem rápida.

---

## 8) Uso do Dashboard de Presença (resumo)

Rota principal:
- `/operations/attendance-dashboard`

O que acompanhar:
- KPIs de presença/falta/atraso/HE
- ranking de faltas e atrasos
- ranking de horas extras
- alertas de risco (kajuuroudou)

Visão individual:
- clicar no funcionário abre drawer lateral
- mostra histórico diário, alertas e observações administrativas
- permite imprimir relatório individual
- permite exportar CSV compatível com Excel

Limites ativos:
- exibidos no topo
- configuráveis via `OperationsSettings`

---

## 9) Permissões Atuais e Pontos de Melhoria

### 9.1 Estado atual (resumo)
- `OperationsMasterDataPermission`:
  - leitura: autenticado
  - escrita: papéis `admin`, `escritorio`
- `OperationsCalendarPermission`:
  - leitura: autenticado
  - escrita: `admin`, `escritorio`, `supervisor`, `gl`

Impacto prático:
- configurações de limites (`/api/operations/settings/current/`) seguem permissão de master data
- observações administrativas seguem permissão de calendário para criação/edição

### 9.2 Melhorias recomendadas
1. Separar permissão de observação administrativa
- permitir criação para `supervisor/gl`
- restringir edição de observações críticas

2. Auditoria reforçada
- trilha explícita de edição por campo em observações administrativas

3. Escopo por departamento/processo
- garantir que usuário só altere dados do seu escopo

4. Perfis finos
- diferenciar perfil “consulta gerencial” de “operação diária”

---

## Anexo A - Endpoints Operacionais Relevantes

- Escala:
  - `GET /api/operations/calendars/`
  - `GET /api/operations/calendars/{id}/assignments/`
  - `GET /api/operations/calendars/{id}/cells/`

- Hikitsugui:
  - `GET /api/operations/hikitsugui-reports/`
  - `POST /api/operations/hikitsugui-reports/`

- Presença:
  - `GET /api/operations/attendance-dashboard/`
  - `GET /api/operations/attendance-dashboard/employees/{employee_id}/`
  - `GET/PATCH /api/operations/settings/current/`
  - `GET/POST/PATCH /api/operations/employee-admin-notes/`

- Produção (oculto da navegação, mas ativo na API):
  - `GET /api/operations/production-snapshots/dashboard/`

---

## Anexo B - Checklist rápido de incidente

1. Confirmar erro no frontend (print + horário + usuário)
2. Validar `error.log` Apache
3. Reproduzir endpoint via `curl`
4. Checar status de migração (`migrate --check`)
5. Verificar conexão MySQL
6. Aplicar correção mínima e revalidar smoke tests

