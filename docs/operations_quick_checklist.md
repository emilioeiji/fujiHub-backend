# FujiHub - Checklist Operacional de Plantão (Rápido)

## 1) Antes do deploy

- [ ] Backup MySQL
```bash
mysqldump -h <host> -u <user> -p --single-transaction <database> | gzip > fujihub_$(date +%F_%H%M).sql.gz
```

- [ ] Conferir `git status`
```bash
cd /caminho/backend
git status
cd /caminho/web
git status
```

- [ ] Confirmar branch correta
```bash
git branch --show-current
```

- [ ] Revisar migrations
```bash
cd /caminho/backend
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

---

## 2) Deploy

```bash
cd /caminho/backend
git pull
pip install -r requirements.txt
python manage.py migrate

cd /caminho/web
git pull
npm ci
npm run build

sudo systemctl restart apache2
```

---

## 3) Smoke test rápido

- [ ] Login no sistema
- [ ] Abrir Escala Operacional (`/operations/calendars`)
- [ ] Abrir Hikitsugui (`/operations/hikitsugui`)
- [ ] Abrir Dashboard de Presença (`/operations/attendance-dashboard`)
- [ ] Testar export/impressão básico (1 ação de cada)
- [ ] Se houver arquivo de cartão ponto, importar e validar divergências

API rápida:
```bash
curl -i https://<dominio>/api/operations/calendars/
curl -i https://<dominio>/api/operations/hikitsugui-reports/
curl -i https://<dominio>/api/operations/attendance-dashboard/
```

Cartão ponto pela tela:
- [ ] Abrir `/operations/attendance-dashboard`
- [ ] Ir ao painel `Cartão ponto x Escala`
- [ ] Clicar em `Importar cartão ponto`
- [ ] Selecionar arquivo `.csv` ou `.txt`
- [ ] Confirmar `CP932 / Shift_JIS` e o mês
- [ ] Clicar em `Importar arquivo`

Cartão ponto pelo terminal, se necessário:
```bash
cd /caminho/backend
python manage.py import_timecard_csv --file /caminho/arquivo.csv --encoding cp932 --month 2026-05
```

Validação rápida do cartão ponto:
- [ ] Abrir `/operations/attendance-dashboard`
- [ ] Conferir KPI `Divergências cartão ponto`
- [ ] Abrir painel `Cartão ponto x Escala`
- [ ] Filtrar por `Sem ponto`, `Atraso` e `Trabalhou na folga`
- [ ] Clicar em uma divergência e abrir o drawer do funcionário
- [ ] Conferir a seção `Cartão ponto` no drawer

---

## 4) Se der erro

### Logs Apache
```bash
sudo tail -n 200 /var/log/apache2/error.log
sudo tail -n 200 /var/log/apache2/access.log
sudo tail -f /var/log/apache2/error.log
```

### Check Django
```bash
cd /caminho/backend
python manage.py check
python manage.py migrate --check
```

### Restaurar backup
```bash
gunzip -c fujihub_YYYY-MM-DD_HHMM.sql.gz | mysql -h <host> -u <user> -p <database>
```

### Reverter commit (rápido)
```bash
cd /caminho/backend
git revert <commit_hash>

cd /caminho/web
git revert <commit_hash>
```

### Redeploy após correção
```bash
cd /caminho/backend
./deploy/deploy_all.sh safe
```
