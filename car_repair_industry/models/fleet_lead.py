from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.http import request


class FleetLead(models.Model):
    _inherit = 'crm.lead'

    vehicle_model_id = fields.Many2one('fleet.vehicle.model', string='Vehicle Model')
    vehicle_brand_id = fields.Many2one('fleet.vehicle.model.brand', string='Vehicle Brand')
    medium_type = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Medium Type', default='online', store=True)
    question_line_ids = fields.One2many('fleet.lead.question.line', 'lead_id')
    lead_date = fields.Date(
        string='Lead Date',
        default=fields.Date.today,
        tracking=True,
        help='Date when the lead was received. Can be set to previous months for historical data.'
    )


    def def_action_quality_lead(self):
        """Move lead to Quality Lead stage (sequence 1)"""
        stage = self._stage_find(domain=[('sequence', '=', 1)])
        self.stage_id = stage.id if stage else False

    def def_action_convert(self):
        """Move lead to Converted stage (sequence 2)"""
        stage = self._stage_find(domain=[('sequence', '=', 2)])
        self.stage_id = stage.id if stage else False

    def def_reset_new_lead(self):
        """Reset lead to New Lead stage (sequence 0)"""
        stage = self._stage_find(domain=[('sequence', '=', 0)])
        self.stage_id = stage.id if stage else False


    @api.model
    def default_get(self, fields_list):
        res = super(FleetLead, self).default_get(fields_list)
        if 'question_line_ids' not in res and self._context.get('default_question_line_ids') is None:
            try:
                questions = self.env['fleet.lead.question'].search([
                    ('active', '=', True)
                ], order='sequence, id')
                if questions:
                    res['question_line_ids'] = [(0, 0, {
                        'question_id': q.id,
                    }) for q in questions]
            except Exception:
                # If questions model is not available yet, skip
                pass
        return res

    def action_open_crm_lead(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'CRM Lead',
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    @api.model
    def action_open_lead_view(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Leads',
            'res_model': 'crm.lead',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def _count_answered_questions(self, question_line_ids_vals=None):
        """
        Count how many questions have been answered (answer field is not empty).
        If question_line_ids_vals is provided, also count from incoming One2many commands.
        """
        self.ensure_one()
        answered_count = 0
        processed_line_ids = set()  # Line IDs that are being modified by commands
        deleted_line_ids = set()  # Line IDs that are being deleted
        
        # Process incoming vals if provided (One2many commands)
        if question_line_ids_vals:
            # Get all existing question lines as a dict for quick lookup
            existing_lines = {line.id: line for line in self.question_line_ids}
            
            for command in question_line_ids_vals:
                cmd_type = command[0]
                
                if cmd_type == 0:  # CREATE: (0, 0, {values})
                    # Count if new line has an answer
                    if command[2] and command[2].get('answer'):
                        answered_count += 1
                
                elif cmd_type == 1:  # UPDATE: (1, id, {values})
                    line_id = command[1]
                    processed_line_ids.add(line_id)
                    # If answer field is in the update values
                    if command[2] and 'answer' in command[2]:
                        # Use the new answer value
                        if command[2].get('answer'):
                            answered_count += 1
                    else:
                        # Answer not being updated, use existing answer if any
                        if line_id in existing_lines and existing_lines[line_id].answer:
                            answered_count += 1
                
                elif cmd_type == 2:  # DELETE: (2, id)
                    deleted_line_ids.add(command[1])
                    processed_line_ids.add(command[1])
                
                elif cmd_type == 6:  # REPLACE ALL: (6, 0, [ids])
                    # Mark all existing lines as processed
                    processed_line_ids.update(existing_lines.keys())
                    # Only keep lines in the replacement list
                    replacement_ids = set(command[2] or [])
                    # Count answers from lines that will remain
                    for line_id in replacement_ids:
                        if line_id in existing_lines and existing_lines[line_id].answer:
                            answered_count += 1
                    # Unprocessed lines are being removed, so don't count them
        
        # Count answers from existing question lines that are not being modified
        for question_line in self.question_line_ids:
            # Skip lines that are being deleted or already processed
            if question_line.id in deleted_line_ids:
                continue
            if question_line.id not in processed_line_ids and question_line.answer:
                answered_count += 1
        
        return answered_count

    def write(self, vals):
        """Override write to validate questions before moving to Quality Lead stage"""
        # Check if stage_id is being changed to Quality Lead
        if 'stage_id' in vals and vals.get('stage_id'):
            quality_lead_stage = self.env['crm.stage'].browse(vals['stage_id'])
            
            if quality_lead_stage.exists() and quality_lead_stage.name == 'Quality Lead':
                # Get question_line_ids commands from vals if present
                question_line_ids_vals = vals.get('question_line_ids')
                
                # Validate each lead being updated
                for lead in self:
                    # Count answers considering both existing and incoming values
                    answered_count = lead._count_answered_questions(question_line_ids_vals)
                    min_required = 2
                    
                    if answered_count < min_required:
                        raise UserError(_(
                            'Before proceeding to Quality Lead stage, please answer at least %d question(s).\n\n'
                            'Currently, you have answered %d question(s).\n\n'
                            'Please answer at least %d question(s) before moving to Quality Lead stage.'
                        ) % (min_required, answered_count, min_required))
        
        return super(FleetLead, self).write(vals)


class FleetLeadQuestionLine(models.Model):
    _name = 'fleet.lead.question.line'
    _description = 'Fleet Lead Question Line'

    lead_id = fields.Many2one('crm.lead', string='Lead', required=True, ondelete='cascade')
    question_id = fields.Many2one(
        'fleet.lead.question',
        string='Question',
        required=True,
        domain="[('active', '=', True)]",
        ondelete='cascade'
    )
    answer = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='Answer')
    comment = fields.Text(string='Comment')



class FleetLeadQuestion(models.Model):
    _name = "fleet.lead.question"
    _description = "Fleet Lead Question"

    name = fields.Text(string="Question")
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(string="Sequence", default=10)
