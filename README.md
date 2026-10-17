# Assignment Cost Estimator

A Django tool that estimates what an international assignment costs the
employer under tax equalisation, and sets out the immigration requirements.

Test case: an employee sent from Switzerland (city of Zurich) to the UK
(London) for two years, 6 April 2026 to 5 April 2028.

Loom walkthrough: 

## What it does

**Cost estimate tab.** Takes home salary, bonus, assignment benefits and an
exchange rate, and returns the employer's cost per year and across the
assignment, in four sections: home pay, assignment benefits, host tax and
charges paid by the employer, and the hypothetical home deductions that
reduce the cost. It also shows the total as a multiple of home pay and the
assumptions the figure depends on.

The employer pays the employee's UK tax, and that payment is itself taxable
income, so the tax is grossed up. Because UK rates change between bands and
the personal allowance is withdrawn above £100,000, the tool solves
T = UKTax(I + T) by iteration rather than by a single multiplication.

**Immigration tab.** The work permit route, the business visit position
before the assignment, passport requirements and the company's obligations,
each with its cost, timing and a link to the GOV.UK page it came from.

## Requirements

Python 3.9 or newer. No database setup, no Node, no API keys.

## Install and run

    git clone https://github.com/khalidsabban/assignment-cost-estimator.git
    cd assignment-cost-estimator
    python3 -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python manage.py runserver

Open http://127.0.0.1:8000. The form is pre-filled with the test case, so a
cost estimate appears on first load with no input and no code changes.

The Django secret key is read from the `DJANGO_SECRET_KEY` environment
variable, and a random one is generated at startup if it is not set, so no
configuration is needed. See `.env.example`.

## Run the tests

    python manage.py test

## How the code is organised

    estimator/engine/       plain Python, no Django imports
      uk_income_tax.py      UK income tax, including the allowance taper
      grossup.py            the iterative tax-on-tax solver
      benefits.py           benefit tagging and the relocation exemption
      swiss_hypothetical.py hypothetical Swiss tax and social security
      social_security.py    which country's system applies, and employer charges
      estimate.py           runs the pipeline and builds the output
      money.py              Decimal helpers and currency conversion
      errors.py             error types the Django layer turns into messages
    estimator/data/         tax and immigration rules as JSON, each with its source URL
    estimator/tests/        tests for every module above, plus the views
    estimator/forms.py      input validation
    estimator/views.py      passes inputs in and renders the result
    docs/                   assumptions and the research behind each figure

The calculation engine does not import Django, so it can be tested without a
server. Rules live in data files rather than in code, so every figure in the
output carries the link to the page it came from, and a rate change never
touches the logic.

All money is handled with Python's `Decimal` type. Nothing is rounded inside
the tax calculation; rounding happens at currency conversion and on display.

## Sources and assumptions

Every tax rule and immigration requirement in the output links to the
official page it came from. The full assumptions list is in
`docs/ASSUMPTIONS.md` and is also shown under the cost table.

The Swiss figures were checked against the Swiss Federal Tax Administration
calculator: supplying the same taxable income, it returns CHF 31,834 of
income tax against this tool's CHF 31,833.01. Running that calculator from
gross pay with its own default deductions returns CHF 29,554, because it
also deducts occupational pension and accident insurance, which the
assignment pack instructs us to exclude. That difference is documented
rather than hidden. The research behind each figure is in `docs/`.

This is an exercise, not tax advice.

## AI tools used


## Known limitations

- Only the Switzerland to UK corridor is supported. Other country pairs
  return a clear message rather than a figure.
- UK 2026/27 rates are used for both assignment years, as the pack instructs.
- Immigration fees and timings were checked on 16 October 2026 and change
  often.
  