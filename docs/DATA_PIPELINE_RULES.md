# Data Pipeline Rules

These rules apply to all large historical market-data builds, resampling jobs, feature-generation pipelines, and other high-volume research processing in this repository.

Before starting any large-scale data build or collection task, read this file together with the repository `AGENTS.md` and the task-specific specification.

## 1. Memory-safe execution is mandatory

Do not design production runs around holding the full multi-year dataset or multiple target datasets as millions of Python objects in RAM.

Prefer bounded processing:

- process one target timeframe or major output at a time;
- use chunked, streaming, or partitioned processing;
- prefer calendar-year partitions for multi-year market data when they preserve the approved data contract;
- write bounded batches / Parquet row groups incrementally instead of accumulating the complete output in Python lists;
- release memory between completed target datasets or partitions.

A methodologically equivalent streaming/partitioned implementation is preferred over a monolithic in-memory implementation when the latter risks exhausting available memory.

## 2. Partition boundaries must not change semantics

Partitioning is an execution strategy only. It must not change the resulting candles, features, timestamps, or other business semantics.

When a calculation can cross a technical partition boundary:

- carry only the minimum required state/tail into the next partition;
- prevent duplicate rows;
- prevent missing rows;
- preserve UTC alignment and the approved timeframe contract;
- independently verify representative partition boundaries.

Outputs must be equivalent to the same calculation performed on the uninterrupted source series, subject only to the approved source-data gaps.

## 3. Sequential target processing

When several large derived datasets are requested, do not keep all targets in memory simultaneously unless bounded memory use has been demonstrated.

Default production pattern:

1. build one target;
2. incrementally persist it;
3. complete target-specific QA;
4. release memory;
5. continue with the next target.

## 4. Persist progress at least every 20 minutes

Any data-collection, data-build, resampling, or large feature-generation task must persist generated data and/or a usable progress checkpoint to durable storage no later than every 20 minutes while work is in progress.

Do not rely on an in-memory run that can lose more than 20 minutes of completed work.

A progress checkpoint should record, where applicable:

- task/stage identity;
- target dataset/timeframe;
- completed partition or chunk;
- input rows processed;
- output rows written;
- coverage completed;
- errors/warnings;
- input/config fingerprint or checksum;
- current artifact/checkpoint path.

## 5. Resume must be real

If a long-running task supports resume/checkpoint behavior, it must be able to continue from a validated completed partition/checkpoint or safely rebuild only the incomplete partition.

Do not label a process resumable if the checkpoint is written only after the full computation is already finished.

Before reusing a checkpoint, verify compatibility with the current input, configuration, code/stage version, and existing artifacts.

## 6. Incremental and atomic artifact writing

Do not expose partially written production artifacts as canonical completed data.

Use a safe pattern such as:

`bounded computation -> temporary/partition output -> validation -> durable write -> final promotion after full QA`

Partial outputs must be clearly distinguishable from final canonical artifacts.

A dataset becomes canonical only after the required coverage is complete and QA/checksum gates have passed.

## 7. Streaming / bounded QA

Large QA jobs must also be resource-safe.

Prefer incremental or metadata-level checks for:

- row counts;
- timestamp min/max;
- chronological order;
- duplicate timestamps;
- expected/actual constituent counts;
- complete/incomplete counts;
- OHLC invariants;
- additive-field invariants;
- known-gap tracking;
- coverage;
- partition metadata and checksums.

Use bounded independent samples and boundary-focused reads for semantic verification instead of materializing the full historical dataset as Python objects solely for QA.

## 8. Smoke test before full historical build

Before an expensive full-history production run, execute the smallest meaningful real-data smoke test that can verify:

- source discovery;
- schema;
- aggregation/calculation semantics;
- output writing;
- partition boundary behavior;
- QA logic.

The smoke test does not replace the full production QA.

## 9. Failure handling

A resource failure such as OOM during an initial implementation attempt is not a data-quality failure if no target artifact was promoted and the source was unchanged.

After such a failure:

- preserve the approved source/data contract and calculation semantics;
- redesign execution to be bounded/streaming/partitioned;
- do not silently change the research method merely to reduce memory use;
- document retries/resumed partitions in the final report.

## 10. Final report for large data builds

In addition to task-specific outputs, report:

- execution strategy;
- partition/chunk scheme;
- target processing order;
- whether incremental writes/checkpoints were used;
- retries or resumed/rebuilt partitions;
- complete/incomplete coverage;
- confirmation that partition boundaries do not alter output semantics;
- checksums/QA status;
- peak memory if readily available.

## 11. Repository and generated-data separation

Generated large research/market datasets remain outside Git unless the approved task explicitly says otherwise.

Git should contain code, tests, lightweight manifests/docs, and the contracts required to reproduce the build.

---

This document is a standing engineering rule. Task-specific specifications may add stricter requirements but must not silently weaken these safeguards.