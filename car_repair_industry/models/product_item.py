from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    model_ids = fields.Many2many(
        'ir.model',
        string='Models',
        help="Models associated with this category for filtering."
    )
    department_ids = fields.Many2many(
        'hr.department',
        string="Departments",
        domain="[('model_ids.model', '=', 'product.category')]"
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    item_code = fields.Char(string="Item Code")
    department_id = fields.Many2one(
        'hr.department',
        string="Department",
        domain="[('model_ids.model', '=', 'product.template')]"
    )
    categ_id = fields.Many2one(
        'product.category',
        string="Product Category",
        domain="[('department_ids', 'in', department_id)]",
        default=False
    )

    @api.onchange('department_id')
    def _onchange_department_id(self):
        if self.department_id:
            if self.categ_id and self.categ_id.department_ids and self.department_id not in self.categ_id.department_ids:
                self.categ_id = False
            return {
                'domain': {
                    'categ_id': [('department_ids', 'in', self.department_id.id)]
                }
            }
        else:
            return {
                'domain': {
                    'categ_id': []
                }
            }

    @api.onchange('categ_id')
    def _onchange_categ_id(self):
        if self.categ_id and self.categ_id.department_ids and not self.department_id:
            if len(self.categ_id.department_ids) == 1:
                self.department_id = self.categ_id.department_ids[0]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'categ_id' in fields_list and not self._context.get('default_categ_id'):
            res['categ_id'] = False
        return res

    # display_name = fields.Char(compute='_compute_display_name', store=True)
    #
    # @api.depends('name')
    # def _compute_display_name(self):
    #     for product in self:
    #         # Always assign actual product name
    #         product.display_name = product.name or '/'
    #
    # def name_get(self):
    #     result = []
    #     show_item_code = self.env.context.get('show_item_code', False)
    #     for product in self:
    #         if show_item_code:
    #             name = product.item_code or '/'
    #         else:
    #             name = product.name or '/'
    #         result.append((product.id, name))
    #     print(result)
    #     return result
    #
    # @api.model
    # def name_search(self, name, args=None, operator='ilike', limit=100):
    #     args = args or []
    #     domain = args + ['|', '|',
    #                      ('item_code', operator, name),
    #                      ('default_code', operator, name),
    #                      ('name', operator, name)]
    #     return self.search(domain, limit=limit).name_get()


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Inherit and store item_code from product.template
    item_code = fields.Char(
        string="Item Code",
        related='product_tmpl_id.item_code',
        store=True,
        readonly=False
    )
    department_id = fields.Many2one(
        'hr.department',
        string="Department",
        related='product_tmpl_id.department_id',
        store=True,
        readonly=False,
        domain="[('model_ids.model', '=', 'product.template')]"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'categ_id' in fields_list and not self._context.get('default_categ_id'):
            res['categ_id'] = False
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Allow searching by item_code, internal ref, or name"""
        args = args or []
        domain = args + ['|', '|',
                         ('item_code', operator, name),
                         ('default_code', operator, name),
                         ('name', operator, name)]
        records = self.search(domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in records]

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            domain = domain + ['|', '|',
                               ('item_code', operator, name),
                               ('default_code', operator, name),
                               ('name', operator, name)]
        return self._search(domain, limit=limit, order=order)
