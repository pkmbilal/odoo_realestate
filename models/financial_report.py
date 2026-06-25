from odoo import fields, models, tools

from .account_move import REAL_ESTATE_EXPENSE_CATEGORIES


class RealestateFinancialReport(models.Model):
    _name = "realestate.financial.report"
    _description = "Real Estate Financial Report"
    _auto = False
    _order = "date desc, id desc"

    date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    move_id = fields.Many2one("account.move", readonly=True)
    contract_id = fields.Many2one("realestate.contract", readonly=True)
    building_id = fields.Many2one("realestate.building", readonly=True)
    unit_id = fields.Many2one("realestate.unit", readonly=True)
    tenant_id = fields.Many2one("res.partner", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    line_type = fields.Selection(
        [("income", "Income"), ("expense", "Expense")],
        readonly=True,
    )
    expense_category = fields.Selection(REAL_ESTATE_EXPENSE_CATEGORIES, readonly=True)
    amount = fields.Monetary(readonly=True, currency_field="currency_id")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW realestate_financial_report AS (
                SELECT
                    move.id * 2 AS id,
                    COALESCE(move.invoice_date, move.date) AS date,
                    move.company_id AS company_id,
                    company.currency_id AS currency_id,
                    move.id AS move_id,
                    contract.id AS contract_id,
                    contract.building_id AS building_id,
                    contract.unit_id AS unit_id,
                    contract.tenant_id AS tenant_id,
                    move.partner_id AS partner_id,
                    'income' AS line_type,
                    NULL::varchar AS expense_category,
                    move.amount_total_signed AS amount
                FROM account_move move
                JOIN realestate_contract contract
                    ON contract.id = move.realestate_contract_id
                JOIN res_company company
                    ON company.id = move.company_id
                WHERE move.move_type IN ('out_invoice', 'out_refund')
                    AND move.state != 'cancel'

                UNION ALL

                SELECT
                    move.id * 2 + 1 AS id,
                    COALESCE(move.invoice_date, move.date) AS date,
                    move.company_id AS company_id,
                    company.currency_id AS currency_id,
                    move.id AS move_id,
                    NULL::integer AS contract_id,
                    move.realestate_expense_building_id AS building_id,
                    move.realestate_expense_unit_id AS unit_id,
                    NULL::integer AS tenant_id,
                    move.partner_id AS partner_id,
                    'expense' AS line_type,
                    move.realestate_expense_category AS expense_category,
                    -move.realestate_expense_amount AS amount
                FROM account_move move
                JOIN res_company company
                    ON company.id = move.company_id
                WHERE move.move_type IN ('in_invoice', 'in_refund')
                    AND move.state != 'cancel'
                    AND (
                        move.realestate_expense_category IS NOT NULL
                        OR move.realestate_expense_building_id IS NOT NULL
                        OR move.realestate_expense_unit_id IS NOT NULL
                    )
            )
            """
        )
