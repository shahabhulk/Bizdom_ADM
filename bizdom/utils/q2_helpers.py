# -*- coding: utf-8 -*-

from datetime import date
import calendar


class Q2Helpers:
    """Helper utilities for Q2 endpoint - Department-level score calculations"""
    
    @staticmethod
    def get_departments_from_categories(category_records, category_type='hr.department'):
        """
        Extract unique departments/mediums from category records
        If multiple category records point to the same department, use the last one (most recent)
        
        Args:
            category_records: Recordset of bizdom.category_lvl1 records
            category_type: Type of category ('hr.department' or 'utm.medium')
        
        Returns:
            List of tuples: [(category_record, department/medium), ...]
        """
        departments = []
        seen_ids = {}  # Use dict to track the latest category record for each department
        
        for cat_rec in category_records:
            if not cat_rec.category_lvl1_selection:
                continue
                
            if cat_rec.category_lvl1_selection._name != category_type:
                continue
            
            dept = cat_rec.category_lvl1_selection
            # Store the latest category record for each department (in case of duplicates)
            seen_ids[dept.id] = (cat_rec, dept)
        
        # Convert dict values to list
        departments = list(seen_ids.values())
        
        return departments
    
    @staticmethod
    def calculate_department_min_max(category_record, score_record, filter_type, start_date, end_date):
        """
        Calculate min/max values for a department based on filter type using category_lvl1 min/max values
        
        Args:
            category_record: bizdom.category_lvl1 record
            score_record: bizdom.score record
            filter_type: 'WTD', 'MTD', 'YTD', or 'Custom'
            start_date: Start date of the period
            end_date: End date of the period
        
        Returns:
            Tuple: (min_value, max_value)
        """
        if not category_record:
            return 0, 0
        
        # Get min/max from category_lvl1 based on score type
        score_type = score_record.type or 'value'
        if score_type == 'percentage':
            min_base = category_record.min_category_percentage_lvl1 or 0
            max_base = category_record.max_category_percentage_lvl1 or 0
            print(f"Q2 calculate_department_min_max: category_id={category_record.id}, category_name={category_record.name}, score_type={score_type}")
            print(f"  - Raw values: min_category_percentage_lvl1={category_record.min_category_percentage_lvl1}, max_category_percentage_lvl1={category_record.max_category_percentage_lvl1}")
        else:
            min_base = category_record.min_category_value_lvl1 or 0
            max_base = category_record.max_category_value_lvl1 or 0
            print(f"Q2 calculate_department_min_max: category_id={category_record.id}, category_name={category_record.name}, score_type={score_type}")
            print(f"  - Raw values: min_category_value_lvl1={category_record.min_category_value_lvl1}, max_category_value_lvl1={category_record.max_category_value_lvl1}")
        
        print(f"  - After 'or 0' fallback: min_base={min_base}, max_base={max_base}, filter_type={filter_type}")
        
        # Check if values are actually None/False (which would become 0)
        if score_type == 'percentage':
            if not category_record.min_category_percentage_lvl1 and not category_record.max_category_percentage_lvl1:
                print(f"  WARNING: Both min and max are None/False/0 for percentage type!")
        else:
            if not category_record.min_category_value_lvl1 and not category_record.max_category_value_lvl1:
                print(f"  WARNING: Both min and max are None/False/0 for value type!")
        
        if filter_type == "WTD":
            # Calculate days in week (including start and end)
            from datetime import timedelta
            days_count = (end_date - start_date).days + 1
            
            # Get days in month for daily rate
            month_start = start_date.replace(day=1)
            days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
            
            min_per_day = min_base / days_in_month if days_in_month > 0 else 0
            max_per_day = max_base / days_in_month if days_in_month > 0 else 0
            
            return round(min_per_day * days_count, 2), round(max_per_day * days_count, 2)
        
        elif filter_type == "MTD" or not filter_type:
            # Calculate days up to end_date in the month
            month_start = start_date.replace(day=1)
            days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
            days_up_to_end = end_date.day
            
            min_per_day = min_base / days_in_month if days_in_month > 0 else 0
            max_per_day = max_base / days_in_month if days_in_month > 0 else 0
            
            return round(min_per_day * days_up_to_end, 2), round(max_per_day * days_up_to_end, 2)
        
        elif filter_type == "YTD":
            # Calculate total days elapsed in YTD
            year_start = date(end_date.year, 1, 1)
            total_days_elapsed = sum(
                calendar.monthrange(end_date.year, m)[1] for m in range(1, end_date.month)
            ) + end_date.day
            days_multiplier = total_days_elapsed / 30.0
            
            return round(min_base * days_multiplier, 2), round(max_base * days_multiplier, 2)
        
        # Custom or default - use base values divided by 30 (monthly base)
        return round(min_base / 30, 2), round(max_base / 30, 2)
    
    @staticmethod
    def compute_department_scores(category_records, start_date, end_date, score_record, user, filter_type=None):
        """
        Compute scores for all departments in a date range
        
        Args:
            category_records: Recordset of bizdom.category_lvl1 records
            start_date: Start date
            end_date: End date
            score_record: bizdom.score record
            user: res.users record
            filter_type: Filter type for min/max calculation
        
        Returns:
            List of department data dictionaries
        """
        dept_grouped = []
        
        # Determine category type based on score
        if score_record.score_name in ["Leads", "Conversion"]:
            category_type = 'utm.medium'
        else:
            category_type = 'hr.department'
        
        # Get unique departments/mediums
        departments = Q2Helpers.get_departments_from_categories(category_records, category_type)
        
        for cat_rec, dept in departments:
            # Ensure we have a single integer ID
            # cat_rec from loop should be a single record, extract its ID safely
            if hasattr(cat_rec, '_ids'):
                # If it's a recordset, get the first ID
                cat_rec_id = cat_rec._ids[0] if cat_rec._ids else None
            else:
                # It's a single record, get its ID
                cat_rec_id = int(cat_rec.id) if hasattr(cat_rec, 'id') else None
            
            if not cat_rec_id:
                continue
            
            # Browse a completely fresh single record using the env from category_records
            # This ensures we have a clean environment without recordset references
            single_rec = category_records.env['bizdom.category_lvl1'].sudo().browse(cat_rec_id)
            
            # Ensure it's really a single record
            if len(single_rec) != 1:
                continue
                
            cat_rec_with_context = single_rec.with_context(
                force_date_start=start_date,
                force_date_end=end_date,
                company_id=user.company_id.id if hasattr(user, 'company_id') else None
            )
            # Call compute method on the single-record recordset
            cat_rec_with_context._compute_context_score_category_lvl1()
            # Access the computed field using .mapped() which safely handles recordsets
            # This avoids the singleton check issue
            values = cat_rec_with_context.mapped('context_score_category_lvl1')
            dept_actual_value = values[0] if values else 0.0
            
            # Round if numeric
            if isinstance(dept_actual_value, (int, float)):
                dept_actual_value = round(dept_actual_value, 2)
            
            dept_data = {
                'department_id': dept.id,
                'department_name': dept.name,
                'actual_value': dept_actual_value
            }
            
            # Add min/max for Labour scores with WTD/MTD/YTD using category_lvl1 values
            if score_record.score_name == "Labour" and filter_type in ["WTD", "MTD", "YTD", "CUSTOM"]:
                print(f"Q2 Processing Labour department: {dept.name}, category_lvl1: {single_rec.name} (ID: {single_rec.id})")
                print(f"Q2 Category record fields - min_category_value_lvl1: {single_rec.min_category_value_lvl1}, max_category_value_lvl1: {single_rec.max_category_value_lvl1}")
                print(f"Q2 Category record fields - min_category_percentage_lvl1: {single_rec.min_category_percentage_lvl1}, max_category_percentage_lvl1: {single_rec.max_category_percentage_lvl1}")
                print(f"Q2 Score type: {score_record.type}")
                min_value, max_value = Q2Helpers.calculate_department_min_max(
                    single_rec, score_record, filter_type, start_date, end_date
                )
                dept_data['min_value'] = min_value
                dept_data['max_value'] = max_value
                dept_data['category_name'] = single_rec.name  # Include category name for debugging
                print(f"Q2 dept_data for {dept.name} (category: {single_rec.name}): actual_value={dept_actual_value}, min_value={min_value}, max_value={max_value}")
                
                # If min/max are 0, warn that they might not be set in category_lvl1
                if min_value == 0 and max_value == 0:
                    print(f"WARNING: Q2 min/max are both 0 for {dept.name} (category: {single_rec.name}). Check if min/max values are set in category_lvl1 record!")
            else:
                dept_data['min_value'] = ''
                dept_data['max_value'] = ''
            
            # Special handling for Leads/Conversion - add quality_lead
            if score_record.score_name in ["Leads", "Conversion"]:
                lead_model = cat_rec.env['crm.lead'].sudo()
                # Leads: stage_id.sequence = 1, Conversion: stage_id.sequence = [1, 2]
                if score_record.score_name == "Leads":
                    stage_domain = [('stage_id.sequence', '=', 1)]
                else:  # Conversion
                    stage_domain = [('stage_id.sequence', 'in', [1, 2])]
                
                quality_lead_count = lead_model.search_count([
                    ('lead_date', '>=', start_date),
                    ('lead_date', '<=', end_date),
                ] + stage_domain + [
                    ('medium_id', '=', dept.id),
                    ('company_id', '=', user.company_id.id)
                ])
                
                dept_data['quality_lead'] = quality_lead_count if quality_lead_count else 0
            
            dept_grouped.append(dept_data)
        
        return dept_grouped

