# Small Business Invoice and GST Assistant

A local MCP-powered assistant that helps small businesses and freelancers in India manage invoices, track payments, identify overdue bills, and generate monthly invoice and estimated GST reports.

## Overview

Small business owners often manage invoices and payments through spreadsheets or manual records. This can make it difficult to track outstanding balances, identify overdue invoices, and prepare monthly summaries.

The **Small Business Invoice and GST Assistant** addresses this problem with a Python-based local server that exposes business operations through the Model Context Protocol (MCP). An MCP-compatible AI client can invoke these operations using natural-language requests.

Invoice records are stored in SQLite, and monthly reports can be exported as CSV files for review in spreadsheet applications.

## Features

- **Invoice management:** Create invoices with customer details, invoice dates, due dates, taxable amounts, and configured GST rates.
- **Payment tracking:** Record partial or full payments and calculate outstanding balances.
- **Overdue detection:** Find unpaid invoices whose due dates have passed.
- **Monthly summaries:** Summarize taxable sales, estimated output GST, invoice totals, recorded payments, and outstanding balances.
- **CSV reports:** Export invoice-level details and monthly summary information.
- **MCP tools:** Expose invoice and reporting operations to an AI client.
- **MCP resources:** Provide a read-only business summary and GST guidance.
- **MCP prompts:** Supply reusable instructions for a monthly business review.
- **Input validation:** Validate required fields, dates, configured GST rates, amounts, and payment limits.
- **Local storage:** Use SQLite without requiring a separate database server.

## Architecture

```text
User
 |
 v
MCP-compatible AI client
(e.g. GitHub Copilot Agent mode)
 |
 v
Model Context Protocol (MCP)
 |
 v
Python MCP server (server.py)
 |
 +----------------------+
 |          |           |
 v          v           v
Tools    Resources    Prompts
 |
 v
Input validation
 |
 v
SQLite database
 |
 v
Monthly CSV reports
```

The AI client interprets the user's request and can invoke an appropriate tool. The Python server validates the arguments, performs the requested operation, and returns the result.

Resources provide information without changing business records. Prompts provide reusable instructions for tasks such as a monthly review.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and validation |
| MCP Python SDK | Expose tools, resources, and prompts |
| SQLite | Persistent invoice storage |
| CSV | Exportable monthly reports |
| VS Code | Development environment |
| GitHub Copilot | Natural-language interaction through MCP |

## MCP Capabilities

### Tools

| Tool | Purpose |
|---|---|
| `create_invoice` | Create and save an invoice |
| `record_payment` | Record a payment and update the outstanding balance |
| `list_overdue_invoices` | Find unpaid invoices past their due dates |
| `get_monthly_gst_summary` | Calculate monthly invoice and estimated output GST figures |
| `export_monthly_report` | Export invoice details and a summary to CSV |

### Resources

| Resource URI | Purpose |
|---|---|
| `business://summary` | Read-only overview of invoice totals, recorded payments, and outstanding balances |
| `business://gst-guide` | Explain the scope and limitations of the GST calculations |

### Prompt

| Prompt | Purpose |
|---|---|
| `monthly_gst_review` | Guide an AI-assisted review of monthly figures, overdue invoices, and GST calculation limitations |

## Project Structure

```text
small-business-gst-assistant/
|
|-- server.py
|-- requirements.txt
|-- README.md
|-- .gitignore
|-- AI_CLIENT_TESTS.md
|-- TEST_RESULTS.md
|-- USER_FEEDBACK.md
|
|-- .vscode/
|   |-- mcp.json
|
|-- invoices.db
|-- reports/
|   |-- monthly_report_YYYY-MM.csv
|
|-- .venv/
```

The `.vscode/mcp.json` file is a local configuration example. Do not commit machine-specific absolute paths. The database, generated reports, and virtual environment are local runtime artifacts and should normally be excluded from version control.

The test documentation files can be included once they exist and contain your actual test results.

## Prerequisites

- Python 3.11 or newer
- Visual Studio Code
- Git
- An MCP-compatible client for AI interaction
- GitHub Copilot access if using Copilot Agent mode

