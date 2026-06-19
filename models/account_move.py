from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    realestate_contract_id = fields.Many2one(
        "realestate.contract", string="Rental Contract", copy=False, index=True, ondelete="restrict"
    )
    rental_period_start = fields.Date(copy=False, index=True)
    rental_period_end = fields.Date(copy=False)

    _sql_constraints = [
        (
            "realestate_contract_period_uniq",
            "unique(realestate_contract_id, rental_period_start)",
            "Only one invoice can be created for a contract rental period.",
        ),
    ]
