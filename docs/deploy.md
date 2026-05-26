# Deploy FujiHub

Este documento descreve o deploy robusto do FujiHub no servidor Ubuntu/Debian.

## Arquitetura Final de Domínios

- Web React: `https://hub.emilioeiji.com.br`
- API Django: `https://api.emilioeiji.com.br`

Importante:
- O domínio `hub.emilioeiji.com.br` serve apenas o frontend.
- A API não deve ser roteada por `hub`.
- Se `/api` for chamado no `hub`, pode retornar HTML do React, e isso é esperado nessa arquitetura.

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
BACKEND_BRANCH=master
WEB_BRANCH=master
BACKEND_SERVICE=fujihub-api
WEB_SERVER_SERVICE=apache2
WEB_BUILD_DIR=dist
WEB_PUBLISH_DIR=/var/www/fujihub-web/dist
VENV_DIR=/var/www/fujihub-api/venv
FORCE_STRATEGY=stash
VITE_API_URL=https://api.emilioeiji.com.br
```

Se o backend roda via Apache/mod_wsgi e não existe um serviço systemd separado para Gunicorn/uWSGI, deixe:

```bash
BACKEND_SERVICE=
WEB_SERVER_SERVICE=apache2
```

Nesse caso, o deploy backend não tenta reiniciar serviço próprio do Django. O reload do `apache2` acontece no deploy web e pode ser suficiente para o Apache/mod_wsgi recarregar a aplicação, dependendo da configuração do WSGI.

Para evitar warnings de assets apontando para `/var/www/web/dist/assets`, configure também o `.env` do backend:

```bash
WEB_DIST_DIR=/var/www/fujihub-web/dist
FRONTEND_ASSETS_DIR=/var/www/fujihub-web/dist/assets
```

Durante o deploy, os scripts também exportam esses valores automaticamente a partir de `WEB_PUBLISH_DIR` quando possível.

Para Apache (recomendado no ambiente atual):

```bash
WEB_SERVER_SERVICE=apache2
```

Para Nginx:

```bash
WEB_SERVER_SERVICE=nginx
```

Para descobrir os nomes reais dos serviços:

```bash
systemctl list-units --type=service | grep -E "apache|nginx|fujihub|gunicorn"
```

Para descobrir a branch real em cada repositório:

```bash
cd /var/www/fujihub-api
git branch --show-current

cd /var/www/fujihub-web
git branch --show-current
```

Use `master` ou `main` no `deploy.env`, conforme o resultado acima.

Se houver endpoints públicos para validação:

```bash
BACKEND_HEALTH_URL=https://api.seu-dominio.com/health/
WEB_HEALTH_URL=https://fujihub.seu-dominio.com/
```

Se não houver `/health/`, deixe `BACKEND_HEALTH_URL=` vazio. O script ainda executa `python manage.py check`.
Observação: `https://api.emilioeiji.com.br/api/token/` pode retornar `405` para GET/HEAD, então não é ideal como health check HTTP simples.

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
- recarrega o web server, Apache ou Nginx;
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
12. Reinicia o serviço systemd quando `BACKEND_SERVICE` estiver configurado.
13. Se `BACKEND_SERVICE` estiver vazio, mostra aviso e segue.

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
10. Recarrega o web server, Apache ou Nginx.
11. Executa health check se `WEB_HEALTH_URL` estiver definido.

## Troubleshooting

### API voltando HTML

Se uma chamada de API voltar HTML, normalmente o frontend está apontando para o domínio web.

Correto:
- `VITE_API_URL=https://api.emilioeiji.com.br`
- `EXPO_PUBLIC_API_URL=https://api.emilioeiji.com.br`

Incorreto:
- usar `https://hub.emilioeiji.com.br` como base da API.

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

Se o navegador continuar mostrando build antigo, verifique cache do browser/CDN e confirme se `WEB_PUBLISH_DIR` é o diretório servido pelo Apache/Nginx.

### VITE_API_URL Errado

Confira:

```bash
grep VITE_API_URL /var/www/fujihub-api/deploy/deploy.env
```

Deve apontar para a API real, não para `localhost`:

```bash
VITE_API_URL=https://hub.emilioeiji.com.br
```

Depois gere novo build:

```bash
./deploy/deploy_web.sh safe
```

### Apache Ou Nginx

Verifique:

```bash
systemctl list-units --type=service | grep -E "apache|nginx"
sudo systemctl status apache2 --no-pager
sudo journalctl -u apache2 -n 80 --no-pager
```

Para Nginx, use:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
sudo journalctl -u nginx -n 80 --no-pager
```

Recarregue o serviço configurado em `WEB_SERVER_SERVICE`:

```bash
sudo systemctl reload apache2
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
- executar `sudo systemctl reload apache2` ou `sudo systemctl reload nginx`, conforme `WEB_SERVER_SERVICE`.

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
export VITE_API_URL=https://hub.emilioeiji.com.br
npm run build
```

HTTP:

```bash
curl -I https://api.seu-dominio.com/health/
curl -I https://fujihub.seu-dominio.com/
```
