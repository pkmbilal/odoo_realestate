from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RealestateContract(models.Model):
    _name = "realestate.contract"
    _description = "Rental Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    tenant_id = fields.Many2one(
        "res.partner", required=True, ondelete="restrict", domain="[('is_tenant', '=', True)]", tracking=True
    )
    unit_id = fields.Many2one(
        "realestate.unit", required=True, ondelete="restrict", tracking=True, index=True
    )
    building_id = fields.Many2one(related="unit_id.building_id", store=True)
    company_id = fields.Many2one(related="unit_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="unit_id.currency_id", store=True)
    rent_product_id = fields.Many2one(
        "product.product",
        required=True,
        ondelete="restrict",
        domain="[('detailed_type', '=', 'service')]",
        tracking=True,
    )
    rent_amount = fields.Monetary(required=True, tracking=True)
    deposit_amount = fields.Monetary(tracking=True)
    payment_cycle = fields.Selection(
        [("monthly", "Monthly"), ("quarterly", "Quarterly"), ("yearly", "Yearly")],
        required=True,
        default="monthly",
        tracking=True,
    )
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)
    next_invoice_date = fields.Date(copy=False, tracking=True)
    termination_date = fields.Date(readonly=True, copy=False, tracking=True)
    termination_reason = fields.Text(copy=False)
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("expired", "Expired"), ("terminated", "Terminated")],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    invoice_ids = fields.One2many("account.move", "realestate_contract_id")
    invoice_count = fields.Integer(compute="_compute_invoice_count")
    history_id = fields.Many2one("realestate.unit.history", readonly=True, copy=False)

    _sql_constraints = [
        ("rent_positive", "check(rent_amount > 0)", "Rent amount must be greater than zero."),
        ("deposit_nonnegative", "check(deposit_amount >= 0)", "Deposit amount cannot be negative."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("realestate.contract") or "New"
            if vals.get("start_date") and not vals.get("next_invoice_date"):
                vals["next_invoice_date"] = vals["start_date"]
        return super().create(vals_list)

    @api.onchange("unit_id")
    def _onchange_unit_id(self):
        if self.unit_id:
            self.rent_amount = self.unit_id.rent_amount
            self.deposit_amount = self.unit_id.deposit_amount

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.invoice_ids)

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for contract in self:
            if contract.start_date and contract.end_date and contract.end_date < contract.start_date:
                raise ValidationError(_("Contract end date must be on or after its start date."))

    @api.constrains("tenant_id")
    def _check_tenant(self):
        for contract in self:
            if not contract.tenant_id.is_tenant:
                raise ValidationError(_("The contract contact must be marked as a tenant."))

    @api.constrains("rent_product_id")
    def _check_rent_product(self):
        for contract in self:
            if contract.rent_product_id.detailed_type != "service":
                raise ValidationError(_("The rent product must be a service product."))

    @api.constrains("state", "unit_id", "start_date", "end_date")
    def _check_active_contract_overlap(self):
        for contract in self.filtered(lambda item: item.state == "active"):
            overlap = self.search_count(
                [
                    ("id", "!=", contract.id),
                    ("unit_id", "=", contract.unit_id.id),
                    ("state", "=", "active"),
                    ("start_date", "<=", contract.end_date),
                    ("end_date", ">=", contract.start_date),
                ]
            )
            if overlap:
                raise ValidationError(_("This unit already has an overlapping active contract."))

    def action_activate(self):
        for contract in self:
            if contract.state != "draft":
                raise UserError(_("Only draft contracts can be activated."))
            if contract.unit_id.status == "maintenance":
                raise UserError(_("A unit in maintenance cannot be occupied."))
            contract._check_active_contract_overlap()
            contract.write({"state": "active", "next_invoice_date": contract.next_invoice_date or contract.start_date})
            contract.unit_id.status = "occupied"
            history = self.env["realestate.unit.history"].create(
                {
                    "unit_id": contract.unit_id.id,
                    "contract_id": contract.id,
                    "tenant_id": contract.tenant_id.id,
                    "start_date": contract.start_date,
                }
            )
            contract.history_id = history
        return True

    def _close_contract(self, state, history_status):
        today = fields.Date.context_today(self)
        for contract in self:
            if contract.state != "active":
                raise UserError(_("Only active contracts can be closed."))
            values = {"state": state}
            if state == "terminated":
                values["termination_date"] = today
            contract.write(values)
            if contract.history_id:
                contract.history_id.write({"end_date": today, "status": history_status})
            other_active = self.search_count(
                [("unit_id", "=", contract.unit_id.id), ("state", "=", "active")]
            )
            if not other_active:
                contract.unit_id.status = "available"
        return True

    def action_terminate(self):
        return self._close_contract("terminated", "terminated")

    def action_vacate(self):
        return self._close_contract("terminated", "vacated")

    def action_expire(self):
        for contract in self:
            if contract.end_date > fields.Date.context_today(contract):
                raise UserError(_("A contract cannot expire before its end date."))
        return self._close_contract("expired", "expired")

    def _next_period_date(self, period_start):
        self.ensure_one()
        increments = {
            "monthly": relativedelta(months=1),
            "quarterly": relativedelta(months=3),
            "yearly": relativedelta(years=1),
        }
        return period_start + increments[self.payment_cycle]

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("Rent invoices can only be created for active contracts."))
        period_start = self.next_invoice_date or self.start_date
        if period_start > self.end_date:
            raise UserError(_("All rental periods in this contract have already been invoiced."))
        duplicate = self.env["account.move"].search_count(
            [
                ("realestate_contract_id", "=", self.id),
                ("rental_period_start", "=", period_start),
            ]
        )
        if duplicate:
            raise UserError(_("An invoice already exists for this rental period."))
        next_period = self._next_period_date(period_start)
        period_end = min(next_period - timedelta(days=1), self.end_date)
        cycle_multiplier = {"monthly": 1, "quarterly": 3, "yearly": 12}[self.payment_cycle]
        product = self.rent_product_id.with_company(self.company_id)
        taxes = product.taxes_id.filtered(lambda tax: tax.company_id == self.company_id)
        invoice = self.env["account.move"].with_company(self.company_id).create(
            {
                "move_type": "out_invoice",
                "partner_id": self.tenant_id.id,
                "company_id": self.company_id.id,
                "currency_id": self.currency_id.id,
                "invoice_date": fields.Date.context_today(self),
                "invoice_origin": self.name,
                "realestate_contract_id": self.id,
                "rental_period_start": period_start,
                "rental_period_end": period_end,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": _("Rent for %(unit)s: %(start)s to %(end)s", unit=self.unit_id.display_name, start=period_start, end=period_end),
                            "quantity": 1.0,
                            "price_unit": self.rent_amount * cycle_multiplier,
                            "tax_ids": [(6, 0, taxes.ids)],
                        },
                    )
                ],
            }
        )
        self.next_invoice_date = next_period
        return {
            "type": "ir.actions.act_window",
            "name": _("Rent Invoice"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": invoice.id,
        }

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("realestate.action_realestate_invoice")
        action["domain"] = [("realestate_contract_id", "=", self.id)]
        action["context"] = {"default_realestate_contract_id": self.id}
        return action
