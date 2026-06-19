from datetime import date

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
        cls.product = cls.env["product.product"].create({"name": "Residential Rent", "detailed_type": "service"})
        cls.sar = cls.env.ref("base.SAR")

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
