# k3s / Oracle Always Free deployment

1. Provision an ARM Oracle Always Free VM with a reserved public IP, open TCP 80/443, and install k3s.
2. Install `cert-manager`, create a DuckDNS hostname, and replace every `REPLACE` value. Use DuckDNS's update URL in a host cron job so its address stays current.
3. Create `postgres-secrets` and `backup-secrets` outside version control, then apply the manifests in this directory.
4. Configure OCI CLI credentials in the backup image; backups must run `pg_dump | gpg --symmetric` then upload to OCI Object Storage.
5. Test recovery before declaring production ready: download one encrypted dump, decrypt it, restore into an isolated PostgreSQL instance, and run a tenant-scoped dashboard query.

Use GitHub Actions repository secrets for `KUBECONFIG`, OCI/registry credentials, Gemini/Groq, Resend, database, and JWT values. Do not commit production secrets.

