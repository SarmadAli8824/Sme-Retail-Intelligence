"use client";

import {FormEvent, useEffect, useMemo, useState} from "react";

const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
type Item = {sku:string; product_name?:string; units?:number; stock_on_hand?:number; days_of_cover?:number|null; suggested_quantity?:number};
type Dashboard = {summary:{total_skus:number;units_sold:number;low_stock_count:number;reorder_count:number};top_movers:Item[];bottom_movers:Item[];low_stock:Item[];overstock:Item[];reorder_suggestions:Item[];sales_trend:{date:string;units:number}[]};
type Inventory = {sku:string;product_name?:string;category?:string;stock_on_hand:number;reorder_point?:number};
type Upload = {id:string;filename:string;kind:string;status:string;total_rows:number;rows_processed:number;errors:{row:number;error:string}[];created_at:string};
type Forecast = {id?:string;sku:string;horizon_days:number;model_name:string;mae:number;rmse:number;confidence:string;predictions:{date:string;quantity:number;lower:number;upper:number}[]};

async function request(path:string, token?:string, init:RequestInit={}) {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(api + path, {...init, headers});
  const data = await response.json().catch(() => ({detail:"Request failed"}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data;
}

export default function Home() {
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<"login"|"register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [org, setOrg] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard|null>(null);
  const [inventory, setInventory] = useState<Inventory[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<any>();
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [user, setUser] = useState<any>();
  const [forecastSku, setForecastSku] = useState("");
  const [horizon, setHorizon] = useState(14);

  const load = async (active=token) => {
    if (!active) return;
    setBusy(true);
    try {
      const [summary, me, stock, history, forecastHistory] = await Promise.all([
        request("/dashboard", active), request("/auth/me", active), request("/inventory", active), request("/uploads", active), request("/forecasts", active)
      ]);
      setDashboard(summary); setUser(me); setInventory(stock); setUploads(history); setForecasts(forecastHistory);
      setForecastSku((current) => current || stock[0]?.sku || ""); setNotice("");
    } catch (error:any) {
      localStorage.removeItem("retail_intelligence_token"); setToken(""); setNotice(error.message);
    } finally { setBusy(false); }
  };

  useEffect(() => { const saved=localStorage.getItem("retail_intelligence_token"); if(saved){setToken(saved); void load(saved)} }, []);
  const authenticate = async (event:FormEvent) => {
    event.preventDefault(); setBusy(true);
    try {
      const body = mode === "register" ? {organization_name:org,email,password} : {email,password};
      const data = await request(mode === "register" ? "/auth/register" : "/auth/login", undefined, {method:"POST",body:JSON.stringify(body)});
      localStorage.setItem("retail_intelligence_token", data.access_token); setToken(data.access_token); await load(data.access_token);
    } catch (error:any) { setNotice(error.message); } finally { setBusy(false); }
  };
  const upload = async (kind:"sales"|"inventory", file?:File) => {
    if (!file) return; setBusy(true);
    try {
      const form = new FormData(); form.append("file", file);
      const result = await request(`/uploads/${kind}`, token, {method:"POST",body:form});
      const rejected = result.errors?.length || 0;
      setNotice(`${kind === "sales" ? "Sales" : "Inventory"} import complete. ${result.rows_processed} rows accepted${rejected ? ` and ${rejected} rejected` : ""}.`);
      await load();
    } catch (error:any) { setNotice(error.message); } finally { setBusy(false); }
  };
  const ask = async (event:FormEvent) => {
    event.preventDefault(); if (!question.trim()) return; setBusy(true);
    try { setAnswer(await request("/chat", token, {method:"POST",body:JSON.stringify({question})})); setQuestion(""); }
    catch (error:any) { setNotice(error.message); } finally { setBusy(false); }
  };
  const runForecast = async (event:FormEvent) => {
    event.preventDefault(); if (!forecastSku) return; setBusy(true);
    try {
      const result = await request(`/forecasts/${encodeURIComponent(forecastSku)}?horizon=${horizon}`, token, {method:"POST"});
      setForecasts((current) => [result, ...current.filter(item => item.sku !== result.sku)]); setNotice(`Forecast ready for ${result.sku}.`);
    } catch (error:any) { setNotice(error.message); } finally { setBusy(false); }
  };
  const maximum = useMemo(() => Math.max(...(dashboard?.top_movers || []).map(item => item.units || 0), 1), [dashboard]);
  const currentForecast = forecasts[0];

  if (!token) return <main className="auth"><section className="intro"><p className="eyebrow">RETAIL CLARITY FROM A CSV</p><h1>Know what your shelves need next.</h1><p>Import sales and stock files, spot risks early, and ask questions in everyday language. No ERP or analyst required.</p><div className="pills"><span>SKU forecasts</span><span>Stock alerts</span><span>Secure analytics</span></div></section><section className="auth-card"><div className="logo">Retail Intelligence<i/></div><p className="step">OWNER WORKSPACE</p><h2>{mode === "login" ? "Welcome back" : "Create your workspace"}</h2><p>{mode === "login" ? "Sign in to see what needs attention today." : "Start with one shop and your existing CSV files."}</p><form className="form" onSubmit={authenticate}>{mode === "register" && <label>Shop or organisation<input required value={org} onChange={event=>setOrg(event.target.value)} placeholder="The Corner Store"/></label>}<label>Email<input required type="email" value={email} onChange={event=>setEmail(event.target.value)} placeholder="you@example.com"/></label><label>Password<input required minLength={12} type="password" value={password} onChange={event=>setPassword(event.target.value)} placeholder="At least 12 characters"/></label>{notice && <p className="alert">{notice}</p>}<button className="primary" disabled={busy}>{busy ? "Please wait" : mode === "login" ? "Sign in" : "Create workspace"}</button></form><button className="link" onClick={()=>{setMode(mode === "login" ? "register" : "login");setNotice("")}}>{mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}</button></section></main>;

  return <main className="app"><header className="top"><a className="logo" href="#overview">Retail Intelligence<i/></a><div className="right"><span><b>{user?.organization_name}</b><small>{user?.email}</small></span><button className="ghost" onClick={()=>{localStorage.removeItem("retail_intelligence_token");setToken("")}}>Sign out</button></div></header><div className="layout"><nav className="nav"><p className="eyebrow">WORKSPACE</p><a href="#overview">Overview</a><a href="#inventory">Inventory</a><a href="#forecast">Forecasts</a><a href="#imports">Data imports</a><a href="#assistant">Ask assistant</a></nav><section className="content"><section className="hero" id="overview"><div><p className="eyebrow">TODAY AT A GLANCE</p><h1>Good afternoon{user?.email ? `, ${user.email.split("@")[0]}` : ""}.</h1><p>Your clearest view of demand, stock, and next actions.</p></div><button className="secondary" onClick={()=>load()} disabled={busy}>{busy ? "Refreshing" : "Refresh data"}</button></section>{notice && <p className="notice">{notice}<button onClick={()=>setNotice("")}>Close</button></p>}<section className="metrics"><article className="metric coral"><span>Needs attention</span><strong>{dashboard?.summary.low_stock_count || 0}</strong><small>Low stock products</small></article><article className="metric green"><span>Sales recorded</span><strong>{dashboard?.summary.units_sold || 0}</strong><small>Total units in your data</small></article><article className="metric blue"><span>Reorder suggestions</span><strong>{dashboard?.summary.reorder_count || 0}</strong><small>Based on 30 day velocity</small></article><article className="metric cream"><span>Tracked range</span><strong>{dashboard?.summary.total_skus || 0}</strong><small>Inventory SKUs</small></article></section><section className="split"><article className="panel momentum"><div className="panel-head"><div><p className="eyebrow">SALES MOMENTUM</p><h2>Top moving products</h2></div><small>All imported sales</small></div>{dashboard?.top_movers.length ? dashboard.top_movers.map(item=><div className="bar" key={item.sku}><span>{item.sku}</span><div className="track"><i style={{width:`${((item.units||0)/maximum)*100}%`}}/></div><b>{item.units}</b></div>) : <Empty text="Upload sales data to reveal your fastest movers."/>}</article><article className="panel"><div className="panel-head"><div><p className="eyebrow">ACTION QUEUE</p><h2>Reorder suggestions</h2></div></div>{dashboard?.reorder_suggestions.length ? dashboard.reorder_suggestions.slice(0,5).map(item=><div className="stock" key={item.sku}><span><strong>{item.sku}</strong><small>{item.days_of_cover} days of cover</small></span><b>Order {item.suggested_quantity}</b></div>) : <Empty text="No immediate reorder actions."/>}</article></section><section className="panel inventory" id="inventory"><div className="panel-head"><div><p className="eyebrow">INVENTORY</p><h2>Every SKU in one view</h2></div><span className="count">{inventory.length} products</span></div>{inventory.length ? <div className="table-wrap"><table><thead><tr><th>SKU</th><th>Product</th><th>Category</th><th>On hand</th><th>Reorder point</th><th>Status</th></tr></thead><tbody>{inventory.map(item=><tr key={item.sku}><td><b>{item.sku}</b></td><td>{item.product_name || "Not provided"}</td><td>{item.category || "General"}</td><td>{item.stock_on_hand}</td><td>{item.reorder_point ?? 10}</td><td><span className={`badge ${item.stock_on_hand < (item.reorder_point ?? 10) ? "risk" : "healthy"}`}>{item.stock_on_hand < (item.reorder_point ?? 10) ? "Low stock" : "Healthy"}</span></td></tr>)}</tbody></table></div> : <Empty text="Upload inventory data to populate this view."/>}</section><section className="split"><article className="panel" id="forecast"><p className="eyebrow">DEMAND FORECAST</p><h2>Plan the next 7 to 30 days.</h2><form className="forecast-form" onSubmit={runForecast}><label>SKU<select value={forecastSku} onChange={event=>setForecastSku(event.target.value)}>{inventory.map(item=><option key={item.sku}>{item.sku}</option>)}</select></label><label>Horizon<select value={horizon} onChange={event=>setHorizon(Number(event.target.value))}><option value={7}>7 days</option><option value={14}>14 days</option><option value={21}>21 days</option><option value={30}>30 days</option></select></label><button className="primary" disabled={busy || !forecastSku}>Generate</button></form>{currentForecast ? <div className="forecast-result"><div><strong>{currentForecast.sku}</strong><span>{currentForecast.model_name.replaceAll("_"," ")} · {currentForecast.confidence} confidence</span></div><div className="forecast-metrics"><span><b>{currentForecast.predictions.reduce((sum,item)=>sum+item.quantity,0).toFixed(1)}</b> predicted units</span><span><b>{currentForecast.mae}</b> MAE</span><span><b>{currentForecast.rmse}</b> RMSE</span></div><div className="mini-bars">{currentForecast.predictions.slice(0,14).map(item=><i key={item.date} title={`${item.date}: ${item.quantity}`} style={{height:`${Math.max(8,item.quantity/Math.max(...currentForecast.predictions.map(point=>point.quantity),1)*100)}%`}}/>)}</div></div> : <Empty text="Choose a SKU with at least three sales dates."/>}</article><article className="panel chat" id="assistant"><p className="eyebrow">ASK THE ASSISTANT</p><h2>Your retail data, in plain English.</h2><p>Ask about availability, low stock, sales, movers, demand, or reorders.</p><div className="prompts"><button onClick={()=>setQuestion("Which items have low stock?")}>Low stock</button><button onClick={()=>setQuestion("What are my best movers?")}>Best movers</button><button onClick={()=>setQuestion("Show my demand forecasts")}>Forecasts</button></div><form className="ask" onSubmit={ask}><input value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask a question about your shop"/><button className="primary" disabled={busy}>Ask</button></form>{answer && <div className={`answer ${answer.rejected ? "rejected" : ""}`}><strong>{answer.answer}</strong><span>{answer.query_summary}</span>{answer.rows?.length > 0 && <div className="answer-list">{answer.rows.slice(0,6).map((row:any,index:number)=><code key={index}>{Object.entries(row).filter(([key])=>key!=="predictions").map(([key,value])=>`${key.replaceAll("_"," ")}: ${value}`).join(" · ")}</code>)}</div>}</div>}</article></section><section className="split"><article className="panel imports" id="imports"><p className="eyebrow">DATA IMPORTS</p><h2>Bring your shop data in.</h2><p>CSV rows are validated, cleaned, and scoped to your workspace.</p><div className="uploads"><label className="upload"><input type="file" accept=".csv,text/csv" onChange={event=>upload("sales",event.target.files?.[0])}/><span>Sales CSV</span><strong>Choose sales file</strong><small>date, sku, quantity_sold</small></label><label className="upload"><input type="file" accept=".csv,text/csv" onChange={event=>upload("inventory",event.target.files?.[0])}/><span>Inventory CSV</span><strong>Choose stock file</strong><small>sku, stock_on_hand</small></label></div></article><article className="panel"><div className="panel-head"><div><p className="eyebrow">RECENT ACTIVITY</p><h2>Import history</h2></div></div>{uploads.length ? uploads.slice(0,5).map(item=><div className="history" key={item.id}><span><strong>{item.filename}</strong><small>{new Date(item.created_at).toLocaleDateString()} · {item.kind}</small></span><span className={`badge ${item.status}`}>{item.status}</span><b>{item.rows_processed}/{item.total_rows}</b></div>) : <Empty text="Your completed imports will appear here."/>}</article></section></section></div></main>;
}

function Empty({text}:{text:string}) { return <div className="empty">{text}</div>; }
