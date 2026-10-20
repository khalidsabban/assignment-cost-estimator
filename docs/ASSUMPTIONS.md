# Assumptions

Every figure this tool produces depends on the assumptions below. They are
listed here for review, and the ones the cost figure depends on are also
shown under the cost table in the output.

Last updated: 19 October 2026

## Scope and method

1. Only the Switzerland (city of Zurich) to UK (London) corridor is
   supported. Any other country pair returns a clear "not supported"
   message rather than a figure.
2. UK 2026/27 income tax rates and thresholds are used for both assignment
   years, as instructed by the assignment pack.
3. England rates are used, not Scottish or Welsh rates, because the
   assignment is to London.
4. The employee is UK tax resident in both years and leaves Swiss tax
   residence for the duration of the assignment, as stated in the pack.
5. This is an exercise, not tax advice.

## Money and rounding

6. All money is calculated with Python's `Decimal` type to avoid
   floating-point rounding errors.
7. Amounts converted from CHF are rounded to the nearest penny at the point
   of conversion. UK tax is calculated without rounding, and figures are
   rounded to pence only when displayed. Each converted line is rounded
   independently, so displayed rows always sum to their displayed total.
   Converting a combined figure instead could differ by a penny.
8. The exchange rate is a fixed input (£1 = CHF 1.10 in the test case) and
   applies unchanged to both years.

## UK income tax

9. The personal allowance taper formally applies to "adjusted net income".
   This tool treats the income passed to the tax function as that income,
   with no further adjustments.
10. No other allowances, reliefs or deductions are applied.

## Gross-up

11. The UK taxable pay before tax (I) is net home pay after the
    hypothetical deductions, plus the taxable benefits. This follows the
    definition given in the assignment pack.
12. The tax on tax is found by iteration, stopping when successive
    estimates differ by less than 0.000001, and raising a clear error if it
    fails to settle within 1,000 iterations.

## Benefits

13. Housing: the employer (or its UK subsidiary) holds the tenancy, and the
    rent paid exceeds the property's annual value, so the taxable amount is
    the rent paid. If the employee were the tenant instead, the same amount
    would be taxable as earnings rather than as a benefit in kind.
14. Relocation allowance: paid as a fixed cash allowance without receipts,
    so it is not a reimbursement of qualifying removal expenses and is fully
    taxable.
15. Moving costs and temporary housing qualify as removal expenses because
    the employee changes their main residence as a result of the change in
    workplace.
16. The serviced apartment counts as temporary living accommodation,
    because the employee intends to move into the rented London flat as
    their accommodation for the posting. Without this reading, the £4,000
    would be fully taxable instead of counting towards the exemption.
17. The relocation exemption of £8,000 is a single cap per relocation,
    shared across all qualifying costs and both years, not renewed each
    year. It is applied in year order as costs arise. In the test case the
    £6,000 of moving costs is fully exempt, £2,000 of the temporary housing
    uses the remainder of the cap, and the other £2,000 is taxable.

## Swiss hypothetical deductions

18. Hypothetical Swiss tax is the federal, cantonal and communal income tax
    a single person living in the city of Zurich would pay on the same
    salary and bonus, with no church tax.
19. Hypothetical Swiss social security covers the employee's AHV/IV/EO and
    unemployment insurance contributions only. The occupational pension
    (BVG) is excluded, as stated in the pack.
20. The Swiss calculation is modelled as follows:
    - Employee AHV/IV/EO at 5.3% on uncapped pay, and unemployment
      insurance (ALV) at 1.1% up to CHF 148,200.
    - Professional expenses of 3% of net employment pay, subject to a
      minimum of CHF 2,000 and a maximum of CHF 4,000. The test case
      reaches the maximum.
    - Insurance premiums at the full single-person cap: CHF 1,800 federal
      and CHF 2,900 cantonal. This assumes qualifying premiums after
      subsidies are sufficient to use the cap. These are capped deductions,
      not automatic allowances.
    - Taxable income is rounded down to the nearest CHF 100, and federal
      tax down to the nearest CHF 0.05.
    - Federal and Zurich taxable incomes differ because their insurance
      deduction caps differ, giving CHF 153,500 federal and CHF 152,400
      cantonal for the test case.
    - The cantonal and communal taxes both derive from a single simple tax
      figure, multiplied by 95% for the canton of Zurich and 119% for the
      city of Zurich.
    - Excluded: church tax, wealth tax, the CHF 24 personal tax, actual
      occupational pension (BVG) and accident insurance contributions,
      commuting and meal costs, pillar 3a, debt interest, donations,
      dependants and other individual deductions.
    - Checked against the Swiss Federal Tax Administration calculator
      (version 2.1.3, accessed 15 October 2026). Supplying the same taxable
      incomes directly, the calculator returns CHF 31,834 of income tax
      against this model's CHF 31,833.01, a difference of under 0.01%.
    - Running the same calculator from gross pay with its own default
      deductions returns CHF 29,554, because it also deducts occupational
      pension and accident insurance. This model excludes those on the
      assignment pack's instruction, so it is about 7.7% higher. This is a
      disclosed modelling difference, not a rounding discrepancy.

## Social security during the assignment

21. The employee remains in the Swiss system for both years, because the
    assignment lasts exactly 24 months, within the posting limit of up to
    2 years. No UK employer Class 1 or Class 1A National Insurance is
    charged. This depends on the posting conditions being met and on a
    certificate of coverage (Portable Document A1), issued by the
    employer's Swiss AHV compensation office, covering the whole
    assignment. The case information does not establish that a certificate
    has been issued, so this is a proposed treatment rather than a
    confirmed one.
22. The UK Employment Allowance is not applied. It is an employer-level
    relief against employer Class 1 only, not a per-employee allowance and
    not available against Class 1A.
23. Swiss contribution rates are the 2026 published rates, held constant for
    the second assignment year as a modelling assumption rather than a
    confirmation of future rates. The same applies to the UK 2026/27 rates.

## Immigration

24. Immigration requirements and fees were checked against live GOV.UK pages
    on 16 October 2026, and are the current figures rather than those in
    force at the assignment's 6 April 2026 start date.
25. The Global Business Mobility Senior or Specialist Worker route is
    assumed, as a temporary intra-group transfer. The Skilled Worker route
    is a viable alternative, and would be preferable where a future
    settlement route matters. The choice remains conditional on the
    occupation code, duties, hours and qualifying salary.
26. The health surcharge is budgeted at the two to two and a half year band,
    because permission normally runs 14 days beyond the job end date, so a
    full two-year assignment usually exceeds two years.
27. No skills charge exemption is assumed. The exemption for certain EU
    nationals transferring from an EU business does not cover a Swiss
    national from a Swiss business, though an occupational exemption may
    still apply.
28. Immigration costs are shown separately for small or charitable and for
    medium or large sponsors, because the sponsor's size is not
    established. The licence fee is shown separately again, as a
    company-level setup cost rather than a per-employee charge.
29. Immigration costs are not included in the employer cost table, which
    covers pay, benefits and tax only.
    