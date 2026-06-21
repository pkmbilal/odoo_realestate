from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


UNIT_TAX_CLASSIFICATION = {
    "flat": "residential",
    "villa": "residential",
    "duplex": "residential",
    "residential_floor": "residential",
    "studio": "residential",
    "townhouse": "residential",
    "traditional_house": "residential",
    "annex": "residential",
    "room": "residential",
    "residential_rest_house": "residential",
    "office": "commercial",
    "shop": "commercial",
    "showroom": "commercial",
    "warehouse": "commercial",
    "commercial_center": "commercial",
    "kiosk": "commercial",
    "commercial_pavilion": "commercial",
}

UNIT_TYPE_DESCRIPTIONS = {
    "flat": "Standard multi-room housing unit within a shared residential building.",
    "villa": "Standalone, independent private house with multiple stories and a courtyard.",
    "duplex": "Half of a semi-detached building sharing one central dividing wall.",
    "residential_floor": "An entire isolated level inside a larger residential property leased out on its own.",
    "studio": "Single open-plan room combining sleeping, cooking, and living spaces.",
    "townhouse": "A narrow, multi-level attached row house sharing sidewalls with neighboring units.",
    "traditional_house": "Standard single-story brick or concrete classic home.",
    "annex": "A self-contained housing structure built atop a villa roof or in a courtyard.",
    "room": "A single room with shared or private facilities, often used for worker accommodation.",
    "residential_rest_house": "A family gathering or suburban vacation property leased long-term for residential use.",
    "office": "Dedicated corporate space, administrative rooms, or an entire office building floor.",
    "shop": "A street-level retail store, commercial outlet, or space within a shopping strip.",
    "showroom": "A large commercial space for product displays, car dealerships, or retail galleries.",
    "warehouse": "A storage facility, fulfillment hub, or inventory yard for commercial goods.",
    "commercial_center": "A leasable area inside a shopping mall or an entire commercial complex.",
    "kiosk": "A small standalone commercial stand in a mall, public square, or walkway.",
    "commercial_pavilion": "An open-air or covered event zone, temporary installation, or commercial courtyard space.",
}


class RealestateBuilding(models.Model):
    _name = "realestate.building"
    _description = "Real Estate Building"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    address = fields.Text()
    floor_ids = fields.One2many("realestate.floor", "building_id")
    unit_ids = fields.One2many("realestate.unit", "building_id")
    floor_count = fields.Integer(compute="_compute_counts")
    unit_count = fields.Integer(compute="_compute_counts")
    available_unit_count = fields.Integer(compute="_compute_counts")

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "Building code must be unique per company."),
    ]

    @api.depends("floor_ids", "unit_ids", "unit_ids.status")
    def _compute_counts(self):
        for building in self:
            building.floor_count = len(building.floor_ids)
            building.unit_count = len(building.unit_ids)
            building.available_unit_count = len(
                building.unit_ids.filtered(lambda unit: unit.status == "available")
            )

    def action_view_units(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("realestate.action_realestate_unit")
        action["domain"] = [("building_id", "=", self.id)]
        action["context"] = {"default_building_id": self.id}
        return action


class RealestateFloor(models.Model):
    _name = "realestate.floor"
    _description = "Real Estate Floor"
    _order = "building_id, sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    building_id = fields.Many2one(
        "realestate.building", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="building_id.company_id", store=True, index=True)
    unit_ids = fields.One2many("realestate.unit", "floor_id")
    unit_count = fields.Integer(compute="_compute_unit_count")

    _sql_constraints = [
        ("name_building_uniq", "unique(name, building_id)", "Floor name must be unique per building."),
    ]

    @api.depends("unit_ids")
    def _compute_unit_count(self):
        for floor in self:
            floor.unit_count = len(floor.unit_ids)


