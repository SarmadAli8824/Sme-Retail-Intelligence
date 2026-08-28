from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Sale
def build_forecast(db: Session, org_id: str, sku: str, horizon: int):
    import numpy as np
    import pandas as pd
    rows=db.execute(select(Sale.date, Sale.quantity_sold).where(Sale.organization_id==org_id,Sale.sku==sku).order_by(Sale.date)).all()
    if len(rows)<3: raise ValueError("At least three sales records are required")
    frame=pd.DataFrame(rows,columns=["date","quantity"]); frame["date"]=pd.to_datetime(frame["date"])
    daily=frame.groupby("date",as_index=False).quantity.sum().set_index("date").asfreq("D",fill_value=0).reset_index()
    holdout=max(1,min(14,len(daily)//5)); train=daily.iloc[:-holdout]; test=daily.iloc[-holdout:]
    if len(daily)>=56:
        try:
            from prophet import Prophet
            model=Prophet(weekly_seasonality=True,daily_seasonality=False,yearly_seasonality=False)
            model.fit(train.rename(columns={"date":"ds","quantity":"y"}))
            eval_pred=model.predict(test[["date"]].rename(columns={"date":"ds"}))["yhat"].clip(lower=0).to_numpy()
            future=pd.date_range(daily.date.max()+timedelta(days=1), periods=horizon, freq="D").to_frame(index=False,name="ds")
            values=model.predict(future)["yhat"].clip(lower=0).to_numpy(); model_name="prophet"
        except Exception: values,eval_pred,model_name=_ses(train.quantity.to_numpy(),horizon,holdout)
    else: values,eval_pred,model_name=_ses(train.quantity.to_numpy(),horizon,holdout)
    actual=test.quantity.to_numpy(); mae=float(np.mean(np.abs(actual-eval_pred))); rmse=float(np.sqrt(np.mean((actual-eval_pred)**2)))
    start=daily.date.max()+timedelta(days=1)
    return {"sku":sku,"horizon_days":horizon,"model_name":model_name,"mae":round(mae,3),"rmse":round(rmse,3),"predictions":[{"date":str((start+timedelta(days=i)).date()),"quantity":round(float(v),2)} for i,v in enumerate(values)]}
def _ses(series,horizon,holdout):
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
    fit=SimpleExpSmoothing(series, initialization_method="estimated").fit(optimized=True)
    return fit.forecast(horizon),fit.forecast(holdout),"simple_exponential_smoothing"
