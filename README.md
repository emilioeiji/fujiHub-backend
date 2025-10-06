# 📦 FujiHub Backend

Este é o **backend do FujiHub**, desenvolvido em **Django + Django REST Framework**, responsável por fornecer a API que integra o frontend (React/React Native) com a camada de dados e autenticação.

---

## 🚀 Tecnologias

- [Python 3.12+](https://www.python.org/)
- [Django 5](https://www.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [SimpleJWT](https://django-rest-framework-simplejwt.readthedocs.io/) para autenticação via tokens
- [django-cors-headers](https://github.com/adamchainz/django-cors-headers) para integração com o frontend

---

## ⚙️ Configuração do ambiente

### 1. Clone o repositório

```bash
git clone git@github.com:emilioeiji/fujiHub-web.git
cd fujiHub/backend
```

### 2. Crie e ative o virtualenv

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure variáveis de ambiente

Crie um arquivo `.env` na raiz do backend:

```env
SECRET_KEY=chave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

### 5. Execute as migrações

```bash
python manage.py migrate
```

### 6. Suba o servidor

```bash
python manage.py runserver
```

---

## 🔑 Autenticação

O backend utiliza **JWT (JSON Web Tokens)**.
Endpoints principais:

- `POST /api/token/` → gera `access` e `refresh`
- `POST /api/token/refresh/` → renova o `access`
- Endpoints protegidos exigem header:
  ```
  Authorization: Bearer <access_token>
  ```

---

## 📡 Integração com o Frontend

- Durante o desenvolvimento:
  - Backend: `http://127.0.0.1:8000`
  - Frontend (Vite): `http://127.0.0.1:5173`
- O CORS já está configurado para permitir chamadas do frontend.

---

## 🗂️ Estrutura de pastas

```
backend/
├── manage.py
├── backend/        # Configurações do projeto
├── app/            # Sua aplicação principal
├── requirements.txt
└── README.md
```

---

## 🧪 Testes

```bash
python manage.py test
```

---

## 📜 Licença

Este projeto é de uso interno do **FujiHub**.