class RealestateUnit(models.Model):
    _name = "realestate.unit"
    _description = "Rentable Unit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "building_id, floor_id, name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    unit_type = fields.Selection(
        [
            ("flat", "Apartment (Flat)"),
            ("villa", "Villa"),
            ("duplex", "Duplex"),
            ("residential_floor", "Floor (Storey)"),
            ("studio", "Studio"),
            ("townhouse", "Townhouse"),
            ("traditional_house", "Traditional House (Bait Sha'abi)"),
            ("annex", "Annex (Arshia / Rooftop Housing)"),
            ("room", "Room"),
            ("residential_rest_house", "Residential Rest House (Istiraha)"),
            ("office", "Office"),
            ("shop", "Shop (Retail Unit)"),
            ("showroom", "Showroom / Exhibition Hall"),
            ("warehouse", "Warehouse / Logistics Unit"),
            ("commercial_center", "Commercial Center (Mall)"),
            ("kiosk", "Kiosk / Booth"),
            ("commercial_pavilion", "Commercial Pavilion / Space"),
            ("other", "Other"),
        ],
        required=True,
        default="flat",
        tracking=True,
    )
    tax_classification = fields.Selection(
        [("residential", "Residential"), ("commercial", "Commercial")],
        string="Tax Classification",
        tracking=True,
    )
    unit_type_description = fields.Text(compute="_compute_unit_type_description")
    building_id = fields.Many2one(
        "realestate.building", required=True, ondelete="restrict", tracking=True, index=True
    )
    floor_id = fields.Many2one(
        "realestate.floor",
        required=True,
        ondelete="restrict",
        tracking=True,
        domain="[('building_id', '=', building_id)]",
    )
    company_id = fields.Many2one(related="building_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.ref("base.SAR"),
        tracking=True,
    )
    rent_amount = fields.Monetary(required=True, tracking=True)
    deposit_amount = fields.Monetary(tracking=True)
    status = fields.Selection(
        [("available", "Available"), ("occupied", "Occupied"), ("maintenance", "Maintenance")],
        required=True,
        default="available",
        tracking=True,
        index=True,
    )
    maintenance_notes = fields.Text()
    contract_ids = fields.One2many("realestate.contract", "unit_id")
    current_contract_id = fields.Many2one(
        "realestate.contract", compute="_compute_current_contract", string="Current Contract"
    )
    history_ids = fields.One2many("realestate.unit.history", "unit_id")

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "Unit code must be unique per company."),
        ("rent_positive", "check(rent_amount > 0)", "Rent amount must be greater than zero."),
        ("deposit_nonnegative", "check(deposit_amount >= 0)", "Deposit amount cannot be negative."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if "tax_classification" not in values:
                unit_type = values.get("unit_type", "flat")
                values["tax_classification"] = UNIT_TAX_CLASSIFICATION.get(unit_type)
        return super().create(vals_list)

    def write(self, values):
        if "unit_type" in values and "tax_classification" not in values:
            values["tax_classification"] = UNIT_TAX_CLASSIFICATION.get(values["unit_type"])
        return super().write(values)

    @api.onchange("unit_type")
    def _onchange_unit_type(self):
        self.tax_classification = UNIT_TAX_CLASSIFICATION.get(self.unit_type)

    @api.depends("unit_type")
    def _compute_unit_type_description(self):
        for unit in self:
            description = UNIT_TYPE_DESCRIPTIONS.get(unit.unit_type)
            unit.unit_type_description = _(description) if description else False

    @api.depends("contract_ids.state")
    def _compute_current_contract(self):
        for unit in self:
            unit.current_contract_id = unit.contract_ids.filtered(
                lambda contract: contract.state == "active"
            )[:1]

    @api.constrains("floor_id", "building_id")
    def _check_floor_building(self):
        for unit in self:
            if unit.floor_id.building_id != unit.building_id:
                raise ValidationError(_("The selected floor does not belong to the building."))

    @api.constrains("currency_id")
    def _check_saudi_riyal_currency(self):
        sar = self.env.ref("base.SAR")
        for unit in self:
            if unit.currency_id != sar:
                raise ValidationError(_("Real estate units must use Saudi Riyal (SAR)."))

    @api.constrains("status")
    def _check_status_matches_contract(self):
        for unit in self:
            has_active_contract = bool(
                self.env["realestate.contract"].search_count(
                    [("unit_id", "=", unit.id), ("state", "=", "active")], limit=1
                )
            )
            if unit.status == "occupied" and not has_active_contract:
                raise ValidationError(_("An occupied unit must have an active contract."))
            if unit.status != "occupied" and has_active_contract:
                raise ValidationError(_("A unit with an active contract must remain occupied."))

    def action_set_maintenance(self):
        for unit in self:
            if unit.current_contract_id:
                raise ValidationError(_("An occupied unit cannot be placed in maintenance."))
            unit.status = "maintenance"

    def action_set_available(self):
        for unit in self:
            if unit.current_contract_id:
                raise ValidationError(_("An occupied unit cannot be marked available."))
            unit.status = "available"


class RealestateUnitHistory(models.Model):
    _name = "realestate.unit.history"
    _description = "Unit Occupancy History"
    _order = "start_date desc, id desc"

    unit_id = fields.Many2one("realestate.unit", required=True, ondelete="cascade", index=True)
    contract_id = fields.Many2one("realestate.contract", required=True, ondelete="cascade", index=True)
    tenant_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    start_date = fields.Date(required=True)
    end_date = fields.Date()
    status = fields.Selection(
        [("occupied", "Occupied"), ("vacated", "Vacated"), ("terminated", "Terminated"), ("expired", "Expired")],
        required=True,
        default="occupied",
    )
    company_id = fields.Many2one(related="unit_id.company_id", store=True, index=True)

    _sql_constraints = [
        ("contract_uniq", "unique(contract_id)", "A contract can have only one occupancy history entry."),
    ]
