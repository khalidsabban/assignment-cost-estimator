import json
from pathlib import Path

from django.shortcuts import render

from estimator.engine.errors import EngineError
from estimator.engine.estimate import estimate_assignment
from estimator.forms import AssignmentForm

IMMIGRATION_PATH = Path(__file__).resolve().parent / "data" / "immigration.json"


def load_immigration():
    """Immigration requirements, or an empty structure if not yet researched."""
    if not IMMIGRATION_PATH.exists():
        return {"categories": []}
    with open(IMMIGRATION_PATH, encoding="utf-8") as immigration_file:
        return json.load(immigration_file)


def index(request):
    """The cost estimate and immigration tabs.

    The form is pre-filled with the assignment pack's test case, so the tool
    produces an estimate on first load with no input needed.
    """
    estimate = None
    engine_error = None

    if request.method == "POST":
        form = AssignmentForm(request.POST)
    else:
        form = AssignmentForm(initial={})

    if form.is_bound and form.is_valid():
        source = form
    elif not form.is_bound:
        # Validate the initial values so the first page load shows a result.
        source = AssignmentForm(data={
            field.name: field.field.initial for field in form
        })
        source.is_valid()
    else:
        source = None

    if source is not None and source.is_valid():
        try:
            estimate = estimate_assignment(source.to_assignment())
        except EngineError as error:
            engine_error = str(error)

    return render(request, "estimator/index.html", {
        "form": form,
        "estimate": estimate,
        "engine_error": engine_error,
        "immigration": load_immigration(),
        "active_tab": request.GET.get("tab", "cost"),
    })
