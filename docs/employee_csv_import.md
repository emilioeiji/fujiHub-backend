# Importação CSV de Funcionários (MT.csv)

Este guia descreve o fluxo seguro para validar e importar funcionários no `master.Employee`.

## Formato recomendado do arquivo

- Tipo: CSV
- Separador: vírgula
- Encoding: UTF-8 (UTF-8 BOM também aceito)
- Cabeçalhos japoneses do MT.csv são suportados

## Como exportar do Excel

1. Abra a planilha no Excel.
2. `Arquivo` -> `Salvar como`.
3. Escolha formato `CSV UTF-8 (delimitado por vírgulas)`.
4. Salve como `MT.csv`.

## Preview por linha de comando (sem alterar banco)

```bash
cd /workspace/backend
python manage.py preview_employee_csv /caminho/MT.csv
```

Opções:

```bash
python manage.py preview_employee_csv /caminho/MT.csv --update-empty --limit-warnings 20 --limit-errors 20
```

- `--update-empty`: permite que campos vazios no CSV limpem campos existentes.
- `--limit-warnings`: limite de warnings mostrados no relatório.
- `--limit-errors`: limite de erros mostrados no relatório.

## Interpretação do resultado

- `warning`: problema não crítico (ex.: referência de shift/process não encontrada).
  - Não bloqueia commit.
- `error`: problema crítico (ex.: `employee_id` vazio, nomes ausentes, data inválida).
  - Bloqueia commit.

Regras importantes:

- `update_empty=false` por padrão (campos vazios não apagam dados existentes).
- `employee_id` identifica create/update.
- Datas placeholder como `1900/01/07` são tratadas como vazias.

## Importação via tela web

1. Acesse `/employees`.
2. Use o bloco **Importar CSV**.
3. Selecione o arquivo.
4. Clique em **Preview**.
5. Revise `creates/updates/warnings/errors`.
6. Clique em **Confirmar importação** somente se `errors = 0`.
