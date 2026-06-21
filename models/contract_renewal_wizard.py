from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RealestateContractRenewalWizard(models.TransientModel):
    _name = "realestate.contract.renewal.wizard"
    _description = "Contract Renewal Wizard"

    contract_id = fields.Many2one("realestate.contract", required=True, readonly=True)
    currency_id = fields.Many2one(related="contract_id.currency_id", readonly=True)
    current_start_date = fields.Date(related="contract_id.start_date", readonly=True)
    current_end_date = fields.Date(related="contract_id.end_date", readonly=True)
    current_payment_cycle = fields.Selection(related="contract_id.payment_cycle", readonly=True)
    current_rent_amount = fields.Monetary(
        related="contract_id.rent_amount", readonly=True, currency_field="currency_id"
    )
    current_deposit_amount = fields.Monetary(
        related="contract_id.deposit_amount", readonly=True, currency_field="currency_id"
    )

    new_end_date = fields.Date(required=True)
    rent_amount = fields.Monetary(currency_field="currency_id")
    deposit_amount = fields.Monetary(currency_field="currency_id")
    payment_cycle = fields.Selection(
        [("monthly", "Monthly"), ("quarterly", "Quarterly"), ("yearly", "Yearly")],
        required=True,
    )
    next_invoice_date = fields.Date()
    renewal_notes = fields.Text()

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        contract_id = self.env.context.get("active_id") or self.env.context.get("default_contract_id")
        contract = self.env["realestate.contract"].browse(contract_id)
        if not contract:
            return values

        values["contract_id"] = contract.id
        values.setdefault("payment_cycle", contract.payment_cycle)
        values.setdefault("rent_amount", contract.rent_amount)
        values.setdefault("deposit_amount", contract.deposit_amount)
        values.setdefault("next_invoice_date", contract.next_invoice_date or contract.end_date + relativedelta(days=1))
        values.setdefault("new_end_date", contract.end_date + self._cycle_delta(contract.payment_cycle))
        return values

    def action_confirm(self):
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("Renewal requires an active contract."))
        self.contract_id._apply_renewal(
            {
                "new_end_date": self.new_end_date,
                "rent_amount": self.rent_amount,
                "deposit_amount": self.deposit_amount,
                "payment_cycle": self.payment_cycle,
                "next_invoice_date": self.next_invoice_date,
                "renewal_notes": self.renewal_notes,
            }
        )
        return {"type": "ir.actions.act_window_close"}

    def _cycle_delta(self, payment_cycle):
        deltas = {
            "monthly": relativedelta(months=1),
            "quarterly": relativedelta(months=3),
            "yearly": relativedelta(years=1),
        }
        return deltas[payment_cycle]
