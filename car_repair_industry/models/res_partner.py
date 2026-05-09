# -*- coding: utf-8 -*-

from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def get_existing_client_contacts(self, typed_name):
        """Return existing partners with same name and their contact data."""
        name = (typed_name or "").strip()
        if not name:
            return []

        partners = self.search([("name", "=ilike", name)], limit=5)

        result = []
        for partner in partners:
            numbers = []
            if partner.phone:
                numbers.append(partner.phone)
            if partner.mobile and partner.mobile not in numbers:
                numbers.append(partner.mobile)

            result.append(
                {
                    "id": partner.id,
                    "name": partner.name,
                    "numbers": numbers,
                    "has_numbers": bool(numbers),
                }
            )
        return result

    @api.model
    def get_conflicts_by_contact_number(self, client_name, numbers, exclude_partner_id=False):
        """Return partners with same phone/mobile but a different customer name."""
        normalized_numbers = [num.strip() for num in (numbers or []) if num and num.strip()]
        if not normalized_numbers:
            return []

        domain = [
            "|",
            ("phone", "in", normalized_numbers),
            ("mobile", "in", normalized_numbers),
        ]
        if exclude_partner_id:
            domain.append(("id", "!=", exclude_partner_id))

        current_name = (client_name or "").strip().lower()
        partners = self.search(domain, limit=5)

        conflicts = []
        for partner in partners:
            partner_name = (partner.name or "").strip().lower()
            if current_name and partner_name == current_name:
                continue

            matched_numbers = []
            if partner.phone and partner.phone in normalized_numbers:
                matched_numbers.append(partner.phone)
            if partner.mobile and partner.mobile in normalized_numbers and partner.mobile not in matched_numbers:
                matched_numbers.append(partner.mobile)

            conflicts.append(
                {
                    "id": partner.id,
                    "name": partner.name,
                    "numbers": matched_numbers or [partner.mobile or partner.phone or ""],
                }
            )
        return conflicts
