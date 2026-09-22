# ENV0-T3-DEFINE

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
 "the datasets the build takes its numbers from, and their roles from T2": "PMC as the base, with PCP for Germany; SPACE_MICRO to the whole market",
 "survey non-response codes": "excluded from every denominator, per variable and per wave: [\"\", \"999997\", \"999998\", \"999999\", \"NA\"] on PURPOSE, [\"\", \"999997\", \"999998\", \"999999\", \"NA\"] on INSTRUMENT in the 2024 wave"
}
```

## The task

Pin every dimension of each input to the one value the build reads for 2024, and classify every code the build reads. The columns are not listed; pin them all.

## Questions

- Q1 · PIN, scored one PICK_ONE per column. For each of the five datasets, the value of every dimension at which the build reads it. Answer object: one address per dataset (full pins). A column omitted is a miss; a column the dataset does not carry is an address that does not exist and is charged.

- Q2 · PICK_ONE per code. For each merchant category the card source names, which class is it? Options: GOODS, DIGITAL, FUEL, SERVICES, MONEY. rows: the 58 MRCHNT_CTGRY_CD values of the card source, other than 5300, 5450, 5720, 5980, 7011, G000, GFUE, GTRV, which the menu publishes and which are not rows of this question.

- Q4 · PICK_ONE per code. In the survey wave the build reads, for each purpose code: physical goods (P1), or not (P2)? rows: the 15 PURPOSE values of that wave, other than NA, 999997, 999998, 999999, which the menu publishes and which are not rows of this question.

- Q5 · PICK_ONE per code. In the survey wave the build reads, for each payment-method code: already inside the base count (I1), or not (I2)? rows: the 12 INSTRUMENT values of that wave, other than NA, 999998, 999999, which the menu publishes and which are not rows of this question.

## Choose from

**Q2 the class of each merchant category**

GOODS, DIGITAL, FUEL, SERVICES, MONEY

**Q4 purpose codes that are physical goods**

- **P1** physical goods
- **P2** not physical goods

**Q5 payment-method codes already inside the base count**

- **I1** already inside the base count
- **I2** not inside it

## Answer form

- **commitments**: Q1: one extraction per dataset, every column that dataset carries pinned to one menu value (TIME_PERIOD included)
- **assignments**: Q2, Q4, Q5: one option per row, keyed by code

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
 "assignments": {
  "<the decision, exactly as it is headed under Choose from>": "<option id>  (or, per row: {\"<row>\": \"<option id>\"})"
 },
 "commitments": [
  {
   "dataset": "<file>",
   "pins": {
    "<column>": "<value>"
   }
  }
 ]
}
```
