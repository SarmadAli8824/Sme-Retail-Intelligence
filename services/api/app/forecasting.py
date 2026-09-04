from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Sale


def _interval(values: np.ndarray, residuals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    spread = max(float(np.std(residuals)) if residuals.size else 0.0, 0.5)
    return np.maximum(0, values - 1.96 * spread), values + 1.96 * spread


def _ses(series: np.ndarray, horizon: int, holdout: int):
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing

    fit = SimpleExpSmoothing(series, initialization_method="estimated").fit(optimized=True)
    return fit.forecast(horizon), fit.forecast(holdout), "simple_exponential_smoothing"


def build_forecast(db: Session, org_id: str, sku: str, horizon: int) -> dict:
    rows = db.execute(
        select(Sale.date, Sale.quantity_sold)
        .where(Sale.organization_id == org_id, Sale.sku == sku)
        .order_by(Sale.date)
    ).all()
    if len(rows) < 3:
        raise ValueError("At least three sales records are required for this SKU")

    frame = pd.DataFrame(rows, columns=["date", "quantity"])
    frame["date"] = pd.to_datetime(frame["date"])
    daily = frame.groupby("date", as_index=False).quantity.sum().set_index("date").asfreq("D", fill_value=0).reset_index()
    holdout = max(1, min(14, len(daily) // 5))
    train, test = daily.iloc[:-holdout], daily.iloc[-holdout:]

    if len(daily) >= 56:
        try:
            from prophet import Prophet

            model = Prophet(weekly_seasonality=True, daily_seasonality=False, yearly_seasonality=False, interval_width=0.95)
            model.fit(train.rename(columns={"date": "ds", "quantity": "y"}))
            evaluation = model.predict(test[["date"]].rename(columns={"date": "ds"}))
            eval_pred = evaluation["yhat"].clip(lower=0).to_numpy()
            future = pd.date_range(daily.date.max() + timedelta(days=1), periods=horizon, freq="D").to_frame(index=False, name="ds")
            predicted = model.predict(future)
            values = predicted["yhat"].clip(lower=0).to_numpy()
            lower = predicted["yhat_lower"].clip(lower=0).to_numpy()
            upper = predicted["yhat_upper"].clip(lower=0).to_numpy()
            model_name = "prophet"
        except Exception:
            values, eval_pred, model_name = _ses(train.quantity.to_numpy(), horizon, holdout)
            lower, upper = _interval(values, test.quantity.to_numpy() - eval_pred)
    else:
        values, eval_pred, model_name = _ses(train.quantity.to_numpy(), horizon, holdout)
        lower, upper = _interval(values, test.quantity.to_numpy() - eval_pred)

    actual = test.quantity.to_numpy()
    mae = float(np.mean(np.abs(actual - eval_pred)))
    rmse = float(np.sqrt(np.mean((actual - eval_pred) ** 2)))
    relative_error = rmse / max(float(np.mean(actual)), 1.0)
    confidence = "high" if len(daily) >= 84 and relative_error <= 0.35 else "medium" if len(daily) >= 28 and relative_error <= 0.75 else "limited"
    start = daily.date.max() + timedelta(days=1)
    predictions = [
        {"date": str((start + timedelta(days=index)).date()), "quantity": round(float(value), 2), "lower": round(float(lower[index]), 2), "upper": round(float(upper[index]), 2)}
        for index, value in enumerate(values)
    ]
    return {"sku": sku, "horizon_days": horizon, "model_name": model_name, "mae": round(mae, 3), "rmse": round(rmse, 3), "confidence": confidence, "status": "ready", "predictions": predictions}
