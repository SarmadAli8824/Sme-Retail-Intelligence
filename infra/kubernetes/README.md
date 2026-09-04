# Oracle Cloud k3s Deployment

These manifests deploy the platform to one ARM based Oracle Cloud Always Free VM. Complete the values marked `REPLACE` before the first deployment. Never commit the rendered secret file.

## 1. Prepare the VM

Create an Ubuntu ARM VM, reserve its public IP, and allow inbound TCP traffic on ports 22, 80, and 443 in both the Oracle network security rules and the host firewall.

Install k3s and cert manager:

```bash
curl -sfL https://get.k3s.io | sh -
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=180s
```

Create a DuckDNS hostname and keep it pointed to the reserved public IP. A simple host cron entry can update it every five minutes:

```text
*/5 * * * * curl -fsS "https://www.duckdns.org/update?domains=YOUR_SUBDOMAIN&token=YOUR_TOKEN&ip="
```

## 2. Create Configuration and Secrets

Copy `config.yaml` to a temporary location outside the repository. Replace the database passwords, JWT secret, backup passphrase, OCI Object Storage upload URL, Grafana password, and optional provider keys. Replace the public hostname in the ConfigMap.

Apply the namespace and private configuration once:

```bash
kubectl apply -f namespace.yaml
kubectl apply -f /secure/location/config.production.yaml
```

The API uses the SQLAlchemy database URL. The Go worker, backup job, and PostgreSQL exporter use ordinary PostgreSQL URLs. The template keeps these values separate so each service receives a compatible connection string.

## 3. Configure GitHub

Add these secrets to the repository production environment:

- `KUBECONFIG`: base64 encoded k3s configuration with the server address changed from localhost to the public VM address
- `DUCKDNS_SUBDOMAIN`: hostname without `.duckdns.org`
- `TLS_EMAIL`: address used for Let's Encrypt notices

GitHub Actions builds ARM images, publishes them to GitHub Container Registry, renders public manifest values, applies the manifests, pins every service to the commit image, and waits for each rollout.

## 4. Verify the Release

```bash
kubectl -n retail-intelligence get pods,svc,ingress,hpa,cronjob
kubectl -n retail-intelligence rollout status deployment/api
curl -fsS https://YOUR_SUBDOMAIN.duckdns.org/health
```

The owner application is available at `/`, the staff application at `/admin/`, API documentation at `/docs`, and Grafana at `/grafana/`.

## Monitoring

Prometheus scrapes FastAPI request counters, Go worker upload and digest counters, and PostgreSQL exporter metrics. Grafana is provisioned with Prometheus as its default data source. Change the Grafana password in the private configuration before deployment.

Useful initial panels include:

- `retail_api_requests_total` grouped by route and status
- `retail_worker_uploads_processed_total`
- `retail_worker_digests_sent_total`
- `retail_worker_errors_total`
- `pg_up`
- PostgreSQL connection and transaction metrics

## Backup and Restore Drill

The nightly job runs `pg_dump`, encrypts the dump with AES256 through GPG, and uploads it using an OCI Object Storage preauthenticated request URL.

Perform this drill before treating backups as complete:

1. Download one encrypted backup from OCI Object Storage.
2. Start a separate empty PostgreSQL database that is not the production database.
3. Run the backup image with `/restore.sh` as its entrypoint and mount the downloaded file.
4. Sign in with a test account and run the dashboard query to confirm tenant data was restored.
5. Record the drill date and backup object name in the operations log.

Example restore command:

```bash
docker run --rm \
  --network host \
  -v "$PWD/retail-backup.sql.gpg:/restore/backup.sql.gpg:ro" \
  -e DATABASE_URL="postgres://restore_user:password@localhost:5432/restore_test" \
  -e GPG_PASSPHRASE="your backup passphrase" \
  -e SOURCE_GPG_FILE="/restore/backup.sql.gpg" \
  --entrypoint /restore.sh \
  ghcr.io/YOUR_ACCOUNT/retail-pg-backup:latest
```

## Resource Notes

The manifests use conservative requests and limits for one small VM. Prometheus keeps seven days of metrics in its pod. PostgreSQL requests a 20 GB persistent volume. Review actual memory, disk, and CPU use before increasing HPA replica limits.
