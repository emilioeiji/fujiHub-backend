# FujiHub Production Validation Checklist (Etapa 12B)

Objetivo: validar funcionamento pós-deploy em produção antes de avançar módulos.

## 1) Pré-condições

- `git pull` executado em `/var/www/fujihub-api` e `/var/www/fujihub-web`
- Deploy concluído com `./deploy/deploy_all.sh safe`
- Banco e serviços online (MySQL + Apache)

## 2) Login e Permissões

- Login com usuário `admin`:
  - Acesso total esperado em `inventory`, `medical`, `operations` e `management`
- Login com usuário `escritorio`:
  - Escrita permitida onde aplicável; sem privilégios de superuser
- Login com usuário `supervisor`:
  - Escrita operacional limitada conforme regras de role
- Usuário autenticado sem role:
  - Leitura permitida quando previsto
  - Escrita indevida negada (`403`)
- Superuser:
  - Deve se comportar como `admin` nas permissões de API
- Idioma:
  - Alternar PT-BR / JA-JP no login e após login
  - Confirmar persistência e textos principais

## 3) Inventory (Uniformes)

- Cadastrar categoria de uniforme
- Cadastrar item com custo (`unit_cost`)
- Criar solicitação `purchase` sem `reason` (deve passar)
- Criar solicitação `donation` sem `reason` (deve falhar)
- Criar solicitação `donation` com `reason` (deve passar)
- Workflow:
  - `pending -> approved -> separated -> delivered`
  - `cancel` somente nas transições válidas
- Confirmar baixa de estoque na separação
- Confirmar `total_cost` por item e por solicitação

## 4) Medical (Atendimento Médico)

- Cadastrar `MedicalReason`, `SymptomType`, `MedicalDestination`
- Criar solicitação médica com sintomas
- Workflow:
  - `requested -> triaged -> in_progress -> completed`
  - `cancel` quando permitido
- Confirmar permissões por role:
  - `admin/escritorio/saude` para ações de workflow
  - leituras para autenticados conforme regra atual

## 5) Operations / Calendar

- Criar calendário mensal
- Importar funcionários do `master`
- Cadastrar posição operacional
- Cadastrar necessidade diária por posição/data
- Gerar escala automática (4x2/5x2)
- Editar célula manualmente
- Colar dados via paste (TSV/Excel)
- Validar parser de códigos compostos
- Validar códigos operacionais e cores
- Validar cálculos:
  - `所定` (regular)
  - `残業` (extra)
  - `過重` (sobrecarga)
- Validar impressão:
  - print view abre
  - `suppress_on_print` respeitado para categorias aplicáveis

## 6) Management

- Acesso `/management` com role permitida
- `accounts`:
  - listar perfil/role (se endpoint habilitado)
  - alterar role/language quando disponível
- `operations`:
  - editar `RotationGroupStyle`, `EmployeeVisualCategory`, `OperationalCode`, `AttendanceStatus`, `WorkTimeCode`, `OperationalPosition`
- `inventory`:
  - editar categorias/itens conforme permissões
- `medical`:
  - editar cadastros mestre
- Usuário sem permissão:
  - acesso negado em escrita

## 7) Deploy e Saúde de Ambiente

- `./deploy/deploy_all.sh safe` sem erro
- `python manage.py migrate --check` OK
- `python manage.py check` OK
- `python manage.py collectstatic --noinput` OK
- `npm run build` OK
- `apache2 reload` OK
- Sem erro crítico nos logs

## 8) Comandos Úteis de Diagnóstico

Backend/API:

```bash
curl -i https://SEU_DOMINIO/api/token/
curl -i https://SEU_DOMINIO/api/operations/calendars/
```

Frontend:

```bash
curl -I https://SEU_DOMINIO/
```

Logs Apache:

```bash
sudo tail -n 200 /var/log/apache2/error.log
sudo tail -n 200 /var/log/apache2/access.log
```

Saúde Django:

```bash
cd /var/www/fujihub-api
source venv/bin/activate
python manage.py check
python manage.py migrate --check
python manage.py makemigrations --check --dry-run
```

Status Git:

```bash
cd /var/www/fujihub-api && git status --short
cd /var/www/fujihub-web && git status --short
```

## 9) Registro de Resultado

- Resultado geral: `PASS` / `PASS COM RESSALVAS` / `FAIL`
- Bugs simples corrigidos: listar ID/descrição
- Pendências grandes: listar e classificar impacto
- Próxima ação recomendada:
  - corrigir pendências críticas
  - repetir checklist mínimo de regressão
