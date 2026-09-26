# Structural PA levels: forensic reconstruction

Статус: **forensic audit only**. Этот каталог не строит новые уровни, не восстанавливает значения отсутствующего `structural_levels.csv` и не является входом Stage 2I.

## Главный вывод

В истории репозитория восстановлены **тринадцать distinct исполняемых методологий** построения price-action levels / boundaries, включая смежные impulse/break/range методы. При этом **точный генератор старого `structural_levels.csv` не найден**: самого файла, manifest/checksum, builder-а и точных строк категорий из старого экспорта в доступных project/research directories и Git history нет.

Следовательно:

- методики Pine и Python можно воспроизвести по версиям;
- причинность большинства вариантов можно классифицировать однозначно;
- старые категории нельзя автоматически связать с одной конкретной версией;
- старый CSV нельзя считать authoritative или безопасно продолжать использовать без внешнего provenance.

## Восстановленные семейства

1. Legacy Range SFP: прямые D/W/M wick levels и локальные pivots/fresh swings.
2. Range SFP v0.4.x: candidate → promoted relevant reaction level.
3. Levels-only: HTF pivots + закрытые D/W/M body levels.
4. Promoted levels-only: multi-timeframe pivot с move-away gate; D/W/M bodies без gate в v0.3.
5. Rebound candidate engine: pivot → первое подтверждённое удаление цены.
6. Structure taxonomy: Entry / Internal / Watch / Anchor, включая phase, lock и cluster variants.
7. Realtime extrema / impulse-into family.
8. HTF confluence/readiness и broken-support/resistance strategy.
9. Standalone closed D/W/M body levels.
10. Opposite-body D/W/M junction levels with origin projection.
11. Global/local pivot impulses + Fibonacci-derived levels.
12. Major-swing candidates + break-from-leading-swing levels.
13. Python causal 4H dynamic range boundaries (rolling и regression channels).

Дополнительно найден ранее сформулированный fallback `minimal_confirmed_1H_4H_N3` только в старом task contract, без найденного implementation/output.

## Что считать causal

Наличие `lookahead_off` недостаточно. Для pivot-методик:

`event_time < pivot_confirmation_time <= available_from`

Если уровень дополнительно ждёт move-away, phase reset или anchor move, `available_from` наступает ещё позже. Рисование линии/label назад к pivot origin не делает уровень известным в прошлом.

Краткая классификация:

- **causal at bar close:** closed D/W/M levels; realtime extrema family; Python 4H ranges с history, исключающей текущий бар;
- **delayed-causal:** все confirmed-pivot families, promotion/rebound, phase/anchor;
- **not reproducibly causal at OHLC close:** intrabar 1m entry trigger без сохранённого tick path;
- **retrospective:** Python leg/event relationships, использующие завершённые macro legs или parent fractions.

Подробности: [methodology_versions.md](methodology_versions.md) и [causality_audit.md](causality_audit.md).

## Старые категории

Категории `internal_support_resistance`, `monthly_high_low` и `old_macro_impulse_low` не найдены буквально ни в коде, ни в Git history. `daily_high_low` и `weekly_high_low` встречаются только как смысловые аналоги ранее заданных D/W high-low outputs; это не доказывает происхождение конкретных строк отсутствующего CSV.

Подробности и confidence: [old_structural_levels_mapping.md](old_structural_levels_mapping.md).

## Итоговая рекомендация

**Нет, старую методику не удалось восстановить достаточно точно, чтобы принять решение о дальнейшем использовании именно старого `structural_levels.csv`.** Исполняемые методики восстановлены достаточно точно для отдельного будущего controlled comparison, но связь старых строк с конкретным builder/version остаётся unresolved. До появления CSV + manifest, builder path/commit или независимого row-level provenance старый файл следует считать непроверяемым legacy artifact.

## QA

- обязательные Pine/Python sources проинвентаризированы;
- Git lineage и содержательные diffs проверены;
- поиск старого CSV, builder-а и exact category strings выполнен в project/research directories и Git history;
- causal availability отделена от визуально backdated event time;
- derived/inferred утверждения явно отделены от verified evidence;
- новые levels/datasets/calculations не создавались.
