# FujiHub Backend

Este é o **backend do FujiHub**, desenvolvido em **Django + Django REST Framework**, responsável por fornecer a API que integra o frontend (React/React Native) com a camada de dados e autenticação.

---

## Tecnologias

- [Python 3.12+](https://www.python.org/)
- [Django 5](https://www.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [SimpleJWT](https://django-rest-framework-simplejwt.readthedocs.io/) para autenticação via tokens
- [django-cors-headers](https://github.com/adamchainz/django-cors-headers) para integração com o frontend

---

## Subindo o ambiente com Dev Container

Este projeto fica em um workspace com três pastas principais:

```text
/workspace
├── backend
├── web
├── mobile
└── .devcontainer
```

O jeito mais simples de preparar o ambiente é usando o Dev Container do VS Code.

1. Abra a pasta raiz do projeto no VS Code.
2. Rode o comando **Dev Containers: Reopen in Container**.
3. Aguarde o container terminar de subir.

O `.devcontainer/docker-compose.yml` sobe:

- `backend`: container Python/Node usado para rodar o Django.
- `mobile`: container Node usado para rodar o Expo.
- `db`: MySQL 8.3 usado pelo backend em desenvolvimento.

O backend usa MySQL por padrão. O SQLite legado em `backend/db.sqlite3` fica apenas como referência/migração local.

### Sem VS Code

Na raiz do workspace:

```bash
docker compose -f .devcontainer/docker-compose.yml up -d --build
```

---

## Rodando o backend

Antes de iniciar, confira as variáveis em `.env`. O repositório inclui `.env.example`
como referência e o arquivo `.env` local fica fora do Git.

O desenvolvimento usa `DJANGO_SETTINGS_MODULE=fuji_backend.settings.dev`.
Para produção, use `DJANGO_SETTINGS_MODULE=fuji_backend.settings.prod` com
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` e `CORS_ALLOWED_ORIGINS` definidos no ambiente.

Dentro do Dev Container, ou via `docker compose exec`, rode:

```bash
cd /workspace/backend
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Se estiver fora do Dev Container:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

O backend fica disponível em:

- `http://localhost:8000`
- `http://127.0.0.1:8000`

Para verificar se a configuração do Django está OK:

```bash
python manage.py check
```

### Banco de dados

No Dev Container, o Django usa o serviço MySQL do compose:

```text
MYSQL_HOST=db
MYSQL_PORT=3306
MYSQL_DATABASE=django
MYSQL_USER=django
MYSQL_PASSWORD=django
```

Para consultar temporariamente o SQLite legado, use:

```bash
DATABASE_ENGINE=sqlite python manage.py shell
```

---

## Autenticação

O backend utiliza **JWT (JSON Web Tokens)**.
Endpoints principais:

- `POST /api/token/` gera `access` e `refresh`
- `POST /api/token/refresh/` renova o `access`
- Endpoints protegidos exigem header:

```http
Authorization: Bearer <access_token>
```

---

## Integração com web e mobile

- Durante o desenvolvimento:
  - Backend: `http://127.0.0.1:8000`
  - Frontend (Vite): `http://127.0.0.1:5173`
- O CORS já está configurado para permitir chamadas do frontend.
- Para testar no celular físico, o mobile precisa chamar o IP da máquina na rede, por exemplo `http://192.168.0.10:8000`, em vez de `localhost`.

---

## Estrutura de pastas

```text
backend/
├── manage.py
├── fuji_backend/   # Configurações do projeto Django
├── core/
├── login/
├── master/
├── users/
├── db.sqlite3
├── requirements.txt
└── README.md
```

---

## Testes

```bash
python manage.py test
```

---

## Licença

Este projeto é de uso interno do **FujiHub**.
