# Operations Time Calculation (10M)

## Objetivo desta etapa

Melhorar o calculo de jornada no calendario operacional sem transformar ainda em controle de ponto completo.

## Regras implementadas

- 4x2 day:
  - inicio padrao `08:30`
  - fim padrao `20:35`
  - intervalo padrao `65` minutos
  - planejado: `540` regular + `120` extra
- 4x2 night:
  - inicio padrao `20:30`
  - fim padrao `08:35`
  - atravessa meia-noite
  - intervalo padrao `65` minutos
  - planejado: `540` regular + `120` extra
- 5x2 (mantido neste MVP):
  - planejado: `480` regular + `180` extra

## Codigos especiais

- `sunday`, `holiday_work`, `sunday_teiji`, `holiday_work_teiji`:
  - planejado: `0` regular + `660` extra
- `vaccine`:
  - planejado: `0` regular + `0` extra
- `teiji`:
  - overtime planejado zerado
  - 4x2: `540` regular cap
  - 5x2: `480` regular cap

## Calculo com horario real

Quando `leave_time` (ou `end_time`) e informado:

1. calcula minutos brutos com base em `start_time`, `leave_time/end_time` e `crosses_midnight`
2. aplica desconto de intervalo simples:
   - < 4h: 0 min
   - >= 4h e < 6h: 20 min
   - >= 6h: ate `break_minutes` (padrao 65)
3. gera minutos liquidos
4. divide entre regular e extra conforme cap do padrao

## Campos preparados

`operations.CalendarDayCell`:

- `start_time`
- `end_time`
- `break_minutes`
- `crosses_midnight`
- `manual_time_override`
- `leave_time`
- `time_note`
- `scheduled_regular_minutes`
- `scheduled_overtime_minutes`
- `actual_work_minutes`
- `actual_overtime_minutes`

`operations.CalendarEmployeeAssignment`:

- `shift_type`: `day` | `night` | `flexible`

## Compatibilidade

- Celas antigas sem campos novos continuam funcionando.
- Defaults de horario sao aplicados automaticamente quando `manual_time_override=false`.
- Totalizadores por assignment (`所定`, `残業`, `過重`) continuam no endpoint.

## Limitações desta etapa

- Sem hora real de entrada vinda de relogio de ponto.
- Sem legislacao japonesa completa (noturno, DSR, regras fiscais etc.).
- Sem importacao de arquivo de ponto.

## Proxima evolucao (10N/10O)

- Importar batidas reais de ponto.
- Comparar planejado x realizado com motivo de divergencia.
- Regras japonesas completas de horas noturnas/feriados/sobrecarga.
