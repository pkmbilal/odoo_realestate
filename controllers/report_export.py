import base64

from odoo import http
from odoo.http import request


class RealestateReportExportController(http.Controller):
    @http.route("/realestate/report/export/xlsx/<int:wizard_id>", type="http", auth="user")
    def download_xlsx(self, wizard_id, **kwargs):
        wizard = request.env["realestate.report.export.wizard"].browse(wizard_id).exists()
        if not wizard:
            return request.not_found()
        wizard.check_access_rights("read")
        wizard.check_access_rule("read")
        if not wizard.file_data:
            content = wizard._generate_xlsx()
            wizard.write({"file_data": base64.b64encode(content), "file_name": "%s.xlsx" % wizard._report_slug()})
        content = base64.b64decode(wizard.file_data)
        headers = [
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Length", len(content)),
            ("Content-Disposition", http.content_disposition(wizard.file_name or "%s.xlsx" % wizard._report_slug())),
        ]
        return request.make_response(content, headers=headers)
