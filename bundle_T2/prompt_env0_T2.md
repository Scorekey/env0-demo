# ENV0-T2-SOURCEMAP

## Brief

A PE client wants to understand the consumer market for physical goods bought online in France, Germany, Spain, Italy and the Netherlands to support a growth and expansion strategy. You are staffed on the data module: establish what the market can be measured from, and assemble the inputs it needs, using 2024 as the reference year unless a task says otherwise. The deliverable is per country: one market size for each of the five. A purchase paid through a wallet charged to a card counts as a card purchase. The data landscape is in ./landscape (see its README.txt).

## Conventions of the model, to be used as they stand

- **a status inside a sum**: where one of the figures a sum would draw on is a status rather than a number, it contributes no term: the sum is formed from the figures that are printed. It is not treated as zero and it does not block the sum.
- **survey non-response codes**: the survey's non-response codes are excluded from every denominator, per variable and per wave.

## Delivery

These eight papers are worked ONE AT A TIME, in station order T1 to T8. A paper is answered and submitted before the next one is opened. Each paper's GIVEN block carries the answers of the stations before it so that the work is not lost if an earlier station went wrong; reading ahead defeats that and is not how the module is run. The published menu, menu_env0.json, is delivered with this paper: it lists every dataset, column and column value that may appear in an answer, and instruction 5 holds every name you write to it.

## GIVEN

```json
{
 "the module's structure from T1, to be used as it stands": [
  "consumers resident in the country, buying physical goods online, from sellers in the country and from sellers abroad",
  "five separate builds, each reported on its own"
 ]
}
```

## The task

Examine every dataset in the landscape and settle the module's sourcing for all five countries: which datasets each country's market is built from. No figures are required; the sourcing is the deliverable.

## Questions

- Q1 · SELECT_SET per country. For each country, which datasets do you build the market from? rows: FR · DE · ES · IT · NL

## Choose from

**universe for Q1**

PAY, PCN, PCP, PCT, PDD, PEM, PIS, PLB, PMC, PPC, PTN, PTT, SPACE, SPACE_MICRO, SSP

**Q1 the datasets each country's market is built from**

the datasets listed under **universe for Q1** above; answer with those names

## Answer form

- **selections**: Q1 the datasets each country's market is built from: one set per country, keyed by country code

## Instructions

1. One answer per question. A second answer to the same question is a format error, not a hedge.
2. An answer is one of: an option id from the list given, a set of ids from the list given, a figure, one of the statuses the contract defines, or a rejection (dataset, pins where they apply, one reason code from the contract).
3. Figures are computed from the source at full precision and reported rounded to six decimal places. Go back to the source rather than to a figure someone has already rounded: a printed figure orients you, the source is what you compute from. Once you have computed a figure yourself and reported it at six decimals, that reported figure is what enters your next step, and the chain continues at six decimals from there. Counts and euro values are in millions, the sources' own convention.
4. Where a cell has no figure, say so: SUPPRESSED, NOT_IN_DATASET, NO_OBSERVATION, INSUFFICIENT_SAMPLE, or in plain words. All of these are read as the same answer. ZERO is not one of them: it means the figure is zero.
5. Every dataset name, column name and column value must appear in the published menu (menu_env0.json). Anything off-menu is returned as a format error and is not scored.
6. Name each figure by the component name the question gives it; a name that matches none, or more than one, of the figures asked for is returned as a format error rather than guessed at.
7. Written explanation may be submitted and is never scored. Only the answer object is read.

Statuses: SUPPRESSED, NO_OBSERVATION, NOT_IN_DATASET, ZERO, INSUFFICIENT_SAMPLE

## Answer template

```json
{
 "selections": {
  "<a set asked PER ROW, exactly as it is headed under Choose from>": {
   "<row>": [
    "<id>",
    "..."
   ]
  }
 }
}
```
