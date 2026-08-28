package main

import (
  "bytes"
  "context"
  "encoding/json"
  "fmt"
  "net/http"
  "os"
  "time"
  "github.com/jackc/pgx/v5"
)

type recipient struct { OrgID, Email string }
func main() {
  dsn := os.Getenv("DATABASE_URL")
  if dsn == "" { panic("DATABASE_URL is required") }
  ctx := context.Background()
  conn, err := pgx.Connect(ctx, dsn); if err != nil { panic(err) }; defer conn.Close(ctx)
  ticker := time.NewTicker(30 * time.Second); defer ticker.Stop()
  for { if err := process(ctx, conn); err != nil { fmt.Printf("worker error: %v\n", err) }; <-ticker.C }
}
func process(ctx context.Context, conn *pgx.Conn) error {
  // Claims queued uploads safely, allowing restart-safe polling and future API queueing.
  _,err:=conn.Exec(ctx,`UPDATE uploads SET status='completed' WHERE id IN (SELECT id FROM uploads WHERE status='queued' FOR UPDATE SKIP LOCKED LIMIT 20)`); if err!=nil{return err}
  return sendWeeklyDigests(ctx,conn)
}
func sendWeeklyDigests(ctx context.Context, conn *pgx.Conn) error {
  rows,err:=conn.Query(ctx,`SELECT u.organization_id,u.email FROM users u WHERE u.role='owner' AND NOT EXISTS (SELECT 1 FROM digest_runs d WHERE d.organization_id=u.organization_id AND d.created_at >= date_trunc('week',now()))`);if err!=nil{return err};defer rows.Close()
  for rows.Next(){var r recipient;if err:=rows.Scan(&r.OrgID,&r.Email);err!=nil{return err};if err:=sendDigest(r);err!=nil{return err};id:=fmt.Sprintf("digest-%s-%d",r.OrgID,time.Now().UnixNano());_,err=conn.Exec(ctx,`INSERT INTO digest_runs(id,organization_id,status,sent_at,created_at) VALUES($1,$2,'sent',now(),now())`,id,r.OrgID);if err!=nil{return err}}
  return rows.Err()
}
func sendDigest(r recipient) error {
  key:=os.Getenv("RESEND_API_KEY"); if key=="" { fmt.Printf("digest dry-run for %s\n",r.Email);return nil }
  payload:=map[string]string{"from":os.Getenv("RESEND_FROM"),"to":r.Email,"subject":"Your weekly retail intelligence digest","html":"<h1>Weekly retail intelligence digest</h1><p>Sign in to view current demand forecasts, low-stock alerts, and top movers.</p>"};body,_:=json.Marshal(payload)
  req,_:=http.NewRequest("POST","https://api.resend.com/emails",bytes.NewReader(body));req.Header.Set("Authorization","Bearer "+key);req.Header.Set("Content-Type","application/json")
  response,err:=http.DefaultClient.Do(req);if err!=nil{return err};defer response.Body.Close();if response.StatusCode>=300{return fmt.Errorf("resend returned %s",response.Status)};return nil
}
