# План исследования структуры после первичной макроразметки

## Текущее состояние знания

На текущем этапе у нас есть только:
- подтверждённые точки макроструктуры `A, B, C, D, ...`;
- исторические отрезки движения цены между соседними макроточками `A→B`, `B→C`, `C→D`, ...;
- историческая разметка того, какие из этих macro segments относятся к макроимпульсному и макрокоррекционному движению.

У нас **пока нет доказанного понятия `parent leg`, `child leg` или внутренней иерархии движений**. Эти понятия нельзя использовать как исходную истину. Они могут появиться позже только как результат исследования.

Главная задача первого этапа: понять, чем объективно отличается поведение цены и свечей внутри известных макроимпульсных и макрокоррекционных segments, и проверить, воспроизводятся ли найденные признаки на меньших масштабах.

## 0. Подготовить extraction tool

До основного исследования нужен воспроизводимый инструмент извлечения выборок из итогового датасета.

Он должен позволять выбирать:
- macro segment ID и его границы A→B;
- исторический macro movement class из утверждённой макроразметки;
- направление движения;
- calculation resolution;
- фазу внутри macro segment по относительному времени и/или относительному ценовому прогрессу;
- необходимые objective feature-поля;
- период рынка / regime context, если он уже определён внешней утверждённой макроразметкой.

Обязательные требования:
- одинаковый запрос даёт воспроизводимый результат;
- сохраняются фильтры и определение выборки;
- tool не решает сам, что является хорошим сигналом;
- исследовательские пороги не вшиваются заранее;
- каждый запрос соответствует конкретной гипотезе;
- сохраняются macro segment ID, A/B anchors и временные границы для проверки на графике;
- исключается look-ahead для causal features;
- retrospective macro labels остаются research labels и не становятся live features.

## 1. Primary macro-signature study: 1D / 12H / 4H

Для каждого известного macro segment A→B рассчитать одинаковый набор objective movement features на трёх основных candle resolutions:
- `1D`;
- `12H`;
- `4H`.

Это три параллельных представления **одного и того же macro segment**, а не три разные истинные структуры рынка.

На каждом resolution считать как минимум:
- range overlap и body overlap между соседними свечами;
- overlap Jaccard / overlap shares;
- penetration / extension;
- close-path и log close-path;
- path efficiency;
- counter-direction path;
- alternation;
- скорость и изменение скорости;
- обновление экстремумов;
- candle geometry: body/wick shares;
- volatility / ATR-normalized measures;
- volume/activity features, когда источник и coverage позволяют корректный расчёт.

Цель: определить, на каком resolution и какие combinations features устойчиво различают известные macro impulse и macro correction segments.

### Почему не выбирать один timeframe заранее

Нельзя заранее считать 1D, 12H или 4H «правильным» structural timeframe. Исследование должно показать:
- где свечей достаточно для статистически содержательного path/overlap анализа;
- где macro behavior ещё не растворяется в локальном шуме;
- какие признаки устойчивы между scales;
- какие признаки специфичны для конкретного resolution.

### 1W

`1W` не входит в primary signature set на первом проходе.

Причина: для многих macro segments недельных свечей будет слишком мало для устойчивого анализа overlap, alternation и динамики признаков.

`1W` сохраняется как optional coarse-context resolution для:
- самых длинных macro segments;
- многомесячных bull/bear regimes;
- robustness checks после основного 1D/12H/4H исследования.

Недостаточное число недельных свечей не должно приводить к искусственным выводам.

## 2. Исследовать динамику признаков внутри macro segment

Анализировать не только агрегат A→B целиком.

Для каждого macro segment на 1D/12H/4H исследовать, как признаки меняются по мере движения:
- начало;
- середина;
- поздняя часть;
- область перед B.

Фазы сначала задавать нейтрально, например относительными квантилями времени/ценового прогресса, без присвоения заранее семантических состояний `mature`, `decelerating` и т. п.

Результат: распределения и траектории признаков, которые реально отличаются между историческими macro impulse и macro correction.

## 3. Repeated-touch macro boundaries

Repeated exact-touch pivot episode является отдельным типом boundary evidence согласно canonical macro-trade-boundary-refinement contract.

Для repeated touch:
- price anchor считается известным;
- единственный authoritative timestamp не выбирается;
- сохраняются first touch, last touch, touch count, touch span и все supporting aggTrades;
- exact time-dependent metrics считаются только там, где boundary resolved;
- fallback использует только интервалы, гарантированно лежащие внутри segment при любом допустимом boundary time.

Дополнительно разрешается research-only boundary sensitivity analysis:
- посчитать, насколько исследовательские результаты меняются при использовании first-touch bound и last-touch bound;
- эти варианты не становятся canonical pivot timestamp;
- если вывод стабилен при обоих bounds, считать его robust к boundary ambiguity;
- если вывод меняется, маркировать feature/result как boundary-sensitive.

## 4. Найти macro impulse/correction signatures

После сравнения всех macro segments определить:
- какие признаки действительно различают исторические macro impulse vs correction;
- направление изменения признаков;
- устойчивость по разным эпохам BTC;
- устойчивость на 1D/12H/4H;
- список неинформативных признаков;
- признаки, работающие только после тонкой подгонки.

