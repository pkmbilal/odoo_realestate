from odoo import api, fields, models


class RealestateDashboard(models.Model):
    _name = "realestate.dashboard"
    _description = "Real Estate Dashboard"
    _order = "company_id"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    _sql_constraints = [
        ("company_uniq", "unique(company_id)", "Only one dashboard record is allowed per company."),
    ]

    building_count = fields.Integer(compute="_compute_metrics")
    floor_count = fields.Integer(compute="_compute_metrics")
    unit_count = fields.Integer(compute="_compute_metrics")
    available_unit_count = fields.Integer(compute="_compute_metrics")
    occupied_unit_count = fields.Integer(compute="_compute_metrics")
    maintenance_unit_count = fields.Integer(compute="_compute_metrics")
    tenant_count = fields.Integer(compute="_compute_metrics")
    active_contract_count = fields.Integer(compute="_compute_metrics")
    invoice_due_count = fields.Integer(compute="_compute_metrics")
    invoice_overdue_count = fields.Integer(compute="_compute_metrics")

    @api.depends("company_id")
    def _compute_metrics(self):
        today = fields.Date.context_today(self)
        Building = self.env["realestate.building"]
        Floor = self.env["realestate.floor"]
        Unit = self.env["realestate.unit"]
        Partner = self.env["res.partner"]
        Contract = self.env["realestate.contract"]
        Move = self.env["account.move"]

        for dashboard in self:
            company_domain = [("company_id", "=", dashboard.company_id.id)]
            unit_company_domain = [("company_id", "=", dashboard.company_id.id)]
            partner_domain = [
                "&",
                ("is_tenant", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", dashboard.company_id.id),
            ]
            invoice_domain = [
                ("company_id", "=", dashboard.company_id.id),
                ("move_type", "=", "out_invoice"),
                ("realestate_contract_id", "!=", False),
                ("state", "!=", "cancel"),
            ]

            dashboard.building_count = Building.search_count(company_domain)
            dashboard.floor_count = Floor.search_count(company_domain)
            dashboard.unit_count = Unit.search_count(unit_company_domain)
            dashboard.available_unit_count = Unit.search_count(unit_company_domain + [("status", "=", "available")])
            dashboard.occupied_unit_count = Unit.search_count(unit_company_domain + [("status", "=", "occupied")])
            dashboard.maintenance_unit_count = Unit.search_count(
                unit_company_domain + [("status", "=", "maintenance")]
            )
            dashboard.tenant_count = Partner.search_count(partner_domain)
            dashboard.active_contract_count = Contract.search_count(company_domain + [("state", "=", "active")])

            due = 0
            overdue = 0
            for move in Move.search(invoice_domain):
                if move.payment_state == "paid":
                    continue
                due_date = move.invoice_date_due or move.invoice_date or today
                if due_date < today:
                    overdue += 1
                else:
                    due += 1
            dashboard.invoice_due_count = due
            dashboard.invoice_overdue_count = overdue

    @api.model
    def action_open_dashboard(self):
        dashboard = self.search([("company_id", "=", self.env.company.id)], limit=1)
        if not dashboard:
            dashboard = self.create({"company_id": self.env.company.id})
        action = self.env["ir.actions.actions"]._for_xml_id("realestate.action_realestate_dashboard")
        action["res_id"] = dashboard.id
        action["target"] = "current"
        return action

    def _open_action(self, xmlid, domain=None, context=None):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(xmlid)
        if domain is not None:
            action["domain"] = domain
        if context is not None:
            action["context"] = context
        return action

    def action_open_buildings(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_building",
            [("company_id", "=", self.company_id.id)],
            {"search_default_company_id": self.company_id.id},
        )

    def action_open_floors(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_floor",
            [("company_id", "=", self.company_id.id)],
            {"search_default_company_id": self.company_id.id},
        )

    def action_open_units(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_unit",
            [("company_id", "=", self.company_id.id)],
            {"search_default_company_id": self.company_id.id},
        )

    def action_open_available_units(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_unit",
            [("company_id", "=", self.company_id.id), ("status", "=", "available")],
        )

    def action_open_occupied_units(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_unit",
            [("company_id", "=", self.company_id.id), ("status", "=", "occupied")],
        )

    def action_open_tenants(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_tenant",
            ["&", ("is_tenant", "=", True), "|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)],
            {"default_is_tenant": True, "search_default_customer": 1},
        )

    def action_open_contracts(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_contract",
            [("company_id", "=", self.company_id.id)],
            {"search_default_company_id": self.company_id.id},
        )

    def action_open_active_contracts(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_contract",
            [("company_id", "=", self.company_id.id), ("state", "=", "active")],
        )

    def action_open_invoices(self):
        self.ensure_one()
        return self._open_action(
            "realestate.action_realestate_invoice",
            [("company_id", "=", self.company_id.id), ("realestate_contract_id", "!=", False)],
        )

    def action_open_due_invoices(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self._open_action(
            "realestate.action_realestate_invoice",
            [
                ("company_id", "=", self.company_id.id),
                ("realestate_contract_id", "!=", False),
                ("payment_state", "!=", "paid"),
                ("state", "!=", "cancel"),
                "|",
                ("invoice_date_due", "=", False),
                ("invoice_date_due", ">=", today),
            ],
        )

    def action_open_overdue_invoices(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self._open_action(
            "realestate.action_realestate_invoice",
            [
                ("company_id", "=", self.company_id.id),
                ("realestate_contract_id", "!=", False),
                ("payment_state", "!=", "paid"),
                ("state", "!=", "cancel"),
                ("invoice_date_due", "<", today),
            ],
        )

    def action_open_settings(self):
        self.ensure_one()
        return self.env["ir.actions.actions"]._for_xml_id("realestate.action_realestate_settings")
