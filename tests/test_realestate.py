from datetime import date
import io
import zipfile

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestRealestate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.building = cls.env["realestate.building"].create({"name": "North Tower", "code": "NT"})
        cls.floor = cls.env["realestate.floor"].create({"name": "Ground", "building_id": cls.building.id})
        cls.unit = cls.env["realestate.unit"].create(
            {"name": "Unit 101", "code": "NT-101", "building_id": cls.building.id, "floor_id": cls.floor.id, "rent_amount": 1200, "deposit_amount": 500}
        )
        cls.tenant = cls.env["res.partner"].create({"name": "Test Tenant", "is_tenant": True})
        cls.product = cls.env["product.product"].search([("detailed_type", "=", "service")], limit=1)
        if not cls.product:
            cls.product = cls.env["product.product"].create({"name": "Residential Rent", "detailed_type": "service"})
        cls.sar = cls.env.ref("base.SAR")
        cls.residential_tax = cls.env["account.tax"].create(
            {
                "name": "Residential Rent Exempt",
                "amount": 0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.env.company.id,
            }
        )
        cls.commercial_tax = cls.env["account.tax"].create(
            {
                "name": "Commercial Rent VAT 15%",
                "amount": 15,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.env.company.id,
            }
        )
        cls.product_tax = cls.env["account.tax"].create(
            {
                "name": "Product Tax Must Not Be Used",
                "amount": 5,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.env.company.id,
            }
        )
        cls.product.taxes_id = cls.product_tax
        cls.env.company.write(
            {
                "realestate_residential_tax_id": cls.residential_tax.id,
                "realestate_commercial_tax_id": cls.commercial_tax.id,
            }
        )

    def _create_contract(self, **overrides):
        values = {
            "tenant_id": self.tenant.id,
            "unit_id": self.unit.id,
            "rent_product_id": self.product.id,
            "rent_amount": 1200,
            "deposit_amount": 500,
            "payment_cycle": "monthly",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
        }
        values.update(overrides)
        return self.env["realestate.contract"].create(values)

    def test_contract_activation_and_vacating(self):
        contract = self._create_contract()
        contract.action_activate()
        self.assertEqual(contract.state, "active")
        self.assertEqual(self.unit.status, "occupied")
        self.assertEqual(contract.history_id.tenant_id, self.tenant)
        contract.action_vacate()
        self.assertEqual(contract.state, "terminated")
        self.assertEqual(self.unit.status, "available")
        self.assertEqual(contract.history_id.status, "vacated")

    def test_overlapping_active_contract_is_rejected(self):
        self._create_contract().action_activate()
        second = self._create_contract()
        with self.assertRaises(ValidationError):
            second.action_activate()

    def test_manual_invoice_and_period_progression(self):
        contract = self._create_contract()
        contract.action_activate()
        action = contract.action_create_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.realestate_contract_id, contract)
        self.assertEqual(invoice.rental_period_start, date(2026, 1, 1))
        self.assertEqual(invoice.rental_period_end, date(2026, 1, 31))
        self.assertEqual(contract.next_invoice_date, date(2026, 2, 1))
        self.assertEqual(invoice.invoice_line_ids.price_unit, 1200)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.residential_tax)
        self.assertEqual(contract.currency_id, self.sar)
        self.assertEqual(invoice.currency_id, self.sar)

    def test_invoice_requires_active_contract(self):
        with self.assertRaises(UserError):
            self._create_contract().action_create_invoice()

    def test_quarterly_invoice_uses_three_months_rent(self):
        contract = self._create_contract(payment_cycle="quarterly")
        contract.action_activate()
        action = contract.action_create_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(invoice.invoice_line_ids.price_unit, 3600)
        self.assertEqual(invoice.rental_period_end, date(2026, 3, 31))
        self.assertEqual(contract.next_invoice_date, date(2026, 4, 1))
        self.assertEqual(invoice.currency_id, self.sar)

    def test_units_require_saudi_riyal(self):
        usd = self.env.ref("base.USD")
        with self.assertRaises(ValidationError):
            self.unit.currency_id = usd

    def test_invalid_contract_dates(self):
        with self.assertRaises(ValidationError):
            self._create_contract(start_date=date(2026, 2, 1), end_date=date(2026, 1, 1))

    def test_contract_requires_tenant_contact(self):
        contact = self.env["res.partner"].create({"name": "Not a Tenant"})
        with self.assertRaises(ValidationError):
            self._create_contract(tenant_id=contact.id)

    def test_cron_generates_all_due_rental_periods(self):
        today = date.today()
        contract = self._create_contract(
            start_date=today.replace(day=1) - relativedelta(months=2),
            end_date=today,
        )
        contract.action_activate()

        invoice_count = self.env["realestate.contract"]._cron_generate_due_invoices()

        self.assertEqual(invoice_count, 3)
        self.assertEqual(contract.invoice_count, 3)
        self.assertGreater(contract.next_invoice_date, contract.end_date)

    def test_cron_ignores_future_invoice_dates(self):
        contract = self._create_contract()
        contract.action_activate()
        contract.next_invoice_date = date.today().replace(year=date.today().year + 1)

        invoice_count = self.env["realestate.contract"]._cron_generate_due_invoices()

        self.assertEqual(invoice_count, 0)
        self.assertFalse(contract.invoice_ids)

    def test_unit_types_default_tax_classification_and_description(self):
        residential_types = {
            "flat",
            "villa",
            "duplex",
            "residential_floor",
            "studio",
            "townhouse",
            "traditional_house",
            "annex",
            "room",
            "residential_rest_house",
        }
        commercial_types = {
            "office",
            "shop",
            "showroom",
            "warehouse",
            "commercial_center",
            "kiosk",
            "commercial_pavilion",
        }
        for unit_type in residential_types:
            self.unit.unit_type = unit_type
            self.assertEqual(self.unit.tax_classification, "residential")
            self.assertTrue(self.unit.unit_type_description)
        for unit_type in commercial_types:
            self.unit.unit_type = unit_type
            self.assertEqual(self.unit.tax_classification, "commercial")
            self.assertTrue(self.unit.unit_type_description)

    def test_commercial_invoice_uses_company_vat_not_product_tax(self):
        self.unit.unit_type = "warehouse"
        contract = self._create_contract()
        contract.action_activate()

        action = contract.action_create_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])

        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.commercial_tax)
        self.assertNotIn(self.product_tax, invoice.invoice_line_ids.tax_ids)

    def test_unclassified_other_unit_cannot_be_invoiced(self):
        self.unit.unit_type = "other"
        contract = self._create_contract()
        contract.action_activate()

        with self.assertRaisesRegex(UserError, "tax classification"):
            contract.action_create_invoice()

    def test_missing_applicable_tax_configuration_blocks_invoice(self):
        self.env.company.realestate_residential_tax_id = False
        contract = self._create_contract()
        contract.action_activate()

        with self.assertRaisesRegex(UserError, "Residential Exempt Tax"):
            contract.action_create_invoice()

    def test_company_rejects_another_companys_rent_tax(self):
        other_company = self.env["res.company"].create(
            {"name": "Other Realestate Company", "country_id": self.env.ref("base.sa").id}
        )
        other_tax_group = self.env["account.tax.group"].create(
            {"name": "Other Company Taxes", "company_id": other_company.id}
        )
        other_tax = self.env["account.tax"].with_company(other_company).create(
            {
                "name": "Other Company VAT",
                "amount": 15,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": other_company.id,
                "tax_group_id": other_tax_group.id,
            }
        )

        with self.assertRaises(UserError):
            self.env.company.realestate_commercial_tax_id = other_tax

    def test_contract_renewal_extends_the_active_contract(self):
        contract = self._create_contract()
        contract.action_activate()

        wizard = self.env["realestate.contract.renewal.wizard"].with_context(active_id=contract.id).create(
            {
                "contract_id": contract.id,
                "new_end_date": date(2027, 12, 31),
                "payment_cycle": "yearly",
                "rent_amount": 1500,
                "deposit_amount": 750,
                "next_invoice_date": date(2027, 1, 1),
                "renewal_notes": "Extended for another term.",
            }
        )
        wizard.action_confirm()

        self.assertEqual(contract.end_date, date(2027, 12, 31))
        self.assertEqual(contract.renewal_count, 1)
        self.assertEqual(contract.rent_amount, 1500)
        self.assertEqual(contract.deposit_amount, 750)
        self.assertEqual(contract.payment_cycle, "yearly")
        self.assertEqual(contract.next_invoice_date, date(2027, 1, 1))
        self.assertEqual(self.unit.status, "occupied")

    def test_dashboard_counts_reflect_portfolio_state(self):
        dashboard = self.env["realestate.dashboard"].search([("company_id", "=", self.env.company.id)], limit=1)

        self.assertEqual(dashboard.building_count, 1)
        self.assertEqual(dashboard.floor_count, 1)
        self.assertEqual(dashboard.unit_count, 1)
        self.assertEqual(dashboard.available_unit_count, 1)
        self.assertEqual(dashboard.occupied_unit_count, 0)
        self.assertEqual(dashboard.maintenance_unit_count, 0)
        self.assertEqual(dashboard.tenant_count, 1)
        self.assertEqual(dashboard.active_contract_count, 0)

        contract = self._create_contract()
        contract.action_activate()
        dashboard.invalidate_recordset()

        self.assertEqual(dashboard.available_unit_count, 0)
        self.assertEqual(dashboard.occupied_unit_count, 1)
        self.assertEqual(dashboard.active_contract_count, 1)

    def test_dashboard_actions_return_expected_domains(self):
        dashboard = self.env["realestate.dashboard"].search([("company_id", "=", self.env.company.id)], limit=1)

        self.assertEqual(dashboard.action_open_dashboard()["res_id"], dashboard.id)
        self.assertEqual(
            dashboard.action_open_available_units()["domain"],
            [("company_id", "=", self.env.company.id), ("status", "=", "available")],
        )
        self.assertEqual(
            dashboard.action_open_occupied_units()["domain"],
            [("company_id", "=", self.env.company.id), ("status", "=", "occupied")],
        )
        self.assertEqual(
            dashboard.action_open_active_contracts()["domain"],
            [("company_id", "=", self.env.company.id), ("state", "=", "active")],
        )
        self.assertEqual(
            dashboard.action_open_overdue_invoices()["domain"],
            [
                ("company_id", "=", self.env.company.id),
                ("realestate_contract_id", "!=", False),
                ("payment_state", "!=", "paid"),
                ("state", "!=", "cancel"),
                ("invoice_date_due", "<", date.today()),
            ],
        )

    def test_dashboard_invoice_kpis_split_due_and_overdue(self):
        dashboard = self.env["realestate.dashboard"].search([("company_id", "=", self.env.company.id)], limit=1)
        other_building = self.env["realestate.building"].create({"name": "South Tower", "code": "ST"})
        other_floor = self.env["realestate.floor"].create({"name": "Ground", "building_id": other_building.id})
        other_unit = self.env["realestate.unit"].create(
            {
                "name": "Unit 201",
                "code": "ST-201",
                "building_id": other_building.id,
                "floor_id": other_floor.id,
                "rent_amount": 2000,
                "deposit_amount": 500,
            }
        )
        other_tenant = self.env["res.partner"].create({"name": "Second Tenant", "is_tenant": True})
        second_contract = self.env["realestate.contract"].create(
            {
                "tenant_id": other_tenant.id,
                "unit_id": other_unit.id,
                "rent_product_id": self.product.id,
                "rent_amount": 2000,
                "deposit_amount": 500,
                "payment_cycle": "monthly",
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
            }
        )

        first_contract = self._create_contract()
        first_contract.action_activate()
        second_contract.action_activate()

        first_invoice = first_contract.action_create_invoice()
        second_invoice = second_contract.action_create_invoice()
        overdue_invoice = self.env["account.move"].browse(first_invoice["res_id"])
        due_invoice = self.env["account.move"].browse(second_invoice["res_id"])
        overdue_invoice.write({"invoice_date_due": date.today() - relativedelta(days=3)})
        due_invoice.write({"invoice_date_due": date.today() + relativedelta(days=3)})

        dashboard.invalidate_recordset()

        self.assertEqual(dashboard.invoice_overdue_count, 1)
        self.assertEqual(dashboard.invoice_due_count, 1)

    def test_vendor_bill_expense_metadata_defaults_building_from_unit(self):
        vendor = self.env["res.partner"].create({"name": "Maintenance Vendor", "supplier_rank": 1})
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": vendor.id,
                "invoice_date": date.today(),
                "realestate_expense_category": "maintenance",
                "realestate_expense_unit_id": self.unit.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Minor repair work",
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 250,
                        },
                    )
                ],
            }
        )

        self.assertEqual(bill.realestate_expense_building_id, self.building)
        self.assertEqual(bill.realestate_expense_unit_id, self.unit)
        self.assertEqual(bill.realestate_expense_category, "maintenance")

        dashboard = self.env["realestate.dashboard"].search([("company_id", "=", self.env.company.id)], limit=1)
        dashboard.invalidate_recordset()

        self.assertEqual(dashboard.expense_bill_count, 1)
        self.assertEqual(dashboard.expense_month_total, 250)

    def test_mismatched_expense_building_and_unit_is_rejected(self):
        vendor = self.env["res.partner"].create({"name": "Utilities Vendor", "supplier_rank": 1})
        other_building = self.env["realestate.building"].create({"name": "East Tower", "code": "ET"})
        other_floor = self.env["realestate.floor"].create({"name": "Ground", "building_id": other_building.id})
        other_unit = self.env["realestate.unit"].create(
            {
                "name": "Unit 301",
                "code": "ET-301",
                "building_id": other_building.id,
                "floor_id": other_floor.id,
                "rent_amount": 1500,
                "deposit_amount": 500,
            }
        )

        with self.assertRaises(ValidationError):
            self.env["account.move"].create(
                {
                    "move_type": "in_invoice",
                    "partner_id": vendor.id,
                    "invoice_date": date.today(),
                    "realestate_expense_category": "utilities",
                    "realestate_expense_building_id": self.building.id,
                    "realestate_expense_unit_id": other_unit.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Power bill",
                                "product_id": self.product.id,
                                "quantity": 1.0,
                                "price_unit": 300,
                            },
                        )
                    ],
                }
            )

    def test_expense_actions_open_vendor_bills_and_reports(self):
        dashboard = self.env["realestate.dashboard"].search([("company_id", "=", self.env.company.id)], limit=1)

        self.assertEqual(
            dashboard.action_open_expenses()["domain"],
            [("company_id", "=", self.env.company.id), ("move_type", "in", ("in_invoice", "in_refund"))],
        )
        self.assertEqual(
            dashboard.action_open_expense_reports()["domain"],
            [
                ("company_id", "=", self.env.company.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "!=", "cancel"),
                "|",
                "|",
                ("realestate_expense_category", "!=", False),
                ("realestate_expense_building_id", "!=", False),
                ("realestate_expense_unit_id", "!=", False),
            ],
        )

    def test_financial_report_combines_income_and_expenses(self):
        contract = self._create_contract()
        contract.action_activate()
        invoice_action = contract.action_create_invoice()
        invoice = self.env["account.move"].browse(invoice_action["res_id"])

        vendor = self.env["res.partner"].create({"name": "Cleaning Vendor", "supplier_rank": 1})
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": vendor.id,
                "invoice_date": date.today(),
                "realestate_expense_category": "cleaning",
                "realestate_expense_building_id": self.building.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Common area cleaning",
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 300,
                        },
                    )
                ],
            }
        )

        income_line = self.env["realestate.financial.report"].search(
            [("move_id", "=", invoice.id), ("line_type", "=", "income")],
            limit=1,
        )
        expense_line = self.env["realestate.financial.report"].search(
            [("move_id", "=", bill.id), ("line_type", "=", "expense")],
            limit=1,
        )

        self.assertEqual(income_line.building_id, self.building)
        self.assertEqual(income_line.unit_id, self.unit)
        self.assertEqual(income_line.tenant_id, self.tenant)
        self.assertEqual(income_line.amount, invoice.amount_total_signed)
        self.assertEqual(expense_line.building_id, self.building)
        self.assertEqual(expense_line.expense_category, "cleaning")
        self.assertEqual(expense_line.amount, -300)

    def test_report_actions_are_registered(self):
        report_actions = {
            "realestate.action_realestate_rent_collection_report": "account.move",
            "realestate.action_realestate_rent_due_report": "account.move",
            "realestate.action_realestate_tenant_outstanding_report": "account.move",
            "realestate.action_realestate_building_income_report": "realestate.financial.report",
            "realestate.action_realestate_profit_analysis_report": "realestate.financial.report",
            "realestate.action_realestate_vat_report": "account.move",
        }
        for xmlid, model in report_actions.items():
            action = self.env.ref(xmlid)
            self.assertEqual(action.res_model, model)

    def test_report_export_wizard_actions_are_registered(self):
        action = self.env.ref("realestate.action_realestate_report_export_wizard")
        pdf_action = self.env.ref("realestate.action_report_realestate_export_pdf")

        self.assertEqual(action.res_model, "realestate.report.export.wizard")
        self.assertEqual(action.target, "new")
        self.assertEqual(pdf_action.model, "realestate.report.export.wizard")
        self.assertEqual(pdf_action.report_type, "qweb-pdf")

    def test_report_export_wizard_generates_pdf_action_and_xlsx(self):
        contract = self._create_contract()
        contract.action_activate()
        invoice_action = contract.action_create_invoice()
        self.env["account.move"].browse(invoice_action["res_id"]).invoice_date = date(2026, 1, 1)
        wizard = self.env["realestate.report.export.wizard"].create(
            {
                "report_type": "rent_collection",
                "date_from": date(2026, 1, 1),
                "date_to": date(2026, 1, 31),
                "building_id": self.building.id,
                "tenant_id": self.tenant.id,
            }
        )

        lines = wizard._get_report_lines()
        pdf_action = wizard.action_print_pdf()
        xlsx_content = wizard._generate_xlsx()

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["tenant"], self.tenant.display_name)
        self.assertIn(pdf_action["type"], ("ir.actions.report", "ir.actions.act_window"))
        if pdf_action["type"] == "ir.actions.act_window":
            self.assertEqual(pdf_action["context"]["report_action"]["type"], "ir.actions.report")
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(xlsx_content)))

    def test_report_export_wizard_rejects_invalid_date_range(self):
        wizard = self.env["realestate.report.export.wizard"].create(
            {
                "report_type": "rent_collection",
                "date_from": date(2026, 2, 1),
                "date_to": date(2026, 1, 1),
            }
        )

        with self.assertRaises(UserError):
            wizard.action_print_pdf()
