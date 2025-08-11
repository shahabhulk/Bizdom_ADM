# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import datetime ,timedelta
import pytz

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    appoi_name = fields.Char(string="name", required=True)
    email = fields.Char(string="Email", required=True)
    phone = fields.Char(string="Phone", required=True)
    time_slot = fields.Float(string="Time Slot")
    booking_id = fields.Char(string="Booking ID", readonly=True ,copy =False)
    apoi_description = fields.Char(string="Appointment Description")
    partner_id = fields.Many2one('res.partner', 'Name')
    weekday_get = fields.Many2one('appointement.slots', string="weekday")
   
 
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            user_tz = self.env.user.tz or 'UTC'
            local_tz = pytz.timezone(user_tz)
            start_time = fields.Datetime.from_string(vals.get('start'))
            stop_time = fields.Datetime.from_string(vals.get('stop'))
            start_time_local = local_tz.localize(start_time, is_dst=None)
            start_time_utc = start_time_local.astimezone(pytz.utc)
            stop_time_local = local_tz.localize(stop_time, is_dst=None)
            stop_time_utc = stop_time_local.astimezone(pytz.utc)
            appoint_id = self.env['appointement.slots'].sudo().search([('id', '=', vals.get('weekday_get'))], limit=1)
            calendar_event_id = self.env['slots'].sudo().search([('time', '=', vals.get('time_slot')), ('slot_time', '=', appoint_id.id)], limit=1)
            calendar_event_id.sudo().update({'is_slot_available': True})
            vals['start'] = fields.Datetime.to_string(start_time_utc)
            vals['stop'] = fields.Datetime.to_string(stop_time_utc)
            slots = super(CalendarEvent, self).create(vals_list)
        sequence_code = 'calendar.event'
        for ref in slots:
            ref.sudo().update({
                'booking_id': self.env['ir.sequence'].next_by_code(sequence_code),
            })

        return slots


    def unlink(self):
        for apt in self:
            appoint_id = self.env['appointement.slots'].sudo().search([('id','=',apt.weekday_get.id)],limit=1)
            calendar_event_id = self.env['slots'].sudo().search([('time','=',apt.time_slot),('slot_time','=',appoint_id.id)],limit=1)
            calendar_event_id.sudo().update({'is_slot_available': False})
        res = super().unlink()
        return res

  
class Website(models.Model):
    _inherit = 'website'  

    def get_service_type_list(self):            
        service_type = self.env['service.type'].sudo().search([])
        return service_type

    def get_car_brand_list(self):            
        car_brand = self.env['fleet.vehicle'].sudo().search([])
        return car_brand

    def get_car_model_list(self):            
        car_model = self.env['fleet.vehicle.model'].sudo().search([])
        return car_model
