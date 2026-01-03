# -*- coding: utf-8 -*-

from datetime import date
import calendar


class Q3Helpers:
    """Helper utilities for Q3 endpoint - Employee-level score calculations"""
    
    @staticmethod
    def compute_employee_scores(category_lvl2_records, start_date, end_date, score_record, user, dept_id, filter_type=None):
        """
        Compute scores for all employees/sources in a date range from category_lvl2 records
        
        Args:
            category_lvl2_records: Recordset of bizdom.category_lvl2 records
            start_date: Start date
            end_date: End date
            score_record: bizdom.score record
            user: res.users record
            dept_id: Department ID (for filtering)
            filter_type: Filter type for min/max calculation
        
        Returns:
            List of employee/source data dictionaries
        """
        emp_grouped = []
        
        # Determine what we're grouping by based on score type
        if score_record.score_name in ["Leads"]:
            # For Leads, group by source (utm.source)
            selection_type = 'utm.source'
            selection_field = 'source_id'
            name_field = 'source_name'
            id_field = 'source_id'
        else:
            # For Labour, TAT, Conversion, etc., group by employee
            selection_type = 'hr.employee'
            selection_field = 'employee_id'
            name_field = 'employee_name'
            id_field = 'employee_id'
        
        # Filter category_lvl2 records by department/medium
        filtered_records = category_lvl2_records.filtered(
            lambda r: r.category_lvl2_selection and 
                      r.category_lvl2_selection._name == selection_type
        )
        
        # For Labour/TAT: filter by department_id
        # For Leads/Conversion: filter by medium_id
        if score_record.score_name in ["Leads", "Conversion"]:
            filtered_records = filtered_records.filtered(lambda r: r.medium_id and r.medium_id.id == dept_id)
        else:
            filtered_records = filtered_records.filtered(lambda r: r.department_id and r.department_id.id == dept_id)
        
        # Group by unique employee/source
        seen_ids = set()
        for cat_lvl2_rec in filtered_records:
            if not cat_lvl2_rec.category_lvl2_selection:
                continue
            
            selection_obj = cat_lvl2_rec.category_lvl2_selection
            if selection_obj.id in seen_ids:
                continue
            
            seen_ids.add(selection_obj.id)
            
            # Get a fresh record to avoid singleton issues
            cat_rec_id = int(cat_lvl2_rec.id)
            single_rec = category_lvl2_records.env['bizdom.category_lvl2'].sudo().browse(cat_rec_id)
            
            if len(single_rec) != 1:
                continue
            
            # Compute score with context
            cat_rec_with_context = single_rec.with_context(
                force_date_start=start_date,
                force_date_end=end_date,
                company_id=user.company_id.id if hasattr(user, 'company_id') else None
            )
            cat_rec_with_context._compute_context_score_category_lvl2()
            values = cat_rec_with_context.mapped('context_score_category_lvl2')
            emp_actual_value = values[0] if values else 0.0
            
            # Round if numeric
            if isinstance(emp_actual_value, (int, float)):
                emp_actual_value = round(emp_actual_value, 2)
            
            # Get name
            if selection_type == 'hr.employee':
                emp_name = selection_obj.name if hasattr(selection_obj, 'name') else "N/A"
            else:  # utm.source
                emp_name = selection_obj.name if hasattr(selection_obj, 'name') else "N/A"
            
            emp_data = {
                id_field: selection_obj.id,
                name_field: emp_name,
                'actual_value': emp_actual_value
            }
            
            # Special handling for Leads - add quality_lead_value and lead_value
            if score_record.score_name == "Leads":
                # Calculate quality leads (stage_id.sequence = 1) and total leads (stage_id.sequence in [0, 1])
                lead_model = category_lvl2_records.env['crm.lead'].sudo()
                source = selection_obj if selection_type == 'utm.source' else None
                
                if source:
                    all_leads = lead_model.search_count([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', 'in', [0, 1]),
                        ('medium_id', '=', dept_id),
                        ('source_id', '=', source.id),
                        ('company_id', '=', user.company_id.id if hasattr(user, 'company_id') else None)
                    ])
                    quality_leads = lead_model.search_count([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', '=', 1),
                        ('medium_id', '=', dept_id),
                        ('source_id', '=', source.id),
                        ('company_id', '=', user.company_id.id if hasattr(user, 'company_id') else None)
                    ])
                    emp_data['lead_value'] = all_leads
                    emp_data['quality_lead_value'] = quality_leads
                    emp_data['actual_value'] = all_leads  # For Leads, actual_value is total leads
            
            # Special handling for Conversion - add quality_lead_value and converted_value
            elif score_record.score_name == "Conversion":
                # Calculate quality leads (stage_id.sequence in [1, 2]) and converted (stage_id.sequence = 2)
                lead_model = category_lvl2_records.env['crm.lead'].sudo()
                employee = selection_obj if selection_type == 'hr.employee' else None
                
                if employee and employee.user_id:
                    all_leads = lead_model.search_count([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', 'in', [1, 2]),
                        ('medium_id', '=', dept_id),
                        ('user_id', '=', employee.user_id.id),
                        ('company_id', '=', user.company_id.id if hasattr(user, 'company_id') else None)
                    ])
                    converted_leads = lead_model.search_count([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', '=', 2),
                        ('medium_id', '=', dept_id),
                        ('user_id', '=', employee.user_id.id),
                        ('company_id', '=', user.company_id.id if hasattr(user, 'company_id') else None)
                    ])
                    emp_data['quality_lead_value'] = all_leads
                    emp_data['converted_value'] = converted_leads
                    emp_data['actual_value'] = converted_leads  # For Conversion, actual_value is converted leads
                    # Rename fields for Conversion response
                    emp_data['saleperson_id'] = emp_data.pop('employee_id')
                    emp_data['saleperson_name'] = emp_data.pop('employee_name')
            
            # Add min/max for Labour scores with WTD/MTD/YTD
            if score_record.score_name == "Labour" and filter_type in ["WTD", "MTD", "YTD"]:
                # For employee-level, we might need to calculate min/max differently
                # For now, leave empty as the original code didn't have employee-level min/max
                emp_data['min_value'] = ''
                emp_data['max_value'] = ''
            else:
                emp_data['min_value'] = ''
                emp_data['max_value'] = ''
            
            emp_grouped.append(emp_data)
        
        return emp_grouped



