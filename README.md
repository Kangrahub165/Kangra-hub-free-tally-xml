# Kangra Hub Free Tally XML

## Bank Statement PDF → Tally XML Converter

**Kangra Hub Free Tally XML** is a production-grade web application that converts digitally generated bank statement PDFs into accurate, import-ready, mathematically balanced Tally XML files for **TallyPrime** and **Tally.ERP 9**.

---

## Key Features

- **Double-Entry Accounting Balancing:** Generates Tally XML strictly matching standard import schemas (`SAMPLE.xml` specification) where total debits algebraically balance total credits to zero (`ISDEEMEDPOSITIVE` correctly assigned).
- **Running Balance Mathematical Audit:** Evaluates `Previous Balance + Credit - Debit = Current Balance` across every transaction row, flagging discrepancies for user review.
- **Multi-Line Narration Handling:** Automatically consolidates wrapped UPI, NEFT, and vendor descriptions into complete narration entries.
- **Intelligent Party-to-Ledger Mapping:** Extracts payee names and retains customized user ledger preferences across future statements.
- **38 Supported Banks:** Dedicated parsers and layout signatures for 38 leading Indian and multinational banks (Punjab National Bank, State Bank of India, HDFC Bank, ICICI Bank, Axis Bank, Kotak Mahindra Bank, Bank of Baroda, etc.).
- **50 Pages/Day Free Quota:** Enforced server-side with automatic midnight reset based on the `Asia/Kolkata` timezone. Upload quota pre-checks prevent partial conversions.
- **Admin Control Panel:** Manage users, grant/revoke unlimited conversion access, monitor all platform jobs, toggle global Free/Paid modes, test statements in the diagnostic sandbox, and configure system settings.
- **Admin "Buy Me a Coffee" Section:** Small, non-intrusive card visible exclusively to the administrator, displaying the supplied official QR code (`buy a coffee/googlepay_qr.png`) for voluntary project support.
- **Production-Grade SEO:** Unique metadata per page, canonical URLs, robots.txt, sitemap.xml, Open Graph, Twitter cards, and JSON-LD structured data with official social profile links.

---

## Architecture Overview

Built around four independent, decoupled engines:

```text
1. PDF Intelligence Engine (pypdf, layout coordinates, password decryptor, validation)
2. Bank / Statement Parser Engine (Modular plugin/adapter registry for 38+ banks)
3. Accounting & Ledger Engine (Party extraction, fuzzy mapping, voucher classifier)
4. Tally XML Engine (Conforming strictly to SAMPLE.xml double-entry specifications)
```

---

## Project Structure

```text
KANGRA HUB FREE TALLY XML/
├── SAMPLE.xml                         (Reference Tally XML)
├── logo.webp                          (Official Kangra Hub logo)
├── favicon_io/                        (Official icons & favicons)
├── buy a coffee/googlepay_qr.png      (Supplied owner QR code)
│
├── database/
│   └── supabase_schema.sql            (Complete PostgreSQL DDL, RLS, functions, triggers, seed data)
│
├── backend/
│   ├── app/
│   │   ├── api/                       (FastAPI REST endpoints: conversions, banks, usage, admin)
│   │   ├── core/                      (Settings, structured exceptions, auth & security)
│   │   ├── pdf/                       (PDF validator, text & layout extractor)
│   │   ├── detector/                  (Bank signatures and multi-strategy detector)
│   │   ├── parsers/                   (BaseStatementParser, registry, PNB, generic standard)
│   │   ├── transactions/              (CanonicalStatement model, normalizer, validator)
│   │   ├── accounting/                (LedgerMapper, voucher classifier)
│   │   ├── tally/                     (TallyXMLGenerator, xml_validator)
│   │   └── utils/                     (Temporary file auto-purger, sanitized logger)
│   ├── tests/                         (Automated test suite: XML, parsers, usage, normalizer)
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── public/                        (Static assets: logo, QR code, manifest, favicons)
│   ├── src/
│   │   ├── app/                       (Next.js App Router: landing, auth, dashboard, convert, admin)
│   │   ├── components/                (Header, Footer, BuyCoffeeCard, JsonLd)
│   │   └── lib/                       (API client, SEO configuration)
│   └── package.json
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start & Installation

### 1. Prerequisites
- **Python:** 3.12+
- **Node.js:** 18+ (tested with Node v24)
- **Supabase Account:** (or run in local dev mode with mock sessions)

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your Supabase URL and keys if using live cloud authentication.

### 3. Setup Supabase Database
Open the **SQL Editor** in your Supabase dashboard and run the entire contents of:
```text
database/supabase_schema.sql
```
This sets up all tables, row-level security (RLS) policies, triggers, daily usage calculation procedures, and seed data for the 38 banks.

### 4. Install & Run Backend (FastAPI)
```bash
cd backend
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn main:app --reload --port 8000
```
Backend API will be live at `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### 5. Install & Run Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Frontend will be live at `http://localhost:3000`.

