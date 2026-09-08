from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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
    alloted_fru = fields.Integer(string="Alloted FRU")

    @api.constrains('type', 'alloted_fru')
    def _check_alloted_fru(self):
        for record in self:
            if record.type == 'service' and record.alloted_fru <= 0:
                raise ValidationError(_("Alloted FRU is mandatory for service products and must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('item_code') and isinstance(vals['item_code'], str):
                vals['item_code'] = vals['item_code'].strip()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('item_code') and isinstance(vals['item_code'], str):
            vals['item_code'] = vals['item_code'].strip()
        return super().write(vals)

    @api.constrains('item_code')
    def _check_unique_item_code(self):
        codes = [rec.item_code.strip() for rec in self if rec.item_code and rec.item_code.strip()]
        lower_codes = [c.lower() for c in codes]
        if len(lower_codes) != len(set(lower_codes)):
            raise ValidationError(_("Duplicate Item Codes found within the submitted records."))

        for record in self:
            if not record.item_code or not record.item_code.strip():
                continue
            code = record.item_code.strip()
            escaped_code = code.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')

            duplicate = self.search([
                ('id', '!=', record.id),
                ('item_code', '=ilike', escaped_code),
            ], limit=1)
            if duplicate:
                dup_type = "Service" if duplicate.type == 'service' else "Part"
                raise ValidationError(
                    _("The Item Code '%(code)s' is already in use by %(type)s product '%(name)s'. "
                      "Item code must be unique across all products (both parts and services).",
                      code=code,
                      type=dup_type,
                      name=duplicate.display_name or duplicate.name)
                )

            archived_duplicate = self.with_context(active_test=False).search([
                ('id', '!=', record.id),
                ('active', '=', False),
                ('item_code', '=ilike', escaped_code),
            ], limit=1)
            if archived_duplicate:
                dup_type = "Service" if archived_duplicate.type == 'service' else "Part"
                raise ValidationError(
                    _("The Item Code '%(code)s' is already assigned to an archived %(type)s product '%(name)s'. "
                      "Please unarchive that product or use a different Item Code.",
                      code=code,
                      type=dup_type,
                      name=archived_duplicate.display_name or archived_duplicate.name)
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
    alloted_fru = fields.Integer(
        string="Alloted FRU",
        related='product_tmpl_id.alloted_fru',
        store=True,
        readonly=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('item_code') and isinstance(vals['item_code'], str):
                vals['item_code'] = vals['item_code'].strip()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('item_code') and isinstance(vals['item_code'], str):
            vals['item_code'] = vals['item_code'].strip()
        return super().write(vals)

    @api.constrains('item_code')
    def _check_unique_item_code(self):
        for record in self:
            if record.product_tmpl_id:
                record.product_tmpl_id._check_unique_item_code()

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
