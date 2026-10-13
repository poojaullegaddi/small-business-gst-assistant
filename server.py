
import csv
import json
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from mcp.server.fastmcp import FastMCP


# --------------------------------------------------
# 1. PROJECT SETTINGS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "invoices.db"
REPORTS_DIR = BASE_DIR / "reports"

# Demo rates only; verify the legally applicable rate
# for the actual goods/services before issuing invoices.
ALLOWED_GST_RATES = {0, 5, 12, 18, 28}

mcp = FastMCP("Small Business Invoice and GST Assistant")


# --------------------------------------------------
# 2. INPUT VALIDATION HELPERS
# --------------------------------------------------

def validate_text(value: str, field: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError(f"{field} cannot be empty.")

    if len(value) > 150:
        raise ValueError(f"{field} is too long.")

    return value


def validate_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(
            f"{field} must use YYYY-MM-DD format."
        )


def money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Amount must be a valid number.")

    if not amount.is_finite():
        raise ValueError("Amount must be finite.")

    if amount < 0:
        raise ValueError("Amount cannot be negative.")

    if amount > Decimal("1000000000"):
        raise ValueError("Amount exceeds the demo limit.")

    return amount.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def format_money(value) -> str:
    return str(money(value))


# --------------------------------------------------
# 3. DATABASE CONNECTION AND TABLE CREATION
# --------------------------------------------------

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                taxable_amount REAL NOT NULL,
                gst_rate INTEGER NOT NULL,
                gst_amount REAL NOT NULL,
                total_amount REAL NOT NULL,
                amount_paid REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (taxable_amount >= 0),
                CHECK (gst_amount >= 0),
                CHECK (total_amount >= 0),
                CHECK (amount_paid >= 0),
                CHECK (amount_paid <= total_amount)
            )
        """)


initialize_database()


# --------------------------------------------------
# 4. TOOL: CREATE AN INVOICE
# --------------------------------------------------

@mcp.tool()
def create_invoice(
    invoice_number: str,
    customer_name: str,
    invoice_date: str,
    due_date: str,
    taxable_amount: float,
    gst_rate: int
) -> str:
    """Create and save a new invoice.

    Dates must use YYYY-MM-DD. GST rate must be one
    of the configured demo rates. Duplicate invoice
    numbers are rejected.
    """

    invoice_number = validate_text(
        invoice_number, "Invoice number"
    )
    customer_name = validate_text(
        customer_name, "Customer name"
    )

    invoice_day = validate_date(
        invoice_date, "Invoice date"
    )
    due_day = validate_date(due_date, "Due date")

    if due_day < invoice_day:
        raise ValueError(
            "Due date cannot be before invoice date."
        )

    if gst_rate not in ALLOWED_GST_RATES:
        raise ValueError(
            f"GST rate must be one of "
            f"{sorted(ALLOWED_GST_RATES)}."
        )

    taxable = money(taxable_amount)

    # Simple invoice calculation for this demo.
    gst = (taxable * Decimal(gst_rate) / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total = taxable + gst

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO invoices (
                invoice_number, customer_name,
                invoice_date, due_date,
                taxable_amount, gst_rate,
                gst_amount, total_amount, amount_paid
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            invoice_number,
            customer_name,
            invoice_day.isoformat(),
            due_day.isoformat(),
            float(taxable),
            gst_rate,
            float(gst),
            float(total)
        ))

        invoice_id = cursor.lastrowid

    return json.dumps({
        "message": "Invoice created successfully.",
        "id": invoice_id,
        "invoice_number": invoice_number,
        "customer_name": customer_name,
        "taxable_amount": str(taxable),
        "gst_rate_percent": gst_rate,
        "gst_amount": str(gst),
        "total_amount": str(total),
        "amount_paid": "0.00",
        "outstanding_amount": str(total)
    }, indent=2)


# --------------------------------------------------
# 5. TOOL: RECORD A PAYMENT
# --------------------------------------------------

@mcp.tool()
def record_payment(
    invoice_number: str,
    payment_amount: float
) -> str:
    """Record a payment against an existing invoice.

    Rejects zero payments and payments exceeding the
    remaining balance.
    """

    invoice_number = validate_text(
        invoice_number, "Invoice number"
    )
    payment = money(payment_amount)

    if payment <= 0:
        raise ValueError("Payment must be greater than zero.")

    with get_connection() as connection:
        row = connection.execute("""
            SELECT * FROM invoices
            WHERE invoice_number = ?
        """, (invoice_number,)).fetchone()

        if row is None:
            raise ValueError("Invoice not found.")

        outstanding = (
            money(row["total_amount"])
            - money(row["amount_paid"])
        )

        if payment > outstanding:
            raise ValueError(
                f"Payment exceeds outstanding balance "
                f"of {outstanding}."
            )

        new_paid = money(row["amount_paid"]) + payment

        connection.execute("""
            UPDATE invoices
            SET amount_paid = ?
            WHERE invoice_number = ?
        """, (float(new_paid), invoice_number))

        remaining = money(row["total_amount"]) - new_paid

    return json.dumps({
        "message": "Payment recorded successfully.",
        "invoice_number": invoice_number,
        "payment_received": str(payment),
        "total_paid": str(new_paid),
        "outstanding_amount": str(remaining),
        "status": (
            "PAID" if remaining == 0 else "PARTIALLY PAID"
        )
    }, indent=2)


# --------------------------------------------------
# 6. TOOL: LIST OVERDUE INVOICES
# --------------------------------------------------

@mcp.tool()
def list_overdue_invoices(as_of_date: str = "") -> str:
    """List invoices past their due date with a balance
    remaining. Optional as_of_date supports testing.
    Defaults to today's date.
    """

    if as_of_date:
        cutoff = validate_date(
            as_of_date, "As-of date"
        ).isoformat()
    else:
        cutoff = date.today().isoformat()

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT invoice_number, customer_name,
                   invoice_date, due_date,
                   total_amount, amount_paid
            FROM invoices
            WHERE due_date < ?
              AND amount_paid < total_amount
            ORDER BY due_date
        """, (cutoff,)).fetchall()

    overdue = []

    for row in rows:
        balance = (
            money(row["total_amount"])
            - money(row["amount_paid"])
        )
        overdue.append({
            "invoice_number": row["invoice_number"],
            "customer_name": row["customer_name"],
            "due_date": row["due_date"],
            "total_amount": str(money(row["total_amount"])),
            "amount_paid": str(money(row["amount_paid"])),
            "outstanding_amount": str(balance)
        })

    return json.dumps({
        "as_of_date": cutoff,
        "overdue_count": len(overdue),
        "invoices": overdue
    }, indent=2)


