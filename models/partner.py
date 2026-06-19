from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_tenant = fields.Boolean(string="Tenant", tracking=True)
    iqama_id = fields.Char(string="Iqama / ID Number", tracking=True, copy=False)
    emergency_contact_name = fields.Char()
    emergency_contact_phone = fields.Char()
    tenant_document_ids = fields.Many2many(
        "ir.attachment",
        "realestate_tenant_attachment_rel",
        "partner_id",
        "attachment_id",
        string="Tenant Documents",
    )
    realestate_contract_ids = fields.One2many("realestate.contract", "tenant_id")
    realestate_contract_count = fields.Integer(compute="_compute_realestate_contract_count")

    def _compute_realestate_contract_count(self):
        for partner in self:
            partner.realestate_contract_count = len(partner.realestate_contract_ids)

    def action_view_realestate_contracts(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("realestate.action_realestate_contract")
        action["domain"] = [("tenant_id", "=", self.id)]
        action["context"] = {"default_tenant_id": self.id}
        return action
