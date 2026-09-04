package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"os"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
)

var processedUploads atomic.Int64
var sentDigests atomic.Int64
var workerErrors atomic.Int64

type recipient struct {
	OrgID string
	Email string
	Name  string
}

type uploadJob struct {
	ID      string
	OrgID   string
	Kind    string
	Payload []byte
}

type salesRow struct {
	Date         string   `json:"date"`
	SKU          string   `json:"sku"`
	QuantitySold float64  `json:"quantity_sold"`
	UnitPrice    *float64 `json:"unit_price"`
	ProductName  *string  `json:"product_name"`
	Category     *string  `json:"category"`
}

type inventoryRow struct {
	SKU          string   `json:"sku"`
	StockOnHand  float64  `json:"stock_on_hand"`
	ReorderPoint *float64 `json:"reorder_point"`
	ProductName  *string  `json:"product_name"`
	Category     *string  `json:"category"`
	UnitCost     *float64 `json:"unit_cost"`
}

type digestStats struct {
	UnitsSold int
	LowStock  int
	TotalSKUs int
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "health" {
		return
	}
	go serveHealth()
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		panic("DATABASE_URL is required")
	}
	ctx := context.Background()
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		panic(err)
	}
	defer conn.Close(ctx)

	if os.Getenv("WORKER_RUN_ONCE") == "true" {
		if err := process(ctx, conn); err != nil {
			panic(err)
		}
		return
	}
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	for {
		if err := process(ctx, conn); err != nil {
			workerErrors.Add(1)
			fmt.Printf("worker error: %v\n", err)
		}
		<-ticker.C
	}
}

func process(ctx context.Context, conn *pgx.Conn) error {
	if err := processUploadJobs(ctx, conn); err != nil {
		return err
	}
	return sendWeeklyDigests(ctx, conn)
}

func processUploadJobs(ctx context.Context, conn *pgx.Conn) error {
	tx, err := conn.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	rows, err := tx.Query(ctx, `SELECT id,organization_id,kind,payload FROM uploads WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 20`)
	if err != nil {
		return err
	}
	jobs := make([]uploadJob, 0)
	for rows.Next() {
		var job uploadJob
		if err := rows.Scan(&job.ID, &job.OrgID, &job.Kind, &job.Payload); err != nil {
			rows.Close()
			return err
		}
		jobs = append(jobs, job)
	}
	rows.Close()

	for _, job := range jobs {
		processed, jobErr := processUpload(ctx, tx, job)
		if jobErr != nil {
			if _, err := tx.Exec(ctx, `UPDATE uploads SET status='failed',completed_at=now() WHERE id=$1`, job.ID); err != nil {
				return err
			}
			continue
		}
		if _, err := tx.Exec(ctx, `UPDATE uploads SET status='completed',rows_processed=$2,payload=NULL,completed_at=now() WHERE id=$1`, job.ID, processed); err != nil {
			return err
		}
		processedUploads.Add(1)
	}
	return tx.Commit(ctx)
}

func processUpload(ctx context.Context, tx pgx.Tx, job uploadJob) (int, error) {
	if job.Kind == "sales" {
		var records []salesRow
		if err := json.Unmarshal(job.Payload, &records); err != nil {
			return 0, err
		}
		for _, row := range records {
			_, err := tx.Exec(ctx, `INSERT INTO sales(id,organization_id,date,sku,quantity_sold,unit_price,product_name,category,upload_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT DO NOTHING`, identifier(), job.OrgID, row.Date, row.SKU, row.QuantitySold, row.UnitPrice, row.ProductName, row.Category, job.ID)
			if err != nil {
				return 0, err
			}
		}
		return len(records), nil
	}
	if job.Kind == "inventory" {
		var records []inventoryRow
		if err := json.Unmarshal(job.Payload, &records); err != nil {
			return 0, err
		}
		for _, row := range records {
			_, err := tx.Exec(ctx, `INSERT INTO inventory(id,organization_id,sku,stock_on_hand,reorder_point,product_name,category,unit_cost,updated_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,now()) ON CONFLICT(organization_id,sku) DO UPDATE SET stock_on_hand=excluded.stock_on_hand,reorder_point=excluded.reorder_point,product_name=excluded.product_name,category=excluded.category,unit_cost=excluded.unit_cost,updated_at=now()`, identifier(), job.OrgID, row.SKU, row.StockOnHand, row.ReorderPoint, row.ProductName, row.Category, row.UnitCost)
			if err != nil {
				return 0, err
			}
		}
		return len(records), nil
	}
	return 0, fmt.Errorf("unsupported upload kind %q", job.Kind)
}

