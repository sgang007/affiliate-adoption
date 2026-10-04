# Deploying to Azure

Target shape — all managed, all autoscaling:

```
Azure Static Web Apps (React)  →  Azure Functions, Linux/Python 3.12 (FastAPI via AsgiFunctionApp)
                                        ↓
                          Azure Database for PostgreSQL (Flexible Server)
```

Prereqs: `az` CLI (logged in), `func` (Azure Functions Core Tools v4), Node 18+.

## 1. Resource group + Postgres

```bash
LOC=centralindia
RG=affiliate-portal
az group create -n $RG -l $LOC

az postgres flexible-server create -g $RG -n affportal-db -l $LOC \
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 \
  --admin-user portal --admin-password '<STRONG-PASSWORD>' \
  --database-name portal --public-access 0.0.0.0   # allows Azure services
DB_URL="postgresql+psycopg2://portal:<STRONG-PASSWORD>@affportal-db.postgres.database.azure.com:5432/portal?sslmode=require"
```

## 2. Function App (API)

```bash
az storage account create -n affportalstore -g $RG -l $LOC --sku Standard_LRS
az functionapp create -n affiliate-portal-api -g $RG \
  --storage-account affportalstore --consumption-plan-location $LOC \
  --runtime python --runtime-version 3.12 --functions-version 4 --os-type linux

az functionapp config appsettings set -n affiliate-portal-api -g $RG --settings \
  DATABASE_URL="$DB_URL" \
  JWT_SECRET="$(openssl rand -hex 32)" \
  PORTAL_BASE_URL="https://affiliate-portal-api.azurewebsites.net" \
  FRONTEND_URL="https://<your-swa>.azurestaticapps.net" \
  CORS_ORIGINS="https://<your-swa>.azurestaticapps.net" \
  ADMIN_EMAIL="admin@yourcompany.com" ADMIN_PASSWORD="<FIRST-LOGIN-PASSWORD>"

cd backend
func azure functionapp publish affiliate-portal-api
```

Tables are created and the admin account is bootstrapped automatically on
first startup (`init_db` in the FastAPI lifespan). Verify:
`curl https://affiliate-portal-api.azurewebsites.net/api/health`.

> **Higher scale:** move to the **Flex Consumption** plan
> (`az functionapp create --flexconsumption-location …`) for faster
> cold-starts and per-instance concurrency control. The app is stateless, so
> nothing else changes. For very high webhook volume, put outbound callback
> delivery on a Storage Queue (see docs/ARCHITECTURE.md).

## 3. Static Web App (frontend)

```bash
az staticwebapp create -n affiliate-portal-web -g $RG -l eastasia --sku Free
TOKEN=$(az staticwebapp secrets list -n affiliate-portal-web -g $RG --query properties.apiKey -o tsv)

cd frontend
echo 'VITE_API_URL=https://affiliate-portal-api.azurewebsites.net' > .env.production
npm ci && npm run build
npx @azure/static-web-apps-cli deploy ./dist --deployment-token $TOKEN --env production
```

Add an SPA fallback so client-side routes work — `frontend/staticwebapp.config.json`
is already in the repo and is picked up from `dist/` at deploy time.

Then update the Function App's `FRONTEND_URL`/`CORS_ORIGINS` with the real
SWA hostname (shown by `az staticwebapp show … --query defaultHostname`).

## 4. Wire up Meridian

For each product in the Admin console, copy the **webhook URL** and
**signing secret** into Meridian's product intelligence engine event config
(see docs/MERIDIAN_INTEGRATION.md for the payload contract).

## 5. Operations

- **Payout cycle:** Admin console → Payouts → *Run payout cycle* (monthly).
- **Secrets:** rotate per-product webhook secrets from the Admin console;
  rotate `JWT_SECRET` via app settings (invalidates sessions).
- **Monitoring:** Application Insights is enabled by default on the Function
  App; `host.json` already samples request telemetry.
- **Email invites:** set `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/SMTP_FROM`
  app settings (or use Azure Communication Services SMTP). Without SMTP the
  invite link is still returned in the UI for manual sharing.
