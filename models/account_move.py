from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


REAL_ESTATE_EXPENSE_CATEGORIES = [
    ("maintenance", "Maintenance"),
    ("utilities", "Utilities"),
    ("cleaning", "Cleaning"),
    ("repairs", "Repairs"),
    ("security", "Security"),
    ("operations", "Operations"),
    ("owner_related", "Owner Related"),
    ("other", "Other"),
]


class AccountMove(models.Model):
    _inherit = "account.move"

    realestate_contract_id = fields.Many2one(
        "realestate.contract", string="Rental Contract", copy=False, index=True, ondelete="restrict"
    )
    rental_period_start = fields.Date(copy=False, index=True)
    rental_period_end = fields.Date(copy=False)
    realestate_expense_category = fields.Selection(
        REAL_ESTATE_EXPENSE_CATEGORIES,
        copy=False,
        tracking=True,
        index=True,
    )
    realestate_expense_building_id = fields.Many2one(
        "realestate.building",
        copy=False,
        tracking=True,
        index=True,
        ondelete="restrict",
    )
    realestate_expense_unit_id = fields.Many2one(
        "realestate.unit",
        copy=False,
        tracking=True,
        index=True,
        ondelete="restrict",
    )
    realestate_expense_amount = fields.Monetary(
        compute="_compute_realestate_expense_amount",
        store=True,
        currency_field="currency_id",
    )

    _sql_constraints = [
        (
            "realestate_contract_period_uniq",
            "unique(realestate_contract_id, rental_period_start)",
            "Only one invoice can be created for a contract rental period.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_expense_defaults(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._apply_expense_defaults(vals)
        return super().write(vals)

    @api.onchange("realestate_expense_unit_id")
    def _onchange_realestate_expense_unit_id(self):
        if self.realestate_expense_unit_id:
            self.realestate_expense_building_id = self.realestate_expense_unit_id.building_id

    @api.onchange("realestate_expense_building_id")
    def _onchange_realestate_expense_building_id(self):
        if (
            self.realestate_expense_unit_id
            and self.realestate_expense_unit_id.building_id != self.realestate_expense_building_id
        ):
            self.realestate_expense_unit_id = False

    @api.constrains("realestate_expense_building_id", "realestate_expense_unit_id")
    def _check_realestate_expense_location(self):
        for move in self.filtered(lambda item: item.move_type in ("in_invoice", "in_refund")):
            if move.realestate_expense_unit_id and move.realestate_expense_building_id:
                if move.realestate_expense_unit_id.building_id != move.realestate_expense_building_id:
                    raise ValidationError(
                        _(
                            "The selected expense unit must belong to the same building as the expense building."
                        )
                    )

    def _apply_expense_defaults(self, vals):
        unit_id = vals.get("realestate_expense_unit_id")
        building_id = vals.get("realestate_expense_building_id")
        if unit_id and not building_id:
            unit = self.env["realestate.unit"].browse(unit_id)
            vals["realestate_expense_building_id"] = unit.building_id.id

    @api.depends("amount_total_signed", "move_type")
    def _compute_realestate_expense_amount(self):
        for move in self:
            if move.move_type in ("in_invoice", "in_refund"):
                move.realestate_expense_amount = -move.amount_total_signed
            else:
                move.realestate_expense_amount = 0.0