# --------------------------------------------------
# 7. TOOL: MONTHLY SUMMARY
# --------------------------------------------------

def get_month_bounds(month: str):
    try:
        month_start = date.fromisoformat(month + "-01")
    except ValueError:
        raise ValueError("Month must use YYYY-MM format.")

    if month_start.strftime("%Y-%m") != month:
        raise ValueError("Month must use YYYY-MM format.")

    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(
            month_start.year, month_start.month + 1, 1
        )

    return month_start.isoformat(), next_month.isoformat()


def build_monthly_summary(month: str) -> dict:
    start, end = get_month_bounds(month)

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM invoices
            WHERE invoice_date >= ?
              AND invoice_date < ?
            ORDER BY invoice_date, invoice_number
        """, (start, end)).fetchall()

    taxable = sum(
        (money(row["taxable_amount"]) for row in rows),
        Decimal("0.00")
    )
    gst = sum(
        (money(row["gst_amount"]) for row in rows),
        Decimal("0.00")
    )
    invoice_total = sum(
        (money(row["total_amount"]) for row in rows),
        Decimal("0.00")
    )
    paid_on_these_invoices = sum(
        (money(row["amount_paid"]) for row in rows),
        Decimal("0.00")
    )
    outstanding = invoice_total - paid_on_these_invoices

    return {
        "month": month,
        "invoice_count": len(rows),
        "taxable_sales": str(taxable),
        "estimated_output_gst": str(gst),
        "invoice_total_including_gst": str(invoice_total),
        "payments_received_against_these_invoices": str(
            paid_on_these_invoices
        ),
        "outstanding_against_these_invoices": str(outstanding),
        "basis": (
            "Invoices dated in the selected month. "
            "This is an estimate of GST on recorded invoices, "
            "not official net GST payable or a GST return."
        )
    }


@mcp.tool()
def get_monthly_gst_summary(month: str) -> str:
    """Summarize invoices dated in a month. Month format
    is YYYY-MM. Shows taxable sales, estimated output GST,
    invoice totals, recorded payments and balances.
    Does not calculate official net GST payable.
    """

    return json.dumps(build_monthly_summary(month), indent=2)


# --------------------------------------------------
# 8. TOOL: EXPORT A MONTHLY CSV REPORT
# --------------------------------------------------

@mcp.tool()
def export_monthly_report(month: str) -> str:
    """Export invoice-level details and a summary to a
    CSV file in the project's reports folder.
    Month format is YYYY-MM.
    """

    start, end = get_month_bounds(month)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT invoice_number, customer_name,
                   invoice_date, due_date,
                   taxable_amount, gst_rate,
                   gst_amount, total_amount, amount_paid
            FROM invoices
            WHERE invoice_date >= ?
              AND invoice_date < ?
            ORDER BY invoice_date, invoice_number
        """, (start, end)).fetchall()

    report_path = REPORTS_DIR / f"monthly_report_{month}.csv"

    with report_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.writer(file)

        writer.writerow([
            "Invoice Number", "Customer", "Invoice Date",
            "Due Date", "Taxable Amount", "GST Rate (%)",
            "GST Amount", "Invoice Total", "Amount Paid",
            "Outstanding Amount"
        ])

        for row in rows:
            outstanding = (
                money(row["total_amount"])
                - money(row["amount_paid"])
            )
            writer.writerow([
                row["invoice_number"],
                row["customer_name"],
                row["invoice_date"],
                row["due_date"],
                format_money(row["taxable_amount"]),
                row["gst_rate"],
                format_money(row["gst_amount"]),
                format_money(row["total_amount"]),
                format_money(row["amount_paid"]),
                str(outstanding)
            ])

        summary = build_monthly_summary(month)
        writer.writerow([])
        writer.writerow(["MONTHLY SUMMARY"])
        writer.writerow(["Month", month])
        writer.writerow(["Invoice Count", summary["invoice_count"]])
        writer.writerow(["Taxable Sales", summary["taxable_sales"]])
        writer.writerow([
            "Estimated Output GST",
            summary["estimated_output_gst"]
        ])
        writer.writerow([
            "Invoice Total",
            summary["invoice_total_including_gst"]
        ])
        writer.writerow(["Basis", summary["basis"]])

    return json.dumps({
        "message": "Monthly report exported.",
        "month": month,
        "invoice_count": len(rows),
        "file_path": str(report_path.resolve()),
        "note": "This CSV is a bookkeeping report, not a GST return."
    }, indent=2)


