import base64
import io

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from odoo import _, fields, models
from odoo.exceptions import UserError


class RealestateReportExportWizard(models.TransientModel):
    _name = "realestate.report.export.wizard"
    _description = "Real Estate Report Export Wizard"

    report_type = fields.Selection(
        [
            ("rent_collection", "Rent Collection"),
            ("rent_due", "Rent Due / Overdue"),
            ("building_income", "Building Income"),
            ("tenant_outstanding", "Tenant Outstanding"),
            ("expense_analysis", "Expense Analysis"),
            ("profit_analysis", "Profit Analysis"),
            ("vat_handoff", "VAT Handoff"),
        ],
        required=True,
        default="rent_collection",
    )
    date_from = fields.Date()
    date_to = fields.Date()
    building_id = fields.Many2one("realestate.building")
    unit_id = fields.Many2one("realestate.unit", domain="[('building_id', '=', building_id)]")
    tenant_id = fields.Many2one("res.partner", domain="[('is_tenant', '=', True)]")
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    def action_print_pdf(self):
        self.ensure_one()
        self._check_date_range()
        return self.env.ref("realestate.action_report_realestate_export_pdf").report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        self._check_date_range()
        content = self._generate_xlsx()
        file_name = "%s.xlsx" % self._report_slug()
        self.write({"file_data": base64.b64encode(content), "file_name": file_name})
        return {
            "type": "ir.actions.act_url",
            "url": "/realestate/report/export/xlsx/%s?download=true" % self.id,
            "target": "self",
        }

    def _check_date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise UserError(_("The start date must be before or equal to the end date."))

    def _get_report_title(self):
        self.ensure_one()
        return dict(self._fields["report_type"].selection).get(self.report_type)

    def _report_slug(self):
        self.ensure_one()
        return "realestate_%s" % self.report_type

    def _get_filter_summary(self):
        self.ensure_one()
        filters = []
        if self.date_from:
            filters.append(_("From: %s") % self.date_from)
        if self.date_to:
            filters.append(_("To: %s") % self.date_to)
        if self.building_id:
            filters.append(_("Building: %s") % self.building_id.display_name)
        if self.unit_id:
            filters.append(_("Unit: %s") % self.unit_id.display_name)
        if self.tenant_id:
            filters.append(_("Tenant: %s") % self.tenant_id.display_name)
        return filters or [_("No filters")]

    def _get_report_columns(self):
        self.ensure_one()
        columns = {
            "rent_collection": [
                ("date", _("Invoice Date"), "date"),
                ("invoice", _("Invoice"), "char"),
                ("tenant", _("Tenant"), "char"),
                ("building", _("Building"), "char"),
                ("unit", _("Unit"), "char"),
                ("payment_state", _("Payment Status"), "char"),
                ("amount", _("Amount"), "amount"),
            ],
            "rent_due": [
                ("date", _("Due Date"), "date"),
                ("invoice", _("Invoice"), "char"),
                ("tenant", _("Tenant"), "char"),
                ("building", _("Building"), "char"),
                ("unit", _("Unit"), "char"),
                ("payment_state", _("Payment Status"), "char"),
                ("amount", _("Outstanding"), "amount"),
            ],
            "tenant_outstanding": [
                ("tenant", _("Tenant"), "char"),
                ("invoice", _("Invoice"), "char"),
                ("date", _("Due Date"), "date"),
                ("building", _("Building"), "char"),
                ("unit", _("Unit"), "char"),
                ("amount", _("Outstanding"), "amount"),
            ],
            "expense_analysis": [
                ("date", _("Bill Date"), "date"),
                ("invoice", _("Bill"), "char"),
                ("partner", _("Vendor"), "char"),
                ("category", _("Category"), "char"),
                ("building", _("Building"), "char"),
                ("unit", _("Unit"), "char"),
                ("amount", _("Amount"), "amount"),
            ],
            "vat_handoff": [
                ("date", _("Invoice Date"), "date"),
                ("invoice", _("Invoice"), "char"),
                ("tenant", _("Tenant"), "char"),
                ("untaxed", _("Untaxed"), "amount"),
                ("tax", _("Tax"), "amount"),
                ("amount", _("Total"), "amount"),
            ],
            "building_income": [
                ("date", _("Date"), "date"),
                ("building", _("Building"), "char"),
                ("unit", _("Unit"), "char"),
                ("tenant", _("Tenant"), "char"),
                ("invoice", _("Invoice"), "char"),
                ("amount", _("Income"), "amount"),
            ],
            "profit_analysis": [
                ("date", _("Date"), "date"),
                ("type", _("Type"), "char"),
                ("building", _("Building"), "char"),
                ("unit", _("Unit"), "char"),
                ("partner", _("Tenant/Vendor"), "char"),
                ("category", _("Expense Category"), "char"),
                ("amount", _("Amount"), "amount"),
            ],
        }
        return columns[self.report_type]

    def _get_report_lines(self):
        self.ensure_one()
        if self.report_type in {"building_income", "profit_analysis"}:
            return self._get_financial_report_lines()
        return self._get_account_move_report_lines()

    def _get_total_amount(self):
        self.ensure_one()
        return sum(line.get("amount") or 0.0 for line in self._get_report_lines())

    def _get_account_move_report_lines(self):
        domain = self._get_account_move_domain()
        moves = self.env["account.move"].search(domain, order="invoice_date desc, date desc, id desc")
        lines = []
        for move in moves:
            contract = move.realestate_contract_id
            if self.report_type == "vat_handoff":
                lines.append(
                    {
                        "date": move.invoice_date,
                        "invoice": move.name,
                        "tenant": move.partner_id.display_name,
                        "untaxed": move.amount_untaxed_signed,
                        "tax": move.amount_tax_signed,
                        "amount": move.amount_total_signed,
                    }
                )
            elif self.report_type == "expense_analysis":
                lines.append(
                    {
                        "date": move.invoice_date,
                        "invoice": move.name,
                        "partner": move.partner_id.display_name,
                        "category": dict(move._fields["realestate_expense_category"].selection).get(
                            move.realestate_expense_category, ""
                        ),
                        "building": move.realestate_expense_building_id.display_name,
                        "unit": move.realestate_expense_unit_id.display_name,
                        "amount": move.realestate_expense_amount,
                    }
                )
            else:
                lines.append(
                    {
                        "date": move.invoice_date_due if self.report_type in {"rent_due", "tenant_outstanding"} else move.invoice_date,
                        "invoice": move.name,
                        "tenant": move.partner_id.display_name,
                        "building": contract.building_id.display_name,
                        "unit": contract.unit_id.display_name,
                        "payment_state": dict(move._fields["payment_state"].selection).get(move.payment_state, ""),
                        "amount": move.amount_residual_signed
                        if self.report_type in {"rent_due", "tenant_outstanding"}
                        else move.amount_total_signed,
                    }
                )
        return lines

    def _get_account_move_domain(self):
        domain = [("company_id", "in", self.env.companies.ids), ("state", "!=", "cancel")]
        date_field = "invoice_date_due" if self.report_type in {"rent_due", "tenant_outstanding"} else "invoice_date"
        if self.report_type == "expense_analysis":
            domain += [
                ("move_type", "in", ("in_invoice", "in_refund")),
                "|",
                "|",
                ("realestate_expense_category", "!=", False),
                ("realestate_expense_building_id", "!=", False),
                ("realestate_expense_unit_id", "!=", False),
            ]
            if self.building_id:
                domain.append(("realestate_expense_building_id", "=", self.building_id.id))
            if self.unit_id:
                domain.append(("realestate_expense_unit_id", "=", self.unit_id.id))
        else:
            domain += [("realestate_contract_id", "!=", False)]
            if self.report_type in {"rent_collection", "vat_handoff"}:
                domain.append(("move_type", "in", ("out_invoice", "out_refund")))
                if self.report_type == "vat_handoff":
                    domain.append(("state", "=", "posted"))
            elif self.report_type in {"rent_due", "tenant_outstanding"}:
                domain += [("move_type", "=", "out_invoice"), ("payment_state", "!=", "paid")]
            if self.building_id:
                domain.append(("realestate_contract_id.building_id", "=", self.building_id.id))
            if self.unit_id:
                domain.append(("realestate_contract_id.unit_id", "=", self.unit_id.id))
            if self.tenant_id:
                domain.append(("partner_id", "=", self.tenant_id.id))
        if self.date_from:
            domain.append((date_field, ">=", self.date_from))
        if self.date_to:
            domain.append((date_field, "<=", self.date_to))
        return domain

    def _get_financial_report_lines(self):
        domain = [("company_id", "in", self.env.companies.ids)]
        if self.report_type == "building_income":
            domain.append(("line_type", "=", "income"))
        if self.date_from:
            domain.append(("date", ">=", self.date_from))
        if self.date_to:
            domain.append(("date", "<=", self.date_to))
        if self.building_id:
            domain.append(("building_id", "=", self.building_id.id))
        if self.unit_id:
            domain.append(("unit_id", "=", self.unit_id.id))
        if self.tenant_id:
            domain.append(("tenant_id", "=", self.tenant_id.id))
        records = self.env["realestate.financial.report"].search(domain, order="date desc, id desc")
        expense_selection = dict(records._fields["expense_category"].selection)
        type_selection = dict(records._fields["line_type"].selection)
        lines = []
        for record in records:
            move = record.move_id
            lines.append(
                {
                    "date": record.date,
                    "type": type_selection.get(record.line_type, ""),
                    "building": record.building_id.display_name,
                    "unit": record.unit_id.display_name,
                    "tenant": record.tenant_id.display_name,
                    "partner": (record.tenant_id or record.partner_id).display_name,
                    "category": expense_selection.get(record.expense_category, ""),
                    "invoice": move.name,
                    "amount": record.amount,
                }
            )
        return lines

    def _generate_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet(self._get_report_title()[:31])
        title_format = workbook.add_format({"bold": True, "font_size": 14})
        label_format = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        text_format = workbook.add_format({"border": 1})
        amount_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        date_format = workbook.add_format({"border": 1, "num_format": "yyyy-mm-dd"})
        total_format = workbook.add_format({"bold": True, "border": 1, "num_format": "#,##0.00"})

        columns = self._get_report_columns()
        lines = self._get_report_lines()
        worksheet.write(0, 0, self._get_report_title(), title_format)
        worksheet.write(1, 0, ", ".join(self._get_filter_summary()))
        worksheet.write(2, 0, _("Company: %s") % self.env.company.display_name)
        header_row = 4
        for col, (_key, label, _kind) in enumerate(columns):
            worksheet.write(header_row, col, label, label_format)
            worksheet.set_column(col, col, 18)

        for row_index, line in enumerate(lines, start=header_row + 1):
            for col, (key, _label, kind) in enumerate(columns):
                value = line.get(key)
                if kind == "amount":
                    worksheet.write_number(row_index, col, value or 0.0, amount_format)
                elif kind == "date" and value:
                    worksheet.write_datetime(row_index, col, fields.Datetime.to_datetime(value), date_format)
                else:
                    worksheet.write(row_index, col, value or "", text_format)

        total_row = header_row + len(lines) + 1
        amount_columns = [index for index, (_key, _label, kind) in enumerate(columns) if kind == "amount"]
        if amount_columns:
            worksheet.write(total_row, 0, _("Total"), label_format)
            for col in amount_columns:
                column_letter = xl_col_to_name(col)
                worksheet.write_formula(
                    total_row,
                    col,
                    "=SUM(%s%s:%s%s)"
                    % (column_letter, header_row + 2, column_letter, header_row + len(lines) + 1),
                    total_format,
                )
        workbook.close()
        return output.getvalue()


class RealestateReportExportPdf(models.AbstractModel):
    _name = "report.realestate.report_realestate_export_pdf"
    _description = "Real Estate Export PDF Report"

    def _get_report_values(self, docids, data=None):
        docs = self.env["realestate.report.export.wizard"].browse(docids)
        return {
            "doc_ids": docids,
            "doc_model": "realestate.report.export.wizard",
            "docs": docs,
        }
