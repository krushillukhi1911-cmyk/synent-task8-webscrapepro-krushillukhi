# WebScrape Pro – Intelligent Website Data Extraction Platform

**WebScrape Pro** is an enterprise-grade website scraping, analytics, and data management platform. Built with Python / Flask, SQLite (via SQLAlchemy), and HTML/Bootstrap 5, it supports static parsing via BeautifulSoup and dynamic client-rendered SPA parsing via Playwright.

This project satisfies **Synent Technologies - Task 8 (Web Scraper)** while demonstrating portfolio-grade software design.

---

## Key Features

- 🔐 **Secure Session Auth**: Hashed credential registration and logins using Bcrypt with role-based dashboard filters.
- 🕷 **Dual Scraping Engines**:
  - **Static parser**: Fast HTTP session-manager parsing with BeautifulSoup.
  - **Dynamic parser**: Emulated Chromium headless browsing using Playwright. Simulates scroll events, handles random delays, emulates screen resolutions, and bypasses basic anti-bot blockers.
- 🧵 **Multi-threaded Background Task Manager**: Scraping tasks execute in concurrent background threads, enabling users to monitor progress via live terminal panels.
- 📡 **Real-time SSE Streams**: Server-Sent Events (SSE) stream backend scraper activity logs live directly onto the user dashboard.
- 🗄 **SQLAlchemy Schema**: Mapped tables for Users, Roles, Projects, ScraperTasks, DataRecords (JSON output format), ExportRecords, and AuditLogs.
- 📤 **Export Engine**: Generate formatted datasets in **CSV**, **JSON**, **Excel (multi-tab)**, **PDF (ReportLab summary reports)**, and **ZIP packages** for bulk downloads.
- 📊 **Aggregated Analytics API**: Live dashboard counts detailing success rate, records scraped, and execution speed.
- 🎨 **Glassmorphism Theme System**: Responsive dark/light theme switching with custom visual styles.

---

## Repository Structure

```text
synent-task8-webscrapepro-krushillukhi/
├── app/
│   ├── __init__.py           # Application Factory & Seeder
│   ├── config.py             # Config classes (dev, prod, test)
│   ├── extensions.py         # DB, Bcrypt, LoginManager declaration
│   ├── models.py             # DB Models & ORM relations
│   ├── routes/
│   │   ├── auth.py           # Login, Register, Profile handlers
│   │   ├── main.py           # Dashboard controllers
│   │   ├── scraper.py        # Task execution & log streams (SSE)
│   │   ├── api.py            # REST CRUD & analytics endpoints
│   │   └── exports.py        # Exporter download triggers
│   ├── services/
│   │   ├── task_manager.py   # Thread pool worker coordinator
│   │   ├── exporter.py       # JSON/CSV/Excel/PDF compile service
│   │   └── scraper/
│   │       ├── base_scraper.py
│   │       ├── static_scraper.py
│   │       └── dynamic_scraper.py
│   ├── static/
│   │   └── css/
│   │       └── style.css     # Dark/light theme & custom styling
│   └── templates/            # HTML Views (Login, Console, Progress, base)
├── tests/
│   └── test_basic.py         # App initialization & offline parser unit tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt          # Python package list
├── run.py                    # App runner
└── README.md                 # User guide documentation
```

---

## Database Schema (SQLite ORM)

```mermaid
erDiagram
    users ||--o{ projects : owns
    users ||--o{ audit_logs : generates
    roles ||--o{ users : assigns
    projects ||--o{ scraper_tasks : schedules
    projects ||--o{ data_records : stores
    projects ||--o{ export_records : indexes
    scraper_tasks ||--o{ data_records : extracts
    scraper_tasks ||--o{ export_records : exports
```

- **User**: Username, email, password_hash, role_id.
- **Role**: Administrator, Member.
- **Project**: Folder container grouping scraper tasks and data records.
- **ScraperTask**: URL, status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`), configuration JSON block.
- **DataRecord**: Holds raw scraped data dictionary (`meta`, `headings`, `paragraphs`, `links`, `contacts`, `media`, `custom_fields`).
- **ExportRecord**: Generated file path tracking size and formats.
- **AuditLog**: Keeps user activity registers.

---

## Installation & Setup

### Option 1: Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/krushillukhi/synent-task8-webscrapepro-krushillukhi.git
   cd synent-task8-webscrapepro-krushillukhi
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright Browsers** (Required for Dynamic JS-Rendering Scraper):
   ```bash
   playwright install
   ```

5. **Run the application**:
   ```bash
   python run.py
   ```
   Open `http://127.0.0.1:5000` in your web browser.

6. **Default Credentials**:
   - Username: `admin`
   - Password: `AdminPass123!`

---

### Option 2: Docker Compose Setup

Run the entire suite containerized inside Docker:

```bash
docker-compose up --build
```
This command compiles the app, configures all necessary Playwright system libraries, starts the server on port `5000`, and creates a local SQLite database that maps output data files safely to host directory volumes.

---

## Running Automated Tests

Run the offline unit tests using `unittest`:

```bash
python -m unittest tests/test_basic.py
```
*(Tests include database seeding checks, role verification, database ORM CRUD validations, and an isolated parser test checking headings/paragraphs/media/emails/tables against offline mock HTML content.)*