func sendWeeklyDigests(ctx context.Context, conn *pgx.Conn) error {
	rows, err := conn.Query(ctx, `SELECT u.organization_id,u.email,o.name FROM users u JOIN organizations o ON o.id=u.organization_id WHERE u.role='owner' AND u.is_active=true AND o.digest_enabled=true AND NOT EXISTS (SELECT 1 FROM digest_runs d WHERE d.organization_id=u.organization_id AND d.created_at >= date_trunc('week',now()))`)
	if err != nil {
		return err
	}
	recipients := make([]recipient, 0)
	for rows.Next() {
		var item recipient
		if err := rows.Scan(&item.OrgID, &item.Email, &item.Name); err != nil {
			rows.Close()
			return err
		}
		recipients = append(recipients, item)
	}
	rows.Close()
	for _, item := range recipients {
		var stats digestStats
		if err := conn.QueryRow(ctx, `SELECT COALESCE((SELECT SUM(quantity_sold) FROM sales WHERE organization_id=$1 AND date >= current_date-7),0)::int,(SELECT COUNT(*) FROM inventory WHERE organization_id=$1 AND stock_on_hand < COALESCE(reorder_point,10)),(SELECT COUNT(*) FROM inventory WHERE organization_id=$1)`, item.OrgID).Scan(&stats.UnitsSold, &stats.LowStock, &stats.TotalSKUs); err != nil {
			return err
		}
		if err := sendDigest(item, stats); err != nil {
			return err
		}
		_, err = conn.Exec(ctx, `INSERT INTO digest_runs(id,organization_id,status,sent_at,created_at) VALUES($1,$2,'sent',now(),now())`, identifier(), item.OrgID)
		if err != nil {
			return err
		}
		sentDigests.Add(1)
	}
	return nil
}

func digestHTML(r recipient, stats digestStats) string {
	const source = `<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#18281f"><div style="background:#183d2d;color:white;padding:28px;border-radius:16px 16px 0 0"><small>RETAIL INTELLIGENCE</small><h1 style="margin:8px 0 0">Your weekly shop digest</h1></div><div style="padding:28px;border:1px solid #dfe7dc"><p>Here is the latest picture for {{.Name}}.</p><table width="100%"><tr><td><b>{{.Stats.UnitsSold}}</b><br><small>Units sold in 7 days</small></td><td><b>{{.Stats.LowStock}}</b><br><small>Low stock items</small></td><td><b>{{.Stats.TotalSKUs}}</b><br><small>Tracked SKUs</small></td></tr></table><p style="margin-top:28px">Open Retail Intelligence to review forecasts, movers, and reorder suggestions.</p></div></div>`
	tmpl := template.Must(template.New("digest").Parse(source))
	var output bytes.Buffer
	_ = tmpl.Execute(&output, struct {
		Name  string
		Stats digestStats
	}{r.Name, stats})
	return output.String()
}

func sendDigest(r recipient, stats digestStats) error {
	key := os.Getenv("RESEND_API_KEY")
	if key == "" {
		fmt.Printf("digest dry run for %s: %d units, %d low stock\n", r.Email, stats.UnitsSold, stats.LowStock)
		return nil
	}
	from := os.Getenv("RESEND_FROM")
	if from == "" {
		from = "onboarding@resend.dev"
	}
	payload := map[string]any{"from": from, "to": []string{r.Email}, "subject": "Your weekly retail intelligence digest", "html": digestHTML(r, stats), "text": fmt.Sprintf("%s weekly digest: %d units sold, %d low-stock items, %d tracked SKUs.", r.Name, stats.UnitsSold, stats.LowStock, stats.TotalSKUs)}
	body, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", "https://api.resend.com/emails", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+key)
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 12 * time.Second}
	response, err := client.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode >= 300 {
		return fmt.Errorf("resend returned %s", response.Status)
	}
	return nil
}

func identifier() string {
	value := make([]byte, 16)
	if _, err := rand.Read(value); err != nil {
		return fmt.Sprintf("worker-%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(value)
}

func serveHealth() {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		_, _ = writer.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("/metrics", func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Type", "text/plain; version=0.0.4")
		_, _ = fmt.Fprintf(writer, "retail_worker_uploads_processed_total %d\nretail_worker_digests_sent_total %d\nretail_worker_errors_total %d\n", processedUploads.Load(), sentDigests.Load(), workerErrors.Load())
	})
	server := &http.Server{Addr: ":8080", Handler: mux, ReadHeaderTimeout: 3 * time.Second}
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		fmt.Printf("health server error: %v\n", err)
	}
}
