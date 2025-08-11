from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    item_code = fields.Char(string="Item Code")

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
        readonly=False  # Optional: make editable if needed
    )

    # Display name field (optional, not used for dropdowns here)
    # display_name = fields.Char(compute='_compute_display_name', store=True)
    #
    # @api.depends('name')
    # def _compute_display_name(self):
    #     for product in self:
    #         # Always assign actual product name
    #         product.display_name = product.name or '/'

    def name_get(self):
        result = []
        for product in self:
            name = product.name or ""
            code = product.item_code or ""
            display_name = f"{code} - {name}" if code else name
            result.append((product.id, display_name))
        return result

    # def name_get(self):
    #     result = []
    #     show_item_code = self.env.context.get('show_item_code', True)
    #
    #     for product in self:
    #         if show_item_code:
    #             name = product.item_code or '/'
    #         else:
    #             name = product.name or '/'
    #         result.append((product.id, name))
    #
    #     return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        """Allow searching by item_code, internal ref, or name"""
        args = args or []
        domain = args + ['|', '|',
                         ('item_code', operator, name),
                         ('default_code', operator, name),
                         ('name', operator, name)]
        return self.search(domain, limit=limit).name_get()
