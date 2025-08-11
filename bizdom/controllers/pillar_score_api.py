from odoo import http
from odoo.http import request


class ScoreAPI(http.Controller):

    # API to create a score under a pillar ID
    @http.route('/api/score/<int:pillar_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def create_score(self, pillar_id, **kwargs):
        name = kwargs.get('name')
        company_id = kwargs.get('company_id')
        if not name or not company_id:
            return {'error': 'Name, and company_id are required'}

        company = request.env['res.company'].sudo().browse(company_id)
        if not company.exists():
            return {'error': 'Company not found'}

        pillar = request.env['bizdom.pillar'].sudo().browse(pillar_id)
        if not pillar.exists():
            return {'error': 'Pillar not found'}

        score = request.env['bizdom.score'].sudo().create({
            'score_name': name,
            'pillar_id': pillar.id,
            'company_id': company.id
        })

        return {
            'message': 'Score created successfully',
        }

    # Api to get or display all scores under a pillar ID
    @http.route('/api/scores/<int:pillar_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_scores(self, pillar_id):
        scores = request.env['bizdom.score'].sudo().search([
            ('pillar_id', '=', pillar_id),

        ])
        score_list = []

        for score in scores:
            score_list.append({
                'id': score.id,
                'name': score.score_name
            })
        return score_list

    #  Api to get a score by its ID
    @http.route('/api/score/<int:score_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_score(self, score_id):
        score = request.env['bizdom.score'].sudo().browse(score_id)
        if not score.exists():
            return {'error': 'Score not found'}
        return {
            'id': score.id,
            'name': score.score_name,
            'pillar_name': score.pillar_id.name
        }

    #  API to update the name, the type and min and max value of a score and to update favorite
    @http.route('/api/score/<int:score_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_score(self, score_id, **kwargs):
        score = request.env['bizdom.score'].sudo().browse(score_id)
        if not score.exists():
            return {'error': 'Score not found'}
        name = kwargs.get('name')
        type = kwargs.get('type')
        max_score_percentage = kwargs.get('max_score_percentage')
        min_score_percentage = kwargs.get('min_score_percentage')
        max_score_number = kwargs.get('max_score_number')
        min_score_number = kwargs.get('min_score_number')
        favorite = kwargs.get('favorite')

        if type == 'percentage':
            if max_score_percentage is not None:
                print(max_score_percentage)
                max_score_percentage /= 100
            if min_score_percentage is not None:
                min_score_percentage /= 100

        # if the total number of favorite scores for a pillar is 3, then it will not allow to add more favorite scores
        if favorite:
            favorites = request.env['bizdom.score'].sudo().search_count([
                ('favorite', '=', True),
                ('pillar_id', '=', score.pillar_id.id),
                ('id', '!=', score.id)
            ])
            if favorites >= 3:
                return {'error': 'You can only choose up to 3 favorite scores per pillar.'}

        score.write({
            'score_name': name,
            'type': type,
            'max_score_percentage': max_score_percentage,
            'min_score_percentage': min_score_percentage,
            'max_score_number': max_score_number,
            'min_score_number': min_score_number,
            'favorite': favorite
        })

        return {'message': 'Score updated successfully'}

    # API to delete a score by its ID 
    @http.route('/api/score/<int:score_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_score(self, score_id):
        score = request.env['bizdom.score'].sudo().browse(score_id)
        if not score.exists():
            return {'error': 'Score not found'}

        score.unlink()
        return {'message': 'Score deleted successfully'}

# pillar_list = []
# for pillar in pillars:
#     pillar_list.append({
#         'id': pillar.id,
#         'name': pillar.name
#     })
# return pillar_list
