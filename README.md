# Chat with SQL

A Streamlit assistant that turns plain-language questions into read-only SQL.
It works immediately with the included SQLite sample and can connect to an
existing PostgreSQL or MySQL database.

<p>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Streamlit 1.62" src="https://img.shields.io/badge/Streamlit-1.62-FF4B4B?logo=streamlit&logoColor=white">
  <img alt="LangChain 1.3" src="https://img.shields.io/badge/LangChain-1.3-1C3C3C?logo=langchain&logoColor=white">
  <img alt="Groq powered" src="https://img.shields.io/badge/Groq-Powered-F55036?logo=groq&logoColor=white">
  <img alt="Read-only SQL" src="https://img.shields.io/badge/SQL-Read--only-4479A1?logo=database&logoColor=white">
</p>

## Features

- Natural-language SQL analysis powered by LangChain and Groq
- SQLite, PostgreSQL, and MySQL connections
- PostgreSQL schema and SSL-mode selection
- Read-only SQLite and PostgreSQL sessions, plus read-only agent instructions
- Project-owned guarded SQL tools with no deprecated community dependency
- Connection values from the sidebar or environment variables
- Follow-up-aware chat history kept separately for each database connection
- Table discovery, database-specific starter prompts, and clear errors
- Cached database connections and agents for responsive Streamlit reruns

## Quick start

Python 3.11 or 3.12 is recommended.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Add your Groq API key to `.env`, or enter it in the sidebar:

```env
GROQ_API_KEY=gsk_your_key_here
```

Open <http://localhost:8501> if Streamlit does not open it automatically.

## Connect PostgreSQL

1. Select **PostgreSQL** in the sidebar.
2. Enter the host, port, username, password, database, and schema.
3. For a hosted database, choose the SSL mode required by your provider;
   **require** is a common choice.
4. Select **Apply connection**. When the status shows **Connected**, ask a
   question in the chat box.

You can prefill the form from `.env`:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=readonly_user
POSTGRES_PASSWORD=change_me
POSTGRES_DATABASE=analytics
POSTGRES_SCHEMA=public
POSTGRES_SSLMODE=prefer
```

For hosted services, use the individual values from the provider's connection
details. Do not paste a complete `postgresql://...` URL into the Host field.

The app asks PostgreSQL to make every connection read-only. You should still
create a dedicated login with only `CONNECT`, `USAGE`, and `SELECT` access:

```sql
CREATE ROLE chat_sql_reader LOGIN PASSWORD 'replace_with_a_strong_password';
GRANT CONNECT ON DATABASE analytics TO chat_sql_reader;
GRANT USAGE ON SCHEMA public TO chat_sql_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO chat_sql_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO chat_sql_reader;
```

Run those grants as a database administrator, replacing the database, schema,
role, and password with your own values. If you cannot create a role, use an
existing account that has read-only access.

## Connect MySQL

Select **MySQL** and enter the connection details in the sidebar. The matching
environment variables are `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
`MYSQL_PASSWORD`, and `MYSQL_DATABASE`. Use a database account with `SELECT`
and metadata-reading permissions.

## Rebuild the SQLite sample

The initializer is idempotent and does not duplicate seed rows.

```powershell
python sqlite.py
```

## Project structure

```text
chat_sql/
|-- .streamlit/config.toml  # Streamlit theme
|-- .env.example           # Safe environment template
|-- .gitignore             # Excludes secrets and local environments
|-- app.py                 # Streamlit chat application
|-- database.py            # Guarded schema inspection and read-only queries
|-- requirements.txt       # Python dependencies
|-- sqlite.py              # SQLite sample initializer
`-- Student.db             # Included sample data
```

## Troubleshooting

**The virtual environment no longer starts**

A Python virtual environment stores the path of the Python installation that
created it. If Python was removed or moved, delete and recreate only `.venv`,
then reinstall `requirements.txt`.

**The chat box is disabled**

Add a valid Groq API key and make sure the connection status says **Connected**.

**PostgreSQL connection failed**

Check the host, port, database, schema, credentials, network allowlist, and SSL
mode. A local PostgreSQL server usually uses port `5432`; hosted providers may
require `require` or `verify-full` SSL.

**No PostgreSQL tables appear**

Confirm that the selected schema is correct and that the login has `USAGE` on
the schema and `SELECT` on its tables.

**PowerShell blocks environment activation**

Activation is optional. After creating a valid environment, run its executables
directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

## Security

- SQLite is opened with `mode=ro`.
- PostgreSQL connections set `default_transaction_read_only=on`.
- API keys and database passwords are masked and removed from displayed errors.
- `.env` and Streamlit secrets are excluded by `.gitignore`.
- A database-level read-only account remains the strongest protection.

## References

Use the compact links below to open the official documentation for the main
tools and databases used by this project.

<p>
  <a href="https://docs.streamlit.io/" title="Streamlit documentation">
    <img alt="Streamlit Docs" src="https://img.shields.io/badge/Streamlit-Docs-FF4B4B?logo=streamlit&logoColor=white">
  </a>
  <a href="https://docs.langchain.com/" title="LangChain documentation">
    <img alt="LangChain Docs" src="https://img.shields.io/badge/LangChain-Docs-1C3C3C?logo=langchain&logoColor=white">
  </a>
  <a href="https://console.groq.com/docs" title="Groq documentation">
    <img alt="Groq Docs" src="https://img.shields.io/badge/Groq-Docs-F55036?logo=groq&logoColor=white">
  </a>
  <a href="https://docs.sqlalchemy.org/" title="SQLAlchemy documentation">
    <img alt="SQLAlchemy Docs" src="https://img.shields.io/badge/SQLAlchemy-Docs-D71F00?logo=sqlalchemy&logoColor=white">
  </a>
  <a href="https://www.sqlite.org/docs.html" title="SQLite documentation">
    <img alt="SQLite Docs" src="https://img.shields.io/badge/SQLite-Docs-003B57?logo=sqlite&logoColor=white">
  </a>
  <a href="https://www.postgresql.org/docs/" title="PostgreSQL documentation">
    <img alt="PostgreSQL Docs" src="https://img.shields.io/badge/PostgreSQL-Docs-4169E1?logo=postgresql&logoColor=white">
  </a>
  <a href="https://dev.mysql.com/doc/" title="MySQL documentation">
    <img alt="MySQL Docs" src="https://img.shields.io/badge/MySQL-Docs-4479A1?logo=mysql&logoColor=white">
  </a>
</p>
