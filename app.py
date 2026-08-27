"""Streamlit application for chatting with SQLite, PostgreSQL, or MySQL."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from sqlalchemy import URL, create_engine

from database import ReadOnlySQLDatabase


APP_DIR = Path(__file__).resolve().parent
SQLITE_DATABASE = APP_DIR / "Student.db"
SQLITE_LABEL = "SQLite sample"
POSTGRESQL_LABEL = "PostgreSQL"
MYSQL_LABEL = "MySQL"
DEFAULT_MODEL = "openai/gpt-oss-120b"

MODEL_OPTIONS = {
    "GPT-OSS 120B - best quality": "openai/gpt-oss-120b",
    "GPT-OSS 20B - faster": "openai/gpt-oss-20b",
}

SAMPLE_QUESTIONS = {
    ":material/groups: Show every user": "Show all users in the database.",
    ":material/location_city: Users by city": (
        "Count the users in each city and sort from highest to lowest."
    ),
    ":material/monitoring: Age summary": (
        "What are the minimum, maximum, and average ages of the users?"
    ),
}

REMOTE_SAMPLE_QUESTIONS = {
    ":material/table_view: Describe the database": (
        "List the available tables and briefly describe what each table stores."
    ),
    ":material/schema: Explain relationships": (
        "Explain the important relationships between the available tables."
    ),
    ":material/analytics: Suggest analyses": (
        "Based on the available schema, suggest five useful questions I can ask."
    ),
}

READ_ONLY_AGENT_PREFIX = """
You are an agent designed to answer questions about a SQL database.
Create syntactically correct {dialect} queries, execute them with the available
tools, inspect the results, and give a concise answer in plain language.
Unless the user requests a specific number of rows, limit results to at most
{top_k} rows. Select only the columns needed to answer the question.

