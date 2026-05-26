# Ambientes FujiHub

O FujiHub separa frontend, API e banco por ambiente para evitar gravações acidentais em produção.

## Tabela de ambientes

| Uso | URL/Config | Observação |
| --- | --- | --- |
| Web local | `http://localhost:5173` | Deve chamar API local por padrão |
| API local | `http://127.0.0.1:8000` | Django em `settings.dev` |
| Banco local | MySQL `db:3306`, database `django` | Devcontainer/docker compose |
| Mobile local | `EXPO_PUBLIC_API_URL=http://IP_DA_MAQUINA:8000` | Celular acessa API pela LAN |
| Web produção | `https://hub.emilioeiji.com.br` | React build servido pelo Apache |
| API produção | `https://api.emilioeiji.com.br` | Django/mod_wsgi |
| Banco produção | Definido no `.env` do servidor | Nunca usar por padrão em dev |

## Web local

Em desenvolvimento, se `VITE_API_URL` não estiver definido, o web usa:

```bash
http://127.0.0.1:8000
```

Comando recomendado:

```bash
cd /workspace/web
VITE_API_URL=http://127.0.0.1:8000 npm run dev -- --host 0.0.0.0
```

No console do navegador, em DEV, deve aparecer:

```text
FujiHub API URL: http://127.0.0.1:8000
```

## Backend local

```bash
cd /workspace/backend
python manage.py runserver 0.0.0.0:8000
```

O backend local deve usar:

```bash
DJANGO_SETTINGS_MODULE=fuji_backend.settings.dev
MYSQL_HOST=db
MYSQL_DATABASE=django
```

## Proteção contra banco de produção em dev

Em `settings.dev`, se `DEBUG=True` e o banco parecer produção, o Django bloqueia a inicialização.

Override apenas para operação intencional:

```bash
ALLOW_DEV_TO_USE_PROD_DB=true
```

Use isso somente para tarefa pontual e consciente.

## Produção web

O build de produção deve receber:

```bash
VITE_API_URL=https://api.emilioeiji.com.br
```

No deploy, isso vem de:

```bash
backend/deploy/deploy.env
```

## Mobile com API local

```bash
REACT_NATIVE_PACKAGER_HOSTNAME=192.168.0.140 \
EXPO_PUBLIC_API_URL=http://192.168.0.140:8000 \
npx expo start --host lan --clear
```

`REACT_NATIVE_PACKAGER_HOSTNAME` ajuda o celular a encontrar o Metro/Expo.
`EXPO_PUBLIC_API_URL` define para qual API o app envia requests.

## Mobile com API de produção

```bash
REACT_NATIVE_PACKAGER_HOSTNAME=192.168.0.140 \
EXPO_PUBLIC_API_URL=https://api.emilioeiji.com.br \
npx expo start --host lan --clear
```

## Como confirmar a API usada

Web local:
- abra o DevTools do navegador;
- confira a linha `FujiHub API URL: ...`;
- confira a aba Network.

Backend local:

```bash
cd /workspace/backend
python manage.py check
```

Mobile:
- confira o valor de `EXPO_PUBLIC_API_URL` usado no comando;
- não use `https://api.emilioeiji.com.br` se quiser testar local.
