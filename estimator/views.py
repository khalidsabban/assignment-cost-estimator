import json
from pathlib import Path

from django.shortcuts import render

from estimator.engine.errors import EngineError
from estimator.engine.estimate import estimate_assignment
from estimator.forms import AssignmentForm

IMMIGRATION_PATH = Path(__file__).resolve().parent / "data" / "immigration.json"

TEST_CASE_DEFAULTS = {
    "home_country": "Switzerland",
    "host_country": "United Kingdom",
    "assignment_months": 24,
    "salary_chf": "150000",
    "bonus_chf": "20000",
    "exchange_rate": "1.10",
    "housing_rent_gbp": "3000",
    "relocation_allowance_chf": "5000",
    "moving_costs_gbp": "6000",
    "temporary_housing_gbp": "4000",
}

def load_immigration():
    """Immigration requirements, or an empty structure if not yet researched."""
    if not IMMIGRATION_PATH.exists():
        return {"categories": []}
    with open(IMMIGRATION_PATH, encoding="utf-8") as immigration_file:
        return json.load(immigration_file)

def index(request):
    """The cost estimate and immigration tabs.

    On first load the form is filled with the assignment pack's test case,
    so the tool produces an estimate with no input needed.
    """
    estimate = None
    engine_error = None

    if request.method == "POST":
        form = AssignmentForm(request.POST)
    else:
        form = AssignmentForm(data=TEST_CASE_DEFAULTS)

    if form.is_valid():
        try:
            estimate = estimate_assignment(form.to_assignment())
        except EngineError as error:
            engine_error = str(error)

    return render(request, "estimator/index.html", {
        "form": form,
        "estimate": estimate,
        "engine_error": engine_error,
        "immigration": load_immigration(),
        "active_tab": request.GET.get("tab", "cost"),
    })      
