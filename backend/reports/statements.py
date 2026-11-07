"""Statements built from the ledger, so they always agree with the books (FR-10, BR-12)."""

import io
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from chamas.models import ChamaMembership
from finance import ledger
from finance.models import FinancialAccount, JournalLine

EMERALD = (6, 78, 59)
FORMULA_START = ("=", "+", "-", "@")


@dataclass
class Table:
    title: str
    headings: list[str]
    rows: list[list] = field(default_factory=list)
    money_columns: set[int] = field(default_factory=set)


@dataclass
class Report:
    title: str
    subtitle: str
    tables: list[Table]


def money(value: Decimal) -> str:
    return f"{value:,.2f}"


def member_statement(membership) -> Report:
    chama = membership.chama
    savings = FinancialAccount.objects.get(chama=chama, code=FinancialAccount.MEMBER_SAVINGS)
    lines = (JournalLine.objects.filter(account=savings, membership=membership)
             .select_related("entry").order_by("entry__transaction_date", "entry__created_at"))
    running = Decimal("0")
    activity = Table("Savings", ["Date", "Description", "Reference", "Paid in", "Paid out",
                                 "Balance"], money_columns={3, 4, 5})
    for line in lines:
        running += line.credit_amount - line.debit_amount
        activity.rows.append([line.entry.transaction_date.isoformat(), line.entry.description,
                              line.entry.transaction_reference, line.credit_amount,
                              line.debit_amount, running])

    today = timezone.localdate()
    schedule = Table("Contribution schedule", ["Due date", "Expected", "Paid", "Outstanding",
                                               "Status"], money_columns={1, 2, 3})
    for row in membership.schedules.filter(due_date__lte=today).order_by("due_date"):
        schedule.rows.append([row.due_date.isoformat(), row.expected_amount, row.paid_amount,
                              row.outstanding, row.status_on(today)])
    return Report(f"{chama.name}: member statement",
                  f"{membership.user.full_name}. Currency {chama.currency}. "
                  f"Prepared {today.isoformat()}.", [activity, schedule])


def group_statement(chama) -> Report:
    today = timezone.localdate()
    accounts = Table("Accounts", ["Account", "Type", "Debits", "Credits", "Balance"],
                     money_columns={2, 3, 4})
    for row in ledger.trial_balance(chama):
        accounts.rows.append([row["name"], row["type"], row["debit"], row["credit"],
                              row["balance"]])
    members = Table("Members", ["Member", "Status", "Savings", "Outstanding now"],
                    money_columns={2, 3})
    for membership in (chama.memberships.select_related("user")
                       .exclude(status__in=["pending", "rejected"])
                       .order_by("user__first_name")):
        owed = sum((s.outstanding for s in membership.schedules.filter(due_date__lte=today)),
                   Decimal("0"))
        members.rows.append([membership.user.full_name, membership.status,
                             ledger.member_savings(membership), owed])
    return Report(f"{chama.name}: financial statement",
                  f"Currency {chama.currency}. Prepared {today.isoformat()}.",
                  [accounts, members])


def _plain(value) -> str:
    """Core PDF fonts cover Latin-1 only."""
    text = money(value) if isinstance(value, Decimal) else str(value)
    return text.encode("latin-1", "replace").decode("latin-1")


def to_pdf(report: Report) -> bytes:
    pdf = FPDF(orientation="landscape", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*EMERALD)
    pdf.cell(0, 10, _plain(report.title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 6, _plain(report.subtitle), new_x="LMARGIN", new_y="NEXT")
    for table in report.tables:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _plain(table.title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        if not table.rows:
            pdf.cell(0, 6, "Nothing yet.", new_x="LMARGIN", new_y="NEXT")
            continue
        with pdf.table(text_align=["RIGHT" if i in table.money_columns else "LEFT"
                                   for i in range(len(table.headings))]) as grid:
            heading = grid.row()
            for title in table.headings:
                heading.cell(_plain(title))
            for values in table.rows:
                row = grid.row()
                for value in values:
                    row.cell(_plain(value))
    return bytes(pdf.output())


def _safe_cell(cell, value):
    """Text is always stored as text, so a value like "=HYPERLINK(...)" can never run."""
    if isinstance(value, Decimal):
        cell.value = float(value)
        cell.number_format = "#,##0.00"
        return
    cell.value = str(value)
    cell.data_type = "s"


def to_xlsx(report: Report) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for table in report.tables:
        sheet = workbook.create_sheet(table.title[:31])
        _safe_cell(sheet.cell(1, 1), report.title)
        sheet.cell(1, 1).font = Font(bold=True, size=14, color="064E3B")
        _safe_cell(sheet.cell(2, 1), report.subtitle)
        for column, title in enumerate(table.headings, start=1):
            cell = sheet.cell(4, column)
            _safe_cell(cell, title)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="064E3B")
            sheet.column_dimensions[cell.column_letter].width = 18
        for row_number, values in enumerate(table.rows, start=5):
            for column, value in enumerate(values, start=1):
                _safe_cell(sheet.cell(row_number, column), value)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def active_members(chama):
    return chama.memberships.filter(status=ChamaMembership.Status.ACTIVE)
