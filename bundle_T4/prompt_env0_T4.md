# ENV0-T4-EXTRACT

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
 "the datasets and their roles, carried forward from T2 and T3": "PMC as the base, with PCP for Germany; SPACE_MICRO to the whole market",
 "T3's answers as they stand": {
  "the pinned address of each input": {
   "PMC": {
    "FREQ": "Q",
    "COUNT_AREA": "_Z",
    "TRMNL_LCTN": "W0",
    "RMT_INTTN": "R",
    "TRANSFORMATION": "N",
    "UNIT_MEASURE": "PN"
   },
   "PCP": {
    "FREQ": "Q",
    "COUNT_AREA": "_Z",
    "TRMNL_LCTN": "W0",
    "TYP_TRNSCTN": "CP0",
    "RL_TRNSCTN": "1",
    "INTTN_CHNNL": "2000",
    "RMT_INTTN": "R",
    "PYMNT_SCHM": "PCS_ALL",
    "CRD_FNCTN": "_Z",
    "SCA": "_X",
    "FRD_TYP": "_Z",
    "TRANSFORMATION": "N",
    "UNIT_MEASURE": "PN"
   },
   "SPACE_MICRO": {
    "TIME_PERIOD": "2024",
    "MEASURE": "PN_W"
   }
  },
  "the classification of the named merchant categories": {
   "4111": "SERVICES",
   "4112": "SERVICES",
   "4121": "SERVICES",
   "4722": "SERVICES",
   "4784": "SERVICES",
   "4814": "SERVICES",
   "4829": "MONEY",
   "4899": "SERVICES",
   "4900": "SERVICES",
   "5200": "GOODS",
   "5211": "GOODS",
   "5251": "GOODS",
   "5310": "GOODS",
   "5311": "GOODS",
   "5331": "GOODS",
   "5399": "GOODS",
   "5411": "GOODS",
   "5422": "GOODS",
   "5441": "GOODS",
   "5462": "GOODS",
   "5499": "GOODS",
   "5541": "FUEL",
   "5542": "FUEL",
   "5651": "GOODS",
   "5661": "GOODS",
   "5691": "GOODS",
   "5712": "GOODS",
   "5732": "GOODS",
   "5734": "DIGITAL",
   "5811": "SERVICES",
   "5812": "SERVICES",
   "5813": "SERVICES",
   "5814": "SERVICES",
   "5815": "DIGITAL",
   "5816": "DIGITAL",
   "5817": "DIGITAL",
   "5818": "DIGITAL",
   "5912": "GOODS",
   "5921": "GOODS",
   "5941": "GOODS",
   "5942": "GOODS",
   "5945": "GOODS",
   "5947": "GOODS",
   "5977": "GOODS",
   "5992": "GOODS",
   "5993": "GOODS",
   "5995": "GOODS",
   "5999": "GOODS",
   "6012": "MONEY",
   "7230": "SERVICES",
   "7399": "SERVICES",
   "7523": "SERVICES",
   "7995": "SERVICES",
   "7999": "SERVICES",
   "9399": "SERVICES",
   "GAIR": "SERVICES",
   "GCAR": "SERVICES",
   "GHOT": "SERVICES"
  },
  "the survey purpose set (physical goods), 2024 wave": [
   "1",
   "2",
   "3",
   "4",
   "8",
   "10"
  ],
  "the survey payment-method set (already inside the base count), 2024 wave": [
   "1",
   "14",
   "3",
   "12",
   "15"
  ]
 },
 "conventions handed to you, to be used as they stand": {
  "the product segment of each physical-goods merchant category": {
   "5200": "HOME_DIY",
   "5211": "HOME_DIY",
   "5251": "HOME_DIY",
   "5310": "GENERAL_MERCHANDISE",
   "5311": "GENERAL_MERCHANDISE",
   "5331": "GENERAL_MERCHANDISE",
   "5399": "GENERAL_MERCHANDISE",
   "5411": "FOOD_GROCERY",
   "5422": "FOOD_GROCERY",
   "5441": "FOOD_GROCERY",
   "5462": "FOOD_GROCERY",
   "5499": "FOOD_GROCERY",
   "5651": "APPAREL",
   "5661": "APPAREL",
   "5691": "APPAREL",
   "5712": "HOME_DIY",
   "5732": "TECH_ELECTRONICS",
   "5912": "HEALTH_BEAUTY",
   "5921": "FOOD_GROCERY",
   "5941": "GENERAL_MERCHANDISE",
   "5942": "GENERAL_MERCHANDISE",
   "5945": "GENERAL_MERCHANDISE",
   "5947": "GENERAL_MERCHANDISE",
   "5977": "HEALTH_BEAUTY",
   "5992": "GENERAL_MERCHANDISE",
   "5993": "GENERAL_MERCHANDISE",
   "5995": "GENERAL_MERCHANDISE",
   "5999": "GENERAL_MERCHANDISE"
  },
  "which merchant categories this map covers": "the 28 categories listed above, which are the physical-goods categories. The menu publishes 66 MRCHNT_CTGRY_CD values in all; the other 38 carry no product segment and are not read by any segment figure: 4111, 4112, 4121, 4722, 4784, 4814, 4829, 4899, 4900, 5300, 5450, 5541, 5542, 5720, 5734, 5811, 5812, 5813, 5814, 5815, 5816, 5817, 5818, 5980, 6012, 7011, 7230, 7399, 7523, 7995, 7999, 9399, G000, GAIR, GCAR, GFUE, GHOT, GTRV."
 },
 "units": "figures in millions; the conversion factor is the SCALE register row, and no literal is legal"
}
```

## The task

Pull the 2024 numbers, per country, from the addresses you pinned. Where a cell does not publish, commit the status it resolves to.

## Questions

- Q1 · VALUE or status, per country. The count the build is based on: the total the base dataset publishes over all merchant categories together, not the sum of the named categories (that sum is Q2's `named_total`).

- Q2 · VALUE, per country and per class. That same count in each of the five classes from T3, on the categories the source names; and their total.

- Q3 · VALUE, per country and per segment. The physical-goods count split into the six product segments the source's categories map to.

- Q4 · VALUE, per country. The value of the physical-goods purchases, from the same rows as their count.

## Component names, per question

**Q1**

- `starting_count`: the base dataset's total over all merchant categories together, at the address pinned at T3

**Q2**

- `class_count.GOODS`: card payments counted on PMC and summed over the 28 merchant categories the classification puts in class GOODS, at the address pinned at T3
- `class_count.DIGITAL`: card payments counted on PMC and summed over the 5 merchant categories the classification puts in class DIGITAL, at the address pinned at T3
- `class_count.FUEL`: card payments counted on PMC and summed over the 2 merchant categories the classification puts in class FUEL, at the address pinned at T3
- `class_count.SERVICES`: card payments counted on PMC and summed over the 21 merchant categories the classification puts in class SERVICES, at the address pinned at T3
- `class_count.MONEY`: card payments counted on PMC and summed over the 2 merchant categories the classification puts in class MONEY, at the address pinned at T3
- `named_total`: the five classes together

**Q3**

- `segment_count.APPAREL`: physical-goods count in segment APPAREL
- `segment_count.TECH_ELECTRONICS`: physical-goods count in segment TECH_ELECTRONICS
- `segment_count.HOME_DIY`: physical-goods count in segment HOME_DIY
- `segment_count.FOOD_GROCERY`: physical-goods count in segment FOOD_GROCERY
- `segment_count.HEALTH_BEAUTY`: physical-goods count in segment HEALTH_BEAUTY
- `segment_count.GENERAL_MERCHANDISE`: physical-goods count in segment GENERAL_MERCHANDISE

**Q4**

- `goods_value`: value of the card payments counted on PMC and summed over the 28 merchant categories the classification puts in class GOODS, EUR millions

## Answer form

- **commitments**: one row per country and component; components as listed per question

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
 "commitments": [
  {
   "geo": "<country>",
   "component": "<component name from the question>",
   "value": "<figure or status>"
  }
 ]
}
```