The MCP Inspector is useful for testing tools, resources, and prompts before connecting an AI client.

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/small-business-gst-assistant.git
cd small-business-gst-assistant
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
```

Use your installed Python 3.11+ version if Python 3.12 is unavailable.

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Run the MCP server

```bash
python server.py
```

The server communicates through standard input/output when launched by an MCP client. Running it directly in a terminal may appear to wait without displaying a message; this is normal for an stdio-based server.

### 5. Test with MCP Inspector

Install the project's declared MCP CLI dependency, then run:

```bash
mcp dev server.py
```

Use the Inspector to connect to the server and test the tools, resources, and prompts.

### 6. Connect an AI client

Configure an MCP-compatible AI client to launch `server.py` using the Python interpreter in your virtual environment.

For VS Code, create a local `.vscode/mcp.json` configuration that points to your project's Python executable and `server.py`. Follow the MCP configuration instructions for the installed VS Code version.

Once connected, select Agent mode in Copilot Chat and test natural-language requests. Review tool arguments and authorize state-changing actions deliberately.

## Example Usage

### Create an invoice

Example request:

> Create an invoice for customer Meera with a taxable amount of ₹2,000 and a configured GST rate of 18%.

Expected calculation:

| Item | Amount |
|---|---:|
| Taxable amount | ₹2,000.00 |
| Estimated GST at 18% | ₹360.00 |
| Invoice total | ₹2,360.00 |

This is a demonstration calculation using the configured rate, not a determination of the legally applicable GST treatment.

### Record a payment

Example request:

> Record a payment of ₹1,000 against invoice INV-AI-001.

For an invoice total of ₹2,360, the expected outstanding balance after this payment is ₹1,360, assuming no other payments have been recorded.

### Find overdue invoices

Example request:

> As of 13 October 2026, list overdue invoices and their outstanding balances.

The server returns invoices whose due dates are before the specified date and which still have an unpaid balance.

### Generate a monthly summary

Example request:

> Summarize the taxable sales, estimated output GST, invoice totals, payments, and outstanding balances for October 2026.

The summary is based on invoices dated within the selected month.

### Export a monthly report

Example request:

> Export the October 2026 invoice report to CSV.

The report is saved in the project's `reports` directory.

## Validation and Testing

The project should be tested for both successful operations and invalid input.

Suggested tests include:

- Valid and duplicate invoice numbers
- Empty customer names and invoice numbers
- Negative invoice amounts
- Invalid GST rates
- Invalid dates and due dates before invoice dates
- Zero and negative payments
- Payments exceeding the outstanding balance
- Payments against non-existent invoices
- Invalid monthly reporting periods
- Correct CSV output and monthly totals
- MCP tool, resource, and prompt discovery
- Natural-language tool calls through the AI client

Test results should be recorded in `TEST_RESULTS.md` and `AI_CLIENT_TESTS.md` based on actual executions.

## Real-User Evaluation

The project includes a planned real-user evaluation with a shop owner or freelancer.

The tester should try invoice creation, payment recording, overdue detection, and monthly report export. Their actual feedback should be recorded in `USER_FEEDBACK.md`, and at least one improvement should be implemented and retested.

Do not treat this evaluation as complete until a real person has tested the application and provided feedback.

## Limitations and GST Disclaimer

This project is a learning prototype for invoice tracking and bookkeeping.

- It does not file GST returns or connect to the official GST portal.
- It does not determine GST registration obligations or validate HSN/SAC classifications.
- Its configured GST rates are demo settings and do not determine the correct rate for every transaction.
- Estimated output GST is not necessarily the GST collected in cash during the month.
- The application does not calculate complete net GST payable after input tax credit, reverse charge, credit notes, adjustments, or other applicable tax rules.
- The current payment model stores a cumulative paid amount rather than a full payment transaction history.

Verify the applicable GST treatment and financial records with a qualified professional before using them for compliance purposes.

rning project exploring Python, SQLite, MCP, and AI-assisted business workflows.