---

## Running Automated Tests

Run the backend test suite:
```bash
py -3.12 -m pytest -v backend/tests/
```
All tests verify:
- Tally XML output format against `SAMPLE.xml` requirements.
- Algebraic zero-balance double entry (`sum(amounts) == 0`).
- Date parsing across Indian & ISO formats.
- Amount parsing with `Decimal` precision.
- Daily 50-page quota enforcement and blocking.
- Unlimited user and admin bypass.
- Bank detector signatures and balance math validation.

---

## Admin Portal & The Buy Me a Coffee Widget

To access the Admin Console:
1. Log into `http://localhost:3000/admin/login` using your administrator account (`admin@tallyxml.in`).
2. Navigate to `http://localhost:3000/admin`.
3. You can:
   - Toggle the site between **FREE TO EVERYONE** and **PAID SERVICE**.
   - Manage users and grant unlimited page quotas.
   - Monitor live conversion logs.
   - Test bank statement statements in the **Testing Lab** without quota consumption.
   - Access the **Buy Me a Coffee** card. Clicking the button displays the modal with the official owner QR code (`buy-a-coffee/googlepay_qr.png`) and UPI payment option.

---

## Search Engine Optimization (SEO)

The site is built with SEO readiness:
- **Canonical URLs:** dynamically rendered based on `NEXT_PUBLIC_SITE_URL`.
- **Robots.txt:** accessible at `/robots.txt` (allows public pages, blocks private routes).
- **XML Sitemap:** auto-generated at `/sitemap.xml`.
- **Social Previews:** Open Graph and Twitter large summary cards configured.
- **Structured Data:** JSON-LD for `Organization` with exact Kangra Hub social links, `WebApplication`, and `FAQPage`.

### Submitting Sitemap to Search Engines:
1. **Google Search Console:**
   - Add your property (e.g. `https://tally.kangrahub.com`).
   - Add verification meta tag or DNS TXT record.
   - Under **Sitemaps**, submit `https://tally.kangrahub.com/sitemap.xml`.
2. **Bing Webmaster Tools:**
   - Add property and submit `https://tally.kangrahub.com/sitemap.xml`.

---

## Adding New Bank Parsers

To add a new bank parser without modifying existing code:
1. Create a parser class inheriting `BaseStatementParser` in `backend/app/parsers/`.
2. Implement `can_parse(doc)` and `parse(doc)`.
3. Register the parser in `backend/app/parsers/registry.py`.
4. Add signature keywords to `backend/app/detector/signatures.py`.
5. Add bank details in `database/supabase_schema.sql`.

---

## License & Trademarks

Kangra Hub Free Tally XML is an independent conversion tool.
*Tally*, *TallyPrime*, and *Tally.ERP 9* are registered trademarks of Tally Solutions Pvt. Ltd.
