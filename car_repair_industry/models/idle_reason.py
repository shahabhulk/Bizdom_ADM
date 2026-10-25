# -*- coding: utf-8 -*-
from odoo import models, fields


class EmployeeIdleReason(models.Model):
    _name = 'employee.idle.reason'
    _description = 'Employee Idle Reason'
    _order = 'sequence, id'

    name = fields.Char(string='Reason', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)


class JobCardIdleReason(models.Model):
    _name = 'job.card.idle.reason'
    _description = 'Job Card Idle Reason'
    _order = 'sequence, id'

    name = fields.Char(string='Reason', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)


class ServiceIdleReason(models.Model):
    _name = 'service.idle.reason'
    _description = 'Service Idle Reason'
    _order = 'sequence, id'

    name = fields.Char(string='Reason', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