# --------------------------------------------------
# 9. RESOURCE: BUSINESS SUMMARY
# --------------------------------------------------

@mcp.resource("business://summary")
def business_summary_resource() -> str:
    """Provide a read-only overview of saved invoices."""

    with get_connection() as connection:
        row = connection.execute("""
            SELECT COUNT(*) AS invoice_count,
                   COALESCE(SUM(total_amount), 0) AS total,
                   COALESCE(SUM(amount_paid), 0) AS paid
            FROM invoices
        """).fetchone()

    total = money(row["total"])
    paid = money(row["paid"])

    return json.dumps({
        "invoice_count": row["invoice_count"],
        "invoice_total": str(total),
        "recorded_payments": str(paid),
        "outstanding_balance": str(total - paid)
    }, indent=2)


# --------------------------------------------------
# 10. RESOURCE: GST GUIDANCE
# --------------------------------------------------

@mcp.resource("business://gst-guide")
def gst_guide_resource() -> str:
    """Explain the scope and limitations of this demo."""

    return (
        "This application records invoice amounts and estimates "
        "output GST using a configured rate. It does not determine "
        "registration obligations, validate HSN/SAC classifications, "
        "calculate input tax credit, handle every GST adjustment, "
        "or file returns. Actual tax treatment depends on the "
        "business, goods or services, place of supply, applicable "
        "rules, and filing method. Verify records with a qualified "
        "GST practitioner before filing."
    )


# --------------------------------------------------
# 11. PROMPT: MONTHLY BUSINESS REVIEW
# --------------------------------------------------

@mcp.prompt()
def monthly_gst_review(month: str) -> str:
    """Prepare an AI-assisted monthly invoice and GST review."""

    get_month_bounds(month)  # Validate the requested month.

    return (
        f"Review the business records for {month}. "
        "Use get_monthly_gst_summary to retrieve the figures, "
        "list_overdue_invoices to identify unpaid overdue bills, "
        "and business://gst-guide to understand the limitations. "
        "Explain taxable sales, estimated output GST, invoice totals, "
        "payments, outstanding balances and overdue invoices. "
        "Do not call the estimate official net GST payable. "
        "Clearly identify missing information and recommend "
        "that the owner verify tax treatment before filing."
    )


# --------------------------------------------------
# 12. START THE LOCAL MCP SERVER
# --------------------------------------------------

if __name__ == "__main__":
    mcp.run()

