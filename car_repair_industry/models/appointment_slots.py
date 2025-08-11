# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class AppointmentSlots(models.Model):
    _name = 'appointement.slots'
    _description = 'Appointement Slots'

    name = fields.Char(string="Day's",compute="_update_day_of_week")
    time = fields.One2many('slots', 'slot_time', string="time")
    appointment_date = fields.Date(string="Slot Date",required=True)

    _sql_constraints = [
        ('unique_appointment_date', 'unique (appointment_date)', 'Please Add Unique Appointement Slots Date.')
    ]

    @api.depends('appointment_date')
    def _update_day_of_week(self):
        for record in self:
            if record.appointment_date:
                day_of_week = record.appointment_date.weekday()
                day_name = {
                    0: 'Monday',
                    1: 'Tuesday',
                    2: 'Wednesday',
                    3: 'Thursday',
                    4: 'Friday',
                    5: 'Saturday',
                    6: 'Sunday',
                }.get(day_of_week, 'Unknown')
                record.name = day_name
            else:
                record.name = False

        return True



class Slots(models.Model):
    _name = 'slots'
    _description = 'Slots'

    slot_time = fields.Many2one('appointement.slots', string='Slot Time')
    time = fields.Float(string="Time", min="")
    is_slot_available = fields.Boolean(string="slot availability")

    def _valid_field_parameter(self, field, name):
        return name == 'min' or super()._valid_field_parameter(field, name)

    @api.constrains('time')
    def _check_values(self):
        for slot in self:
            new_time = slot.time
            if slot.time <= 0.00 or slot.time > 24.00:
                raise ValidationError("Please enter Valid Time")
            existing_slots = self.search([('id', '!=', slot.id), ('slot_time', '=', slot.slot_time.id), ('time', '=', new_time)])
            if existing_slots:
                raise ValidationError("Please enter a unique Time")
