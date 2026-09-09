# Project History and Recovery Guide

This file preserves the working context needed to continue the SME Retail Intelligence project after the local folder is removed. GitHub stores the source code, documentation, screenshots, and commit history. The Codex application stores the original chat separately, so the raw conversation is not part of Git itself.

## Project Goal

Build a lightweight CSV first retail and inventory platform for small shops that do not use Shopify or an ERP. Owners can upload sales and inventory files, receive demand forecasts for each SKU, view stock insights, and ask safe natural language questions about their data.

## Main Requirements

- Use FastAPI and PostgreSQL as the system of record.
- Support organization scoped owner and staff accounts with password hashing and JWT access tokens.
- Accept sales and inventory CSV files, validate rows, report errors, and prevent duplicate imports.
- Produce forecasts for 7 to 30 days using Prophet when enough history exists and exponential smoothing for shorter histories.
- Show low stock, overstock, top mover, bottom mover, and reorder insights.
- Provide a read only natural language assistant with Gemini as the optional primary provider and Groq as the fallback.
- Validate generated SQL with sqlglot, allow only approved reads, add the organization condition on the server, and audit accepted and rejected requests.
- Provide a Next.js owner dashboard and an Angular staff workspace.
- Use a Go worker for queued imports and weekly digest processing.
- Run locally with Docker Compose and include Kubernetes files for a k3s deployment.
- Include tests, GitHub Actions, monitoring, backup instructions, sample CSV files, and clear setup documentation.

## Request and Decision History

1. The project began as a planning task. Development was held until explicit approval was given.
2. The approved implementation plan established the FastAPI, Go, Next.js, Angular, PostgreSQL, Docker, and Kubernetes architecture.
3. Local setup work installed the required dependencies, started the services, and explained how to run and stop the project.
4. The owner and staff interfaces were refined into a minimal green themed design with clearer navigation and small animations. Unwanted placeholder wording and the horizontal statistics strip were removed.
5. The repository was created and connected to GitHub under the name `Sme-Retail-Intelligence`. The README and repository description were written in simple language.
6. GitHub Actions failures were reviewed and corrected until the earlier published revision passed all four continuous integration jobs.
7. The separate portfolio repository and resume were updated in their own repository. That work is intentionally not copied into this retail repository.
8. A final system audit tested source builds, dependencies, browser journeys, APIs, roles, tenant isolation, CSV processing, forecasting, safe chat, Docker, PostgreSQL restore, worker metrics, logs, and Kubernetes files.
9. The audit found and corrected the low stock wording rule, outdated Python and Go dependencies, local hostname access, the Angular root redirect, Angular asynchronous rendering, and small browser polish issues.
10. The final report and page screenshots were added under `docs` so the verified behavior can be reviewed without running the system.

## Current Verified State

The local release passed the following checks on 4 September 2026:

- 7 FastAPI tests passed.
- 50 authenticated API workflow checks passed.
- Go tests passed.
- Python and Go vulnerability scans reported no known or reachable vulnerabilities at test time.
- Next.js and Angular production builds passed with zero npm vulnerabilities.
- All five application containers reported healthy status.
- 30 Kubernetes resources passed strict schema validation with no invalid resources or errors. One cert manager resource was skipped because its custom schema was not bundled with the validator.
- A PostgreSQL custom format backup was restored into a temporary database. The restored row counts matched the source database.
- The Go worker completed a queued CSV import and reported zero worker errors.
- The final browser run completed 14 views without console errors.
- The recent container log scan found no error, fatal, panic, or traceback entries.

The detailed evidence is in `docs/SME-Retail-Intelligence-Full-System-Test-Report.docx`. Page screenshots are stored in `docs/evidence`.

## Services and Local Addresses

| Service | Technology | Local address | Purpose |
| --- | --- | --- | --- |
| Owner dashboard | Next.js | http://localhost:3000 | Inventory, insights, forecasts, imports, and chat |
| Staff workspace | Angular and Nginx | http://localhost:4200/admin/ | Team access, import review, uploads, and settings |
| API | FastAPI | http://localhost:8000 | Authentication, data, forecasting, chat, health, and metrics |
| Database | PostgreSQL | Internal Docker network | Tenant scoped system of record |
| Worker | Go | Internal Docker network | Queued CSV processing and weekly digest execution |

The interactive API page is at http://localhost:8000/docs and metrics are at http://localhost:8000/metrics.

## Restore the Project on Any Computer

Install Git and Docker Desktop, then run:

```powershell
git clone https://github.com/SarmadAli8824/Sme-Retail-Intelligence.git
Set-Location Sme-Retail-Intelligence
Copy-Item .env.example .env
docker compose up --build
```

Use the local demo account:

```text
Email: owner@demo.example
Password: RetailDemo123!
```

Stop the project while keeping database data:

```powershell
docker compose down
```

Remove only the running containers and local database volume when a completely fresh start is required:

```powershell
docker compose down --volumes
```

## Continue Work With Codex

Clone the repository first, open the cloned folder in Codex, and start a new task with this instruction:

```text
Read README.md and docs/PROJECT-HISTORY-AND-RECOVERY.md completely. Inspect the current Git status and recent commits before changing anything. Continue the SME Retail Intelligence project from the documented state and preserve the existing architecture and writing style.
```

The current Codex task can still be opened from the Codex sidebar after the local repository is removed. A new task will not automatically inherit the old messages, so this recovery file is the durable project handoff.

## Production Work That Still Needs Accounts

The repository contains production files, but these steps cannot be verified without credentials and account access:

- Create the Oracle Cloud ARM virtual machine and complete the k3s rollout.
- Configure DuckDNS and issue the live Let's Encrypt certificate.
- Upload encrypted backups to OCI Object Storage.
- Send a real weekly message through Resend.
- Test live Gemini and Groq provider calls.
- Add the public HTTPS address and unlisted YouTube walkthrough to the README.

Do not place any production password, API key, kubeconfig, or private token in GitHub. Store those values in GitHub Secrets and the production secret store.

## Safe Local Deletion Checklist

Before deleting the local folder, confirm all of the following:

1. `git status` shows no uncommitted files that matter.
2. `git log -1` shows the same final commit locally and on GitHub.
3. The GitHub repository opens and contains `README.md`, `docs`, `apps`, `services`, and `infra`.
4. The final GitHub Actions run is green.
5. Any local only production credentials have been copied to a password manager. They are intentionally excluded from GitHub.

After these checks pass, the project folder can be deleted and restored later by cloning the GitHub repository. Docker images, stopped containers, volumes, and build cache use space outside the repository folder. Remove those separately through Docker Desktop only when they are no longer needed.
