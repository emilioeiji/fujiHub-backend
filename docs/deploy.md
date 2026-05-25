# Deploy FujiHub

Este documento descreve o deploy robusto do FujiHub no servidor Ubuntu/Debian.

Os scripts ficam dentro do repositório backend para permitir este fluxo no servidor:

```bash
cd /var/www/fujihub-api
git pull
./deploy/deploy_all.sh safe
```

ou, quando houver alterações locais conhecidas:

```bash
./deploy/deploy_all.sh force
```

## Estrutura Esperada

```bash
/var/www/fujihub-api
/var/www/fujihub-web
```

O backend e o web são repositórios separados. Os scripts ficam no backend, mas atualizam os dois diretórios usando as variáveis de `deploy.env`.

## Primeira Configuração

No servidor:

```bash
cd /var/www/fujihub-api
cp deploy/deploy.env.example deploy/deploy.env
nano deploy/deploy.env
chmod +x deploy/*.sh
```

Configure pelo menos:

```bash
API_DIR=/var/www/fujihub-api
WEB_DIR=/var/www/fujihub-web
BACKEND_SERVICE=fujihub-api
NGINX_SERVICE=nginx
WEB_BUILD_DIR=dist
WEB_PUBLISH_DIR=/var/www/fujihub-web/dist
VENV_DIR=/var/www/fujihub-api/venv
FORCE_STRATEGY=stash
VITE_API_URL=https://api.seu-dominio.com
```

Se houver endpoints públicos para validação:

```bash
BACKEND_HEALTH_URL=https://api.seu-dominio.com/health/
WEB_HEALTH_URL=https://fujihub.seu-dominio.com/
```

Se não houver `/health/`, deixe `BACKEND_HEALTH_URL=` vazio. O script ainda executa `python manage.py check`.

## Deploy Seguro

Use no deploy normal:

```bash
cd /var/www/fujihub-api
git pull
./deploy/deploy_all.sh safe
```

O modo `safe`:

- aborta se backend ou web tiver alterações locais;
- não apaga nada;
- exige branch correta;
- executa `git fetch` e `git pull --ff-only`;
- roda migrations;
- executa `collectstatic`;
- faz build do frontend;
- recarrega nginx;
- reinicia o serviço backend.

## Deploy Forçado

Use quando o servidor tiver alterações locais e você quiser seguir mesmo assim:

```bash
./deploy/deploy_all.sh force
```

Por padrão:

```bash
FORCE_STRATEGY=stash
```

Isso faz `git stash push -u` antes do pull, preservando mudanças locais.

Para descartar alterações locais:

```bash
FORCE_STRATEGY=reset
```

Com `reset`, o script executa:

```bash
git reset --hard HEAD
git clean -fd
```

Use `reset` apenas quando tiver certeza de que as alterações locais não precisam ser preservadas.

## Deploy Apenas Backend

```bash
cd /var/www/fujihub-api
./deploy/deploy_backend.sh safe
```

Etapas executadas:

1. Carrega `deploy/deploy.env`.
2. Entra em `API_DIR`.
3. Verifica branch atual.
4. Trata alterações locais conforme `safe` ou `force`.
5. Executa `git fetch`.
6. Executa `git pull --ff-only`.
7. Ativa o virtualenv.
8. Instala dependências Python.
9. Executa migrations.
10. Executa `collectstatic`.
11. Executa `python manage.py check`.
12. Reinicia o serviço systemd.
13. Mostra status e logs recentes.

## Deploy Apenas Web

```bash
cd /var/www/fujihub-api
./deploy/deploy_web.sh safe
```

Etapas executadas:

1. Carrega `deploy/deploy.env`.
2. Entra em `WEB_DIR`.
3. Trata alterações locais.
4. Executa `git fetch`.
5. Executa `git pull --ff-only`.
6. Valida `VITE_API_URL`.
7. Executa `npm ci` se houver `package-lock.json`; senão `npm install`.
8. Executa `npm run build`.
9. Publica `dist` em `WEB_PUBLISH_DIR`, se for diferente.
10. Recarrega nginx.
11. Executa health check se `WEB_HEALTH_URL` estiver definido.

## Troubleshooting

### Git Pull Bloqueado

Erro comum:

```text
error: Your local changes to the following files would be overwritten by merge
```

Diagnóstico:

```bash
cd /var/www/fujihub-api
git status --short

cd /var/www/fujihub-web
git status --short
```

Opções:

```bash
./deploy/deploy_all.sh safe
```

Vai abortar sem apagar nada.

```bash
./deploy/deploy_all.sh force
```

Com `FORCE_STRATEGY=stash`, preserva alterações em stash.

### Migration Faltando

```bash
cd /var/www/fujihub-api
source venv/bin/activate
python manage.py showmigrations --plan
python manage.py migrate --check
python manage.py migrate
sudo systemctl restart fujihub-api
```

### Static Files

Backend:

```bash
cd /var/www/fujihub-api
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart fujihub-api
```

Frontend:

```bash
cd /var/www/fujihub-api
./deploy/deploy_web.sh safe
```

Se o navegador continuar mostrando build antigo, verifique cache do browser/CDN e confirme se `WEB_PUBLISH_DIR` é o diretório servido pelo nginx.

### VITE_API_URL Errado

Confira:

```bash
grep VITE_API_URL /var/www/fujihub-api/deploy/deploy.env
```

Deve apontar para a API real, não para `localhost`:

```bash
VITE_API_URL=https://api.seu-dominio.com
```

Depois gere novo build:

```bash
./deploy/deploy_web.sh safe
```

### Nginx

Verifique:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
sudo journalctl -u nginx -n 80 --no-pager
```

Recarregue:

```bash
sudo systemctl reload nginx
```

### Systemd Backend

Verifique:

```bash
sudo systemctl status fujihub-api --no-pager
sudo journalctl -u fujihub-api -n 120 --no-pager
```

Problemas comuns:

- `deploy.env` com serviço errado.
- `.env` do Django ausente.
- `DJANGO_SETTINGS_MODULE` errado.
- MySQL indisponível.
- Migration pendente.
- Dependência Python faltando.

### Permissões De Arquivo

Se o deploy falhar por permissão:

```bash
ls -la /var/www/fujihub-api
ls -la /var/www/fujihub-web
```

Confirme que o usuário que roda deploy consegue:

- ler os repositórios;
- escrever no diretório de build/publicação;
- executar `sudo systemctl restart fujihub-api`;
- executar `sudo systemctl reload nginx`.

Para systemd sem senha, configure sudoers com cuidado para os comandos específicos.

## Validações Manuais

Backend:

```bash
cd /var/www/fujihub-api
source venv/bin/activate
python manage.py check
python manage.py migrate --check
```

Web:

```bash
cd /var/www/fujihub-web
export VITE_API_URL=https://api.seu-dominio.com
npm run build
```

HTTP:

```bash
curl -I https://api.seu-dominio.com/health/
curl -I https://fujihub.seu-dominio.com/
```
