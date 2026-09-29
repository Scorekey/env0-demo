# ENV0-CHAIN-mid-start-from-T3

*mid-start-from-T3 (extraction onward)*

## Brief

A PE client wants to understand the consumer market for physical goods bought online in France, Germany, Spain, Italy and the Netherlands to support a growth and expansion strategy. You are staffed on the data module: establish what the market can be measured from, and assemble the inputs it needs, using 2024 as the reference year unless a task says otherwise. The deliverable is per country: one market size for each of the five. A purchase paid through a wallet charged to a card counts as a card purchase. The data landscape is in ./landscape (see its README.txt).

## Conventions of the model, to be used as they stand

- **a status inside a sum**: where one of the figures a sum would draw on is a status rather than a number, it contributes no term: the sum is formed from the figures that are printed. It is not treated as zero and it does not block the sum.
- **survey non-response codes**: the survey's non-response codes are excluded from every denominator, per variable and per wave.

## Delivery

This paper is delivered on its own, with the data and nothing else. The eight station papers are not in reach and are not part of this task. The published menu, menu_env0.json, is delivered with this paper: it lists every dataset, column and column value that may appear in an answer. A score produced under any other delivery is not a score of this environment.

## GIVEN

```json
{
 "the module's structure, to be used as it stands": [
  "consumers resident in the country, buying physical goods online, from sellers in the country and from sellers abroad",
  "five separate builds, each reported on its own",
  "one measured part of the market, scaled to the whole by the share of the market that part represents",
  "transaction-based: the number of online goods purchases, the average value per purchase, the share of online purchases that are physical goods, the share of goods purchases on a channel that can be counted"
 ],
 "the datasets the build takes its numbers from, and their roles": "PMC as the base, with PCP for Germany; SPACE_MICRO to the whole market",
 "Kinds of physical goods. Where the build needs physical goods split by kind, it uses these six, defined as follows.": {
  "APPAREL": "clothing and footwear",
  "TECH_ELECTRONICS": "consumer electronics",
  "FOOD_GROCERY": "food and drink for people",
  "HEALTH_BEAUTY": "pharmacy and cosmetics",
  "HOME_DIY": "furniture, hardware and building materials",
  "GENERAL_MERCHANDISE": "every other physical-goods retailer; the survey has no purpose code for it, and where the build needs it on the survey side it is read as all physical-goods purposes together"
 }
}
```

## The task

Build the market from the structure and sources given: per country, the figures listed below. Declare the route you took. Each computed figure is reported at six decimals and enters later steps as reported.

## Choose from

## The figures asked for, and the name to write for each

- `physical_goods_count`: the number of physical-goods purchases the country's residents make online
- `average_value_per_purchase`: the average value of one physical-goods purchase, EUR
- `market_value`: the value of physical goods bought online in 2024 by consumers resident in the country, from sellers in the country and abroad together, EUR millions
- `value_sellers_in_country`: the part of it served by sellers in the country, EUR millions
- `value_sellers_abroad`: the part of it served by sellers in other markets, EUR millions

## Answer form

- **commitments**: one row per country and component, for FR, DE, ES, IT, NL
- **route**: the extraction you specified: `extraction`, a list of addresses, each one a dataset, a column and a column value from the published menu. Required. Read as SOURCE, beside your figures and never combined with them.

## Instructions

1. One answer per question. A second answer to the same question is a format error, not a hedge.
2. An answer is one of: an option id from the list given, a set of ids from the list given, a figure, one of the statuses the contract defines, or a rejection (dataset, pins where they apply, one reason code from the contract).
3. Figures are computed from the source at full precision and reported rounded to six decimal places. Go back to the source rather than to a figure someone has already rounded: a printed figure orients you, the source is what you compute from. Once you have computed a figure yourself and reported it at six decimals, that reported figure is what enters your next step, and the chain continues at six decimals from there. Counts and euro values are in millions, the sources' own convention.
4. Where a cell has no figure, say so: SUPPRESSED, NOT_IN_DATASET, NO_OBSERVATION, INSUFFICIENT_SAMPLE, or in plain words. All of these are read as the same answer. ZERO is not one of them: it means the figure is zero.
5. Every dataset name, column name and column value must appear in the published menu (menu_env0.json). Anything off-menu is returned as a format error and is not scored.
6. Name each figure by the component name the question gives it; a name that matches none, or more than one, of the figures asked for is returned as a format error rather than guessed at.
7. Written explanation may be submitted and is never scored. Only the answer object is read.
8. Only a figure you report is rounded. A ratio or intermediate you do not report is carried at full precision into the figure that reports it.
9. Declare the route you took: the extraction you specified. Each entry is one address -- a dataset, a column, and a column value -- and every name in it comes from the published menu, as instruction 5 requires of every other address you write. The route is REQUIRED. It is not a second answer: nothing you write here changes a figure you reported. Its addresses are read as SOURCE, reported beside your figures and never combined with them. A submission with no route is reported as route not declared, which is an outcome, not a blank.

Statuses: SUPPRESSED, NO_OBSERVATION, NOT_IN_DATASET, ZERO, INSUFFICIENT_SAMPLE

## Answer template

```json
{
 "commitments": [
  {
   "geo": "<country>",
   "component": "<component name from the list>",
   "value": "<figure or status>"
  }
 ],
 "route": {
  "extraction": [
   {
    "dataset": "<dataset>",
    "column": "<column>",
    "value": "<column value>"
   }
  ]
 }
}
```
