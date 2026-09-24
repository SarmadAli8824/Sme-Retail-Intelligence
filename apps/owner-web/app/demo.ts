// This adapter is used only for the public, browser-only sample-data demo.
// The Docker application continues to call the real authenticated FastAPI API.
const inventory=[
  {sku:"COFFEE-01",product_name:"House Blend Coffee",category:"Pantry",stock_on_hand:8,reorder_point:16,units:645},
  {sku:"TEA-02",product_name:"Breakfast Tea",category:"Pantry",stock_on_hand:42,reorder_point:12,units:393},
  {sku:"OATS-03",product_name:"Rolled Oats",category:"Breakfast",stock_on_hand:120,reorder_point:20,units:309},
  {sku:"HONEY-04",product_name:"Wildflower Honey",category:"Pantry",stock_on_hand:6,reorder_point:10,units:225},
  {sku:"PASTA-05",product_name:"Penne Pasta",category:"Pantry",stock_on_hand:55,reorder_point:15,units:477},
  {sku:"SOAP-06",product_name:"Olive Oil Soap",category:"Home",stock_on_hand:24,reorder_point:8,units:225},
];
const low=inventory.filter(p=>p.stock_on_hand<p.reorder_point);
const movers=[...inventory].sort((a,b)=>b.units-a.units);
let forecasts:any[]=[];
export async function demoRequest(path:string,init:RequestInit={}){
  if(path==="/auth/me")return {organization_name:"The Corner Pantry",email:"Sample workspace",role:"owner"};
  if(path==="/inventory")return inventory;
  if(path==="/dashboard")return {summary:{total_skus:inventory.length,units_sold:inventory.reduce((s,p)=>s+p.units,0),low_stock_count:low.length,reorder_count:low.length},top_movers:movers,bottom_movers:[...movers].reverse(),low_stock:low,overstock:[],reorder_suggestions:low.map(p=>({...p,days_of_cover:(p.stock_on_hand/(p.units/84)).toFixed(1),suggested_quantity:Math.ceil(p.units/84*14-p.stock_on_hand)}))};
  if(path==="/uploads")return [{id:"sample-sales",filename:"sales-sample.csv",kind:"sales",status:"sample",total_rows:504,rows_processed:504,created_at:"2026-09-24T09:00:00Z"},{id:"sample-stock",filename:"inventory-sample.csv",kind:"inventory",status:"sample",total_rows:6,rows_processed:6,created_at:"2026-09-24T09:00:00Z"}];
  if(path==="/forecasts")return forecasts;
  if(path.startsWith("/forecasts/")){
    const [encoded,params]=path.slice(11).split("?");const item=inventory.find(p=>p.sku===decodeURIComponent(encoded));if(!item)throw Error("Choose a sample product.");
    const horizon=Number(new URLSearchParams(params).get("horizon")||14);
    const f={sku:item.sku,model_name:"illustrative_daily_average_preview",confidence:"sample",mae:"Not evaluated",rmse:"Not evaluated",predictions:Array.from({length:horizon},(_,i)=>({date:new Date(Date.UTC(2026,8,25+i)).toISOString().slice(0,10),quantity:Number((item.units/84).toFixed(1))}))};
    forecasts=[f,...forecasts.filter(p=>p.sku!==f.sku)];return f;
  }
  if(path==="/chat"){
    const question=JSON.parse(String(init.body||"{}")).question?.toLowerCase()||"";
    if(/delete|drop|password|secret|update|insert/.test(question))return {answer:"This demo supports read only inventory questions.",query_summary:"No query was executed.",rows:[],rejected:true};
    const rows=/low|reorder/.test(question)?low:/worst|bottom/.test(question)?[...movers].reverse():/best|mover|sales/.test(question)?movers:/forecast|demand/.test(question)?forecasts:inventory;
    return {answer:rows.length?`Here are ${rows.length} matching sample records.`:"Generate a sample forecast first, then ask again.",query_summary:"Browser-only sample answers. No AI provider or database query is used in this public demo.",rows,rejected:false};
  }
  if(path.startsWith("/uploads/"))throw Error("File processing runs in the full Docker app. This public demo uses sample data only; your selected file has not been uploaded.");
  throw Error("This action is available in the full Docker app.");
}
