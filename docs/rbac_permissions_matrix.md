# FujiHub RBAC - Matriz de Permissões

## 1) Perfis Operacionais

Perfis suportados no RBAC operacional:

- `kl` (KL / ﾘｰﾀﾞｰ)
- `gl` (GL / ｸﾞﾙｰﾌﾟﾘｰﾀﾞ)
- `supervisor` (Supervisor / ｽｰﾊﾟｰﾊﾞｲｻﾞ)
- `manager` (Manager / ﾏﾈｰｼﾞｬｰ)
- `senior_manager` (SeniorManager / ｼﾆｱﾏﾈｰｼﾞｬ)
- `responsavel` (Responsável)
- `trainer_master` (TrainerMaster / ﾚｰﾅｰﾏｽﾀ)
- `hr` (HR / Staff)
- `director` (Director)
- `vice_director` (ViceDirector)
- `viewer` (Viewer)
- `dashboard_tv` (DashboardTV)

## 2) Escopos

Escopo de acesso é aplicado por `UserOperationScope` e pode incluir:

- `department`
- `process`
- `shift`
- `line` (texto, quando aplicável)
- `area` (texto, quando aplicável)
- `global` (papéis globais)

### Regras gerais de escopo

- `director` e `vice_director`: acesso global.
- `hr`: acesso global para módulos administrativos previstos.
- Perfis operacionais (`kl`, `gl`, `supervisor`, `manager`, `senior_manager`, `responsavel`, `trainer_master`, `viewer`, `dashboard_tv`) dependem de escopo associado.
- `superuser` Django: acesso total (bypass de RBAC).

## 3) Matriz por Módulo

Legenda:

- `V`: visualizar
- `E`: editar
- `-`: sem acesso
- `Escopo`: `Global` ou `Associado` (department/process/shift/line/area)

| Perfil | Escala | Hikitsugui | Dashboard Presença | Obs. Administrativas | Settings Operacionais | Exportações | Templates | Histórico |
|---|---|---|---|---|---|---|---|---|
| KL | V (Associado), E: não | V/E (Associado) | V (Associado), detalhe conforme escopo | - | - | conforme tela/módulo permitido | - | V (Associado) |
| GL | V/E (Associado) | V/E (Associado) | V (Associado), detalhe conforme escopo | - | - | conforme escopo e tela | V/E (Associado) | V (Associado) |
| Supervisor | V/E (Associado) | V/E (Associado) | V (Associado) | V (Associado) | - | conforme escopo e tela | V/E (Associado) | V (Associado) |
| Manager | V/E (Associado) | V/E (Associado) | V (Associado) | V/E (Associado para notas) | - | conforme escopo e tela | V/E (Associado) | V (Associado) |
| SeniorManager | V/E (Associado multi-linha) | V/E (Associado multi-linha) | V (Associado multi-linha) | V (Associado) | leitura permitida | conforme escopo e tela | V/E (Associado) | V (Associado) |
| Responsavel | V (Associado amplo), E: não | V (Associado amplo), E: não | V (Associado amplo) | V (Associado) | leitura permitida | leitura/export conforme permitido | V (Associado), E: não | V (Associado) |
| TrainerMaster | V/E (Associado) | V/E (Associado) | V (Associado) | - | - | conforme escopo e tela | V/E (Associado) | V (Associado) |
| HR/Staff | V global em Escala; E de Escala: não por padrão | V (conforme regra atual) | V global | V/E global | V/E global | permitido para rotinas administrativas | gestão conforme regra atual | V |
| Director | V/E Global | V/E Global | V Global | V/E Global | V/E Global | Global | Global | Global |
| ViceDirector | V/E Global | V/E Global | V Global | V/E Global | V/E Global | Global | Global | Global |
| Viewer | V (Associado), E: não | V (Associado), E: não | V (Associado), sem ações de edição | - | - | leitura apenas | - | V (Associado) |
| DashboardTV | painel/dashboard conforme escopo, sem edição | - | V agregado (sem ações sensíveis de detalhe/edição) | - | - | - | - | - |

> Observação: algumas ações de exportação seguem permissões da tela/módulo e escopo efetivo aplicado no backend.

## 4) Regras por Perfil (resumo)

### KL (`kl`)
- Pode visualizar Escala no escopo associado.
- Não edita Escala por padrão.
- Pode operar Hikitsugui no escopo associado.
- Não acessa observações administrativas sensíveis por padrão.

### GL (`gl`)
- Edita Escala no escopo associado.
- Pode importar/sincronizar assignments e operar templates no escopo.
- Pode operar Hikitsugui no escopo associado.

### Supervisor (`supervisor`)
- Acesso gerencial de linha no escopo associado.
- Visualiza admin notes no escopo permitido.

### Manager (`manager`)
- Acesso gerencial de linha no escopo associado.
- Pode criar/editar observações administrativas no contexto permitido.

### SeniorManager (`senior_manager`)
- Acesso ampliado multi-linha por escopos associados.
- Pode leitura de settings operacionais e gestão operacional no escopo.

### Responsavel (`responsavel`)
- Visualização ampla por escopo associado.
- Sem ações decisórias/administrativas críticas (perfil readonly ampliado).

### TrainerMaster (`trainer_master`)
- Acesso operacional transversal no escopo associado.
- Sem privilégios globais administrativos por padrão.

### HR (`hr`)
- Acesso administrativo (presença, observações, settings).
- Leitura global em módulos administrativos previstos.

### Director / ViceDirector
- Escopo global com leitura e escrita.

### Viewer (`viewer`)
- Somente leitura no escopo associado.

### DashboardTV (`dashboard_tv`)
- Apenas visualização de dashboard/painel.
- Sem edição.

## 5) Regras Especiais

- KL pode estar cadastrado no master como relief/ririfu, mas no RBAC continua sendo `kl`.
- `responsavel` tem visualização ampla e sem permissões administrativas críticas.
- `dashboard_tv` não edita nada.
- `superuser` Django tem acesso total.
- Mapeamento temporário de papéis legados `accounts.Role`:
  - `admin` -> `director`
  - `escritorio` -> `hr`
  - `supervisor` -> `supervisor`
  - `gl` -> `gl`
  - `consulta` -> `viewer`

## 6) Onde Configurar no Sistema

Configuração de RBAC é feita no Django Admin, principalmente nos modelos:

- `OperationRole`
  - catálogo de papéis
  - flags (readonly, dashboard-only, global)
- `UserOperationProfile`
  - vínculo usuário -> papel principal
- `UserOperationScope`
  - escopos por usuário (department/process/shift/line/area)

Fluxo recomendado:

1. Criar/validar papel em `OperationRole`.
2. Associar usuário em `UserOperationProfile`.
3. Definir escopos em `UserOperationScope`.
4. Validar no endpoint de diagnóstico de permissões do usuário:
   - `GET /api/operations/me/permissions/`

## 7) Observações de Operação

- Frontend oculta/mostra ações conforme permissões, mas backend é a fonte final de autorização.
- Em caso de dúvida de acesso, conferir primeiro:
  - perfil ativo
  - escopos ativos
  - se usuário está usando fallback legado ou RBAC novo.