This application is read-only. Never execute INSERT, UPDATE, DELETE, DROP,
ALTER, TRUNCATE, CREATE, REPLACE, GRANT, REVOKE, or any other statement that
changes data or database structure. If asked to modify data, explain that the
application supports read-only analysis. Always inspect the available tables
and their schemas instead of guessing names. If a query fails, correct it and
try again with a simpler query. Use the conversation history to resolve
follow-up requests, including references such as "that table" or "all rows".
If a database tool still fails, report its exact error instead of replacing it
with a generic message. Do not invent results that were not returned by the
database.
""".strip()


load_dotenv(APP_DIR / ".env")

st.set_page_config(
    page_title="Chat with SQL",
    page_icon=":material/database:",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("conversation_store", {})


@st.cache_resource(ttl="2h", max_entries=10, show_spinner=False)
def configure_database(
    database_type: str,
    host: str = "",
    port: int = 3306,
    username: str = "",
    password: str = "",
    database_name: str = "",
    schema: str = "",
    ssl_mode: str = "prefer",
) -> ReadOnlySQLDatabase:
    """Create and cache a read-only connection for a supported database."""
    if database_type == SQLITE_LABEL:
        if not SQLITE_DATABASE.exists():
            raise FileNotFoundError(
                "Student.db was not found. Run `python sqlite.py` to create it."
            )

        def create_read_only_connection() -> sqlite3.Connection:
            return sqlite3.connect(
                f"file:{SQLITE_DATABASE.as_posix()}?mode=ro",
                uri=True,
                check_same_thread=False,
            )

        engine = create_engine("sqlite://", creator=create_read_only_connection)
    elif database_type == POSTGRESQL_LABEL:
        connection_url = URL.create(
            drivername="postgresql+psycopg",
            username=username,
            password=password or None,
            host=host,
            port=port,
            database=database_name,
        )
        engine = create_engine(
            connection_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "connect_timeout": 10,
                "sslmode": ssl_mode,
                "options": "-c default_transaction_read_only=on",
            },
        )
    else:
        connection_url = URL.create(
            drivername="mysql+mysqlconnector",
            username=username,
            password=password or None,
            host=host,
            port=port,
            database=database_name,
        )
        engine = create_engine(
            connection_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={"connection_timeout": 10},
        )

    return ReadOnlySQLDatabase(engine, schema=schema or None)


def create_database_tools(database: ReadOnlySQLDatabase):
    """Create narrowly scoped read-only tools for one database connection."""

    @tool("sql_db_list_tables")
    def list_tables() -> str:
        """List all tables and views available in the configured schema."""
        names = database.get_usable_table_names()
        return ", ".join(names) if names else "No tables are available."

    @tool("sql_db_schema")
    def describe_tables(table_names: str = "") -> str:
        """Describe columns and relationships. Input is comma-separated table names."""
        requested_names = [
            name.strip() for name in table_names.split(",") if name.strip()
        ]
        return database.describe_tables(requested_names or None)

    @tool("sql_db_query")
    def query_database(query: str) -> str:
        """Execute one read-only SELECT, WITH, or EXPLAIN SQL statement."""
        try:
            return database.run_query(query)
        except ValueError as error:
            return f"Query rejected: {error}"

    return [list_tables, describe_tables, query_database]


@st.cache_resource(ttl="1h", max_entries=10, show_spinner=False)
def configure_agent(
    database_type: str,
    api_key: str,
    model: str,
    host: str = "",
    port: int = 3306,
    username: str = "",
    password: str = "",
    database_name: str = "",
    schema: str = "",
    ssl_mode: str = "prefer",
):
    """Create and cache the Groq-backed, read-only SQL agent."""
    database = configure_database(
        database_type,
        host,
        port,
        username,
        password,
        database_name,
        schema,
        ssl_mode,
    )
    llm = ChatGroq(
        api_key=api_key,
        model=model,
        temperature=0,
        streaming=False,
        max_retries=2,
        reasoning_effort="low",
    )
    return create_agent(
        model=llm,
        tools=create_database_tools(database),
        system_prompt=READ_ONLY_AGENT_PREFIX.format(
            dialect=database.dialect,
            top_k=25,
        ),
    )


def safe_error_message(error: Exception, *sensitive_values: str) -> str:
    """Return useful error details without echoing credentials."""
    message = str(error).strip() or error.__class__.__name__
    for value in sensitive_values:
        if value:
            message = message.replace(value, "***")
    return message[:500]


def environment_port(variable_name: str, default: int) -> int:
    """Read a valid TCP port from the environment or return the default."""
    try:
        port = int(os.getenv(variable_name, str(default)))
    except ValueError:
        return default
    return port if 1 <= port <= 65535 else default


with st.sidebar:
    st.header(":material/tune: Connection")
    database_type = st.segmented_control(
        "Database source",
        [SQLITE_LABEL, POSTGRESQL_LABEL, MYSQL_LABEL],
        default=SQLITE_LABEL,
        required=True,
        key="database_type",
        width="stretch",
    )

    database_host = ""
    database_port = 5432 if database_type == POSTGRESQL_LABEL else 3306
    database_user = ""
    database_password = ""
    database_name = ""
    database_schema = ""
    ssl_mode = "prefer"

    if database_type in (POSTGRESQL_LABEL, MYSQL_LABEL):
        is_postgresql = database_type == POSTGRESQL_LABEL
        environment_prefix = "POSTGRES" if is_postgresql else "MYSQL"
        default_port = 5432 if is_postgresql else 3306
        form_key = "postgresql_connection" if is_postgresql else "mysql_connection"

        with st.form(form_key, border=False):
            database_host = st.text_input(
                "Host",
                value=os.getenv(f"{environment_prefix}_HOST", ""),
                placeholder="localhost",
                key=f"{environment_prefix.lower()}_host",
            ).strip()
            database_port = int(
                st.number_input(
                    "Port",
                    min_value=1,
                    max_value=65535,
                    value=environment_port(
                        f"{environment_prefix}_PORT",
                        default_port,
                    ),
                    step=1,
                    key=f"{environment_prefix.lower()}_port",
                )
            )
            database_user = st.text_input(
                "Username",
                value=os.getenv(f"{environment_prefix}_USER", ""),
                placeholder="readonly_user",
                key=f"{environment_prefix.lower()}_user",
            ).strip()
            database_password = st.text_input(
                "Password",
                value=os.getenv(f"{environment_prefix}_PASSWORD", ""),
                type="password",
                help=(
                    "Optional for local servers configured without password "
                    "authentication."
                ),
                key=f"{environment_prefix.lower()}_password",
            )
            database_name = st.text_input(
                "Database",
                value=os.getenv(f"{environment_prefix}_DATABASE", ""),
                placeholder="analytics",
                key=f"{environment_prefix.lower()}_database",
            ).strip()

            if is_postgresql:
                database_schema = st.text_input(
                    "Schema",
                    value=os.getenv("POSTGRES_SCHEMA", "public"),
                    placeholder="public",
                    help=(
                        "Only tables in this PostgreSQL schema are exposed "
                        "to the assistant."
                    ),
                    key="postgres_schema",
                ).strip()
                ssl_options = [
                    "prefer",
                    "require",
                    "verify-ca",
                    "verify-full",
                    "disable",
                ]
                configured_ssl_mode = os.getenv("POSTGRES_SSLMODE", "prefer")
                ssl_mode = st.selectbox(
                    "SSL mode",
                    options=ssl_options,
                    index=(
                        ssl_options.index(configured_ssl_mode)
                        if configured_ssl_mode in ssl_options
                        else 0
                    ),
                    help="Use 'require' for most hosted PostgreSQL services.",
                    key="postgres_sslmode",
                )

            st.form_submit_button(
                "Apply connection",
                icon=":material/cable:",
                width="stretch",
            )
    else:
        st.caption(f"Sample data: `{SQLITE_DATABASE.name}`")

    st.subheader(":material/smart_toy: Model")
    selected_model_label = st.selectbox(
        "Groq model",
        options=list(MODEL_OPTIONS),
        index=0,
    )
    selected_model = MODEL_OPTIONS[selected_model_label]

    environment_api_key = os.getenv("GROQ_API_KEY", "").strip()
    entered_api_key = st.text_input(
        "Groq API key",
        type="password",
        placeholder=(
            "Using GROQ_API_KEY from .env"
            if environment_api_key
            else "Enter a key from console.groq.com"
        ),
        help="The typed value stays in this Streamlit session.",
    ).strip()
    api_key = entered_api_key or environment_api_key

    if environment_api_key and not entered_api_key:
        st.badge("Loaded from environment", icon=":material/check:", color="green")

    if st.button(
        "Clear conversation",
        icon=":material/delete_sweep:",
        width="stretch",
        disabled=not st.session_state.messages,
    ):
        st.session_state.messages.clear()
        st.rerun()

    st.caption("Read-only SQL analysis - Groq + LangChain")


st.title(":material/database: Chat with SQL")
st.caption(
    "Ask questions in plain language and let the assistant inspect your "
    "database, write SQL, and explain the results."
)

connection_context = (
    database_type,
    database_host,
    database_port,
    database_user,
    database_name,
    database_schema,
)
active_connection_context = st.session_state.get("connection_context")
conversation_store = st.session_state.conversation_store

if active_connection_context is None:
    st.session_state.connection_context = connection_context
    conversation_store.setdefault(connection_context, st.session_state.messages)
elif active_connection_context != connection_context:
    conversation_store[active_connection_context] = st.session_state.messages
    st.session_state.messages = conversation_store.setdefault(connection_context, [])
    st.session_state.connection_context = connection_context

missing_connection_fields = []
if database_type in (POSTGRESQL_LABEL, MYSQL_LABEL):
    connection_fields = {
        "host": database_host,
        "username": database_user,
        "database": database_name,
    }
    if database_type == POSTGRESQL_LABEL:
        connection_fields["schema"] = database_schema
    missing_connection_fields = [
        name for name, value in connection_fields.items() if not value
    ]

database = None
database_error = ""
table_names: tuple[str, ...] = ()

if not missing_connection_fields:
    try:
        with st.spinner("Checking the database connection..."):
            database = configure_database(
                database_type,
                database_host,
                database_port,
                database_user,
                database_password,
                database_name,
                database_schema,
                ssl_mode,
            )
            table_names = tuple(database.get_usable_table_names())
    except Exception as error:
        database_error = safe_error_message(error, database_password, api_key)

with st.container(border=True):
    st.subheader(":material/cable: Connection status")
    with st.container(horizontal=True, vertical_alignment="center"):
        if database is not None:
            st.badge("Connected", icon=":material/check_circle:", color="green")
            st.badge(
                f"{len(table_names)} table{'s' if len(table_names) != 1 else ''}",
                icon=":material/table_chart:",
                color="blue",
            )
        elif missing_connection_fields:
            st.badge("Setup needed", icon=":material/settings:", color="orange")
        else:
            st.badge("Connection failed", icon=":material/error:", color="red")

        st.markdown(f"**{database_type}** - `{selected_model}`")

    if table_names:
        st.caption("Available tables: " + ", ".join(f"`{name}`" for name in table_names))

if missing_connection_fields:
    st.info(
        f"Complete the {database_type} connection form in the sidebar, then "
        "select **Apply connection**. Missing: "
        + ", ".join(missing_connection_fields)
        + ".",
        icon=":material/info:",
    )
elif database_error:
    st.error(
        "The database connection could not be opened. Check the connection "
        f"details and permissions. Details: {database_error}",
        icon=":material/database_off:",
    )

if not api_key:
    st.info(
        "Add `GROQ_API_KEY` to `.env` or enter a Groq API key in the sidebar "
        "to enable chat.",
        icon=":material/key:",
    )

agent = None
if database is not None and api_key:
    try:
        with st.spinner("Preparing the SQL assistant..."):
            agent = configure_agent(
                database_type,
                api_key,
                selected_model,
                database_host,
                database_port,
                database_user,
                database_password,
                database_name,
                database_schema,
                ssl_mode,
            )
    except Exception as error:
        agent_error = safe_error_message(error, database_password, api_key)
        st.error(
            f"The SQL assistant could not start. Details: {agent_error}",
            icon=":material/smart_toy:",
        )


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


selected_suggestion = None
if agent is not None and not st.session_state.messages:
    st.caption("Try a sample question")
    available_questions = (
        SAMPLE_QUESTIONS
        if database_type == SQLITE_LABEL
        else REMOTE_SAMPLE_QUESTIONS
    )
    selected_suggestion = st.pills(
        "Sample questions",
        options=list(available_questions),
        label_visibility="collapsed",
        key="sample_question",
    )

typed_prompt = st.chat_input(
    "Ask a question about your database...",
    key="chat_prompt",
    disabled=agent is None,
    submit_mode="disable",
    max_chars=2_000,
)
prompt = (
    available_questions.get(selected_suggestion)
    if selected_suggestion
    else typed_prompt
)

if prompt and agent is not None:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.status("Exploring the database...", expanded=False) as status:
                conversation_messages = [
                    {
                        "role": message["role"],
                        "content": message["content"],
                    }
                    for message in st.session_state.messages
                ]
                response = agent.invoke(
                    {"messages": conversation_messages},
                    {"recursion_limit": 30},
                )
                final_message = response["messages"][-1]
                answer = final_message.text or "No answer was returned."
                status.update(
                    label="Answer ready",
                    state="complete",
                    expanded=False,
                )
            st.markdown(answer)
        except Exception as error:
            details = safe_error_message(error, database_password, api_key)
            answer = (
                "I couldn't complete that request. Check the API key, model "
                f"access, and database connection, then try again. Details: {details}"
            )
            st.error(answer, icon=":material/error:")

    st.session_state.messages.append({"role": "assistant", "content": answer})
