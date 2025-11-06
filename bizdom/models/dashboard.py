# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class BizdomDashboard(models.AbstractModel):  # Changed from models.Model to models.AbstractModel
    _name = 'bizdom.dashboard'
    _description = 'Bizdom Dashboard'

    # Remove _auto = False as it's not needed for abstract models

    @api.model
    def get_pillars(self):
        """Get list of all pillars with their details"""
        Pillar = self.env['bizdom.pillar']  # Replace with your actual pillar model
        return Pillar.search_read([], ['id', 'name', 'description', 'color'])

    # ... rest of your methods remain the same ...
    @api.model
    def get_scores(self, pillar_id):
        """Get favorite scores for a specific pillar"""
        Score = self.env['bizdom.score']  # Replace with your actual score model

        # Search for favorite scores for the given pillar
        scores = Score.search([
            ('pillar_id', '=', int(pillar_id)),
            ('is_favorite', '=', True)
        ])

        result = []
        for score in scores:
            result.append({
                'id': score.id,
                'name': score.name,
                'value': score.value,
                'target': score.target_value or 100,  # Default target if not set
                'progress': self._calculate_progress(score.value, score.target_value),
                'status': self._get_score_status(score.value, score.target_value),
                'last_updated': fields.Datetime.to_string(
                    score.write_date or score.create_date or fields.Datetime.now()),
            })
        return result

    def _calculate_progress(self, value, target):
        """Calculate progress percentage"""
        if not target or target == 0:
            return 0
        return min(100, round((value / target) * 100, 2))

    def _get_score_status(self, value, target):
        """Determine status based on value vs target"""
        if not target:
            return 'info'
        progress = (value / target) * 100
        if progress >= 90:
            return 'success'
        elif progress >= 70:
            return 'warning'
        return 'danger'

    @api.model
    def get_dashboard_data(self, pillar_id=None):
        """Get complete dashboard data for the given pillar"""
        pillars = self.get_pillars()

        # If no pillar_id provided, use the first one
        if not pillar_id and pillars:
            pillar_id = pillars[0]['id']

        scores = self.get_scores(pillar_id) if pillar_id else []

        return {
            'pillars': pillars,
            'scores': scores,
            'active_pillar': pillar_id,
            'last_updated': fields.Datetime.now(),
        }