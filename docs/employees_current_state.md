# Employees Current State (Etapa 13A)

Resumo do estado antes da evolução operacional:

## Models mapeados

- `master.Employee`:
  - Base principal consumida por calendário operacional e demais módulos.
  - Muitos campos administrativos já existentes.
  - Sem defaults operacionais explícitos suficientes para escala/importação.
- `master.Department`:
  - Estrutura de departamento usada em vínculos de funcionário e filtros.
- `Organization`:
  - Não há model ativo em `master` para organização operacional (nesta etapa, mantido como campo textual no funcionário para uso prático).
- `accounts.Role`:
  - Define perfil funcional (`admin`, `escritorio`, `supervisor`, `gl`, etc.).
- `accounts.UserProfile`:
  - Vincula usuário, role, departamento e idioma.

## API pré-etapa

- `master.EmployeeViewSet` sem permissões por role específicas e sem filtros robustos.
- Endpoints de referência (`departments`, `processes`, `shifts`, etc.) já disponíveis.
- Importação do calendário inferia padrões de forma simplificada sem priorizar defaults do próprio funcionário.

## Web pré-etapa

- Tela `/employees` funcional, mas com UX limitada para operação diária:
  - sem filtros operacionais robustos;
  - sem edição rápida focada em escala;
  - pouca visibilidade de status/categoria operacional.
