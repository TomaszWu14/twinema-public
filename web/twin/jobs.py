"""Zadania kolejki dla modułu bliźniaka (US-007, US-024): symulacja i kalibracja dnia projektowego, import zadań."""

from datetime import date

from twin.models import WarehouseModel
from twin.models_tasks import WarehouseTaskBatch


def simulate_day(p):
    from twin.views.warehouse_design_sim import run_simulation
    batch = WarehouseTaskBatch.objects.get(pk=p["batch"])
    wm = WarehouseModel.objects.get(pk=p["model"])
    result, n_tasks = run_simulation(batch, wm, date.fromisoformat(p["day"]), p["prm"])
    return {"result": result, "n_tasks": n_tasks}


def calibrate_day(p):
    from twin.views.warehouse_calibration import compute_calibration
    batch = WarehouseTaskBatch.objects.get(pk=p["batch"])
    wm = WarehouseModel.objects.get(pk=p["model"])
    return {"result": compute_calibration(batch, wm, date.fromisoformat(p["day"]))}


def import_tasks(p):
    from twin.ewm_tasks_import import run_import
    batch = run_import(p["batch"], p["token"])
    return {"status": batch.status, "message": batch.message}
