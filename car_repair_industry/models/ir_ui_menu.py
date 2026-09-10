# -*- coding: utf-8 -*-
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _get_car_repair_restricted_menu_ids(self):
        """ Return set of menu IDs that should be hidden for the current user based on department/role. """
        to_hide_ids = set()
        user = self.env.user

        is_manager = (
            user.has_group('car_repair_industry.group_fleet_repair_directeur_commercial') or
            user.has_group('car_repair_industry.group_fleet_repair_service_manager')
        )
        is_head_tech = user.has_group('car_repair_industry.group_fleet_repair_head_technician')

        bodyshop_menu = self.env.ref('car_repair_industry.menu_fleet_repair_bodyshop', raise_if_not_found=False)
        workshop_menu = self.env.ref('car_repair_industry.menu_fleet_repair_workshop', raise_if_not_found=False)
        dashboard_menu = self.env.ref('car_repair_industry.car_repair_dashboard_menu', raise_if_not_found=False)
        car_repair_menu = self.env.ref('car_repair_industry.menu_sub_car_repair', raise_if_not_found=False)

        # 1. Managers must NOT see Bodyshop or Workshop menus
        if is_manager:
            if bodyshop_menu:
                to_hide_ids.add(bodyshop_menu.id)
            if workshop_menu:
                to_hide_ids.add(workshop_menu.id)

        # 2. Head Technicians (who are not managers)
        if is_head_tech and not is_manager:
            # Hide Dashboard and generic Car Repair menus
            if dashboard_menu:
                to_hide_ids.add(dashboard_menu.id)
            if car_repair_menu:
                to_hide_ids.add(car_repair_menu.id)

            # Determine department
            dep_name = ''
            employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if employee and employee.department_id and employee.department_id.name:
                dep_name = employee.department_id.name.lower()
            else:
                dep = self.env['hr.department'].sudo().search([
                    '|', ('name', 'ilike', user.name),
                    ('name', 'ilike', user.login or '')
                ], limit=1)
                if dep and dep.name:
                    dep_name = dep.name.lower()

            if 'bodyshop' in dep_name:
                # In Bodyshop: hide Workshop
                if workshop_menu:
                    to_hide_ids.add(workshop_menu.id)
            elif 'workshop' in dep_name:
                # In Workshop: hide Bodyshop
                if bodyshop_menu:
                    to_hide_ids.add(bodyshop_menu.id)
            else:
                # Neither: hide both
                if bodyshop_menu:
                    to_hide_ids.add(bodyshop_menu.id)
                if workshop_menu:
                    to_hide_ids.add(workshop_menu.id)

        # 3. Non-head technicians and non-managers
        if not is_head_tech and not is_manager:
            if bodyshop_menu:
                to_hide_ids.add(bodyshop_menu.id)
            if workshop_menu:
                to_hide_ids.add(workshop_menu.id)
            if dashboard_menu:
                to_hide_ids.add(dashboard_menu.id)

        return to_hide_ids

    def _load_menus_blacklist(self):
        blacklist = super()._load_menus_blacklist()
        restricted_ids = self._get_car_repair_restricted_menu_ids()
        if restricted_ids:
            return list(set(blacklist) | restricted_ids)
        return blacklist

    @api.returns('self')
    def _filter_visible_menus(self):
        visible = super()._filter_visible_menus()
        restricted_ids = self._get_car_repair_restricted_menu_ids()
        if restricted_ids:
            return visible.filtered(lambda m: m.id not in restricted_ids)
        return visible
