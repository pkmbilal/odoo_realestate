from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    realestate_residential_tax_id = fields.Many2one(
        "account.tax",
        string="Residential Exempt Tax",
        check_company=True,
        help="Sales tax representing the configured Saudi residential rental exemption.",
    )
    realestate_commercial_tax_id = fields.Many2one(
        "account.tax",
        string="Commercial VAT Tax",
        check_company=True,
        help="Sales tax representing the configured Saudi commercial rental VAT treatment.",
    )

    @api.constrains("realestate_residential_tax_id", "realestate_commercial_tax_id")
    def _check_realestate_taxes(self):
        for company in self:
            taxes = company.realestate_residential_tax_id | company.realestate_commercial_tax_id
            if any(tax.company_id != company or tax.type_tax_use != "sale" for tax in taxes):
                raise ValidationError(
                    _("Realestate taxes must be sales taxes belonging to the configured company.")
                )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    realestate_residential_tax_id = fields.Many2one(
        related="company_id.realestate_residential_tax_id",
        readonly=False,
        domain="[('type_tax_use', '=', 'sale'), ('company_id', '=', company_id)]",
    )
    realestate_commercial_tax_id = fields.Many2one(
        related="company_id.realestate_commercial_tax_id",
        readonly=False,
        domain="[('type_tax_use', '=', 'sale'), ('company_id', '=', company_id)]",
    )