Не создавать формальные live states до этого этапа.

## 5. Только после macro signature discovery проверить перенос на меньшие масштабы

После того как macro impulse/correction signatures найдены, проверить, встречаются ли похожие objective movement classes внутри macro segments на меньших resolutions.

Первый кандидат для такого исследования — `1H`, затем `15m`; `5m/1m` оставлять для более позднего tactical/execution layer, если данные покажут необходимость.

На этом этапе ещё не предполагать `parent_leg_id` / `child_leg_id`.

Задача:
- найти внутренние directional movements объективным, отдельно утверждённым методом;
- измерить их теми же normalized features;
- проверить, похожи ли некоторые внутренние движения на найденную macro impulse signature, а другие — на macro correction signature;
- проверить устойчивость аналогии статистически и visually на historical replay.

Только если вложенная повторяемость подтверждается, можно вводить formal parent/child hierarchy.

## 6. Проверить нормализацию между масштабами

Для scale comparison проверить нормализацию через:
- ATR / realized volatility;
- амплитуду исследуемого движения;
- elapsed time;
- local range;
- relative speed;
- path efficiency;
- relative overlap/penetration metrics.

Результат: признаки, которые можно корректно сравнивать между 1D, 12H, 4H и затем 1H/15m.

## 7. Проверить фрактальную гипотезу

Мы не предполагаем заранее, что рынок фрактален в нужной для стратегии форме.

После получения macro signatures проверить, повторяется ли на меньшем масштабе последовательность вроде:

directional expansion → высокая efficiency/speed → изменение скорости → ухудшение обновления экстремумов → рост overlap/alternation/returns → compression/transition.

Названия стадий здесь являются описанием гипотезы, а не готовыми labels.

Результат:
- scale-invariant features;
- scale-dependent features;
- отсутствие повторяемости, если данные её не подтверждают.

## 8. Только после подтверждения вложенности построить hierarchy model

Если данные показывают устойчивую вложенную структуру, отдельно спроектировать:
- что является movement unit на каждом scale;
- как определяется его начало и конец causal способом;
- когда меньшее движение относится к более крупному;
- как хранить направление и position-inside-larger-movement;
- как избегать future leakage.

Именно здесь, а не раньше, могут появиться `parent movement` / `child movement` или другие более подходящие термины.

## 9. Проверить multi-timeframe согласованность

После появления доказанной hierarchy определить:
- какой scale меняется первым;
- какие признаки являются ранним предупреждением;
- какие дают позднее confirmation;
- какие признаки противоречат друг другу между scales;
- какие combinations полезны для tactical и structural decisions.

## 10. Сформировать формальные states

Только после анализа данных сформировать states вроде:
- impulse-like active movement;
- mature / decelerating movement;
- correction-like movement;
- possible range / transition;
- continuation / reversal candidate.

Финальные названия и границы должны следовать из результатов исследования.

## 11. Добавить depth / retracement / Fibonacci как research features

После появления causal movement hierarchy можно исследовать location/depth внутри более крупного движения.

Fibonacci levels не считать истинными правилами входа заранее.

Разрешено исследовать как features, например:
- 0.382;
- 0.5;
- 0.618;
- 0.786;
- continuous retracement depth;
- time retracement / duration ratios.

Цель: проверить, меняется ли probability/outcome conditioning на depth и combined structure state.

## 12. Проверить устойчивость результатов

Проверять отдельно:
- разные периоды;
- bullish/bearish historical macro regimes;
- high/low volatility;
- modern BTC era vs older history;
- out-of-sample periods;
- sensitivity к gaps, data quality, timeframe, window lengths и segmentation assumptions.

Признак, работающий только после тонкой подгонки, считать слабым.

## 13. Проверить практическую ценность модели

Для каждого candidate state измерить:
- probability continuation в направлении более крупного подтверждённого movement context;
- probability correction continuation;
- probability reversal/transition;
- последующий размер движения;
- time-to-confirmation;
- MAE/MFE;
- false early switches;
- robustness после fees/slippage для будущих strategy hypotheses.

## 14. Формализовать правила для ботов

Только после research validation оформить отдельную спецификацию:
- regime/structure layer;
- RangeBot;
- ImpulseBot или другое фактически подтверждённое разделение;
- context-only features;
- action-triggering features;
- risk layer.

## 15. Контрольный historical replay

На выбранных historical periods проверить:
- что causal algorithm реально знал в каждый момент;
- момент изменения state;
- отсутствие future leakage;
- отсутствие недопустимого state-flapping;
- соответствие calculated state реальному chart context;
- отдельно repeated-touch boundary-sensitive cases.

Только после этого переходить к production trading logic.

---

## Главный принцип

Текущая известная структура:

`macro points A/B/C/... → known historical macro segments A→B/B→C/...`

Дальше исследование должно идти так:

`macro segments → 1D/12H/4H objective signatures → impulse/correction distinction → within-segment feature dynamics → test recurrence on 1H/15m → only if supported: hierarchy → MTF causal states → out-of-sample validation → strategy rules`.

Не вводить `parent/child` как факт до того, как вложенная структура подтверждена данными.
