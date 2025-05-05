from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    parent_id = fields.Many2one(
        'hr.department',
        string='Parent Department',
        ondelete='cascade'
    )

    def unlink(self):
        for department in self:
            # Recursively delete all children first
            department.child_ids.unlink()
        return super(HrDepartment, self).unlink()
