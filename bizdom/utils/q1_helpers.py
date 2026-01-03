# -*- coding: utf-8 -*-

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import calendar


class Q1Helpers:
    """Helper utilities for Q1 endpoint - Date range calculations"""
    
    @staticmethod
    def get_date_ranges(filter_type, start_date_str=None, end_date_str=None):
        """
        Get date ranges for Q1 overview based on filter type
        
        Args:
            filter_type: 'Custom', 'WTD', 'MTD', 'YTD', or None (defaults to MTD)
            start_date_str: Start date string in 'DD-MM-YYYY' format (for Custom)
            end_date_str: End date string in 'DD-MM-YYYY' format (for Custom)
        
        Returns:
            List of tuples: [(start_date, end_date, period_label), ...]
        
        Raises:
            ValueError: If dates are invalid or start_date > end_date
        """
        today = date.today()
        
        if filter_type == "Custom" and start_date_str and end_date_str:
            return Q1Helpers._get_custom_ranges(start_date_str, end_date_str)
        elif filter_type == "WTD":
            return Q1Helpers._get_week_ranges(today)
        elif filter_type == "MTD" or not filter_type:
            return Q1Helpers._get_month_ranges(today)
        elif filter_type == "YTD":
            return Q1Helpers._get_year_ranges(today)
        else:
            # Default to MTD
            return Q1Helpers._get_month_ranges(today)
    
    @staticmethod
    def _get_custom_ranges(start_date_str, end_date_str):
        """Handle Custom date range filter"""
        from datetime import datetime
        
        start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
        end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
        
        if start_date > end_date:
            raise ValueError("Start date should be less than end date")
        
        delta = relativedelta(end_date, start_date)
        total_months = delta.years * 12 + delta.months
        
        ranges = []
        
        if total_months > 3:
            # For date ranges > 3 months, show yearly segments (last 3 years)
            current_year = start_date.year
            end_year = end_date.year
            
            for year in range(3):
                year_start = date(current_year - year, start_date.month, start_date.day)
                year_end = date(end_year - year, end_date.month, end_date.day)
                
                ranges.append((
                    year_start,
                    year_end,
                    f"{year_start.strftime('%d-%m-%Y')} to {year_end.strftime('%d-%m-%Y')}"
                ))
        else:
            # For date ranges ≤ 3 months, show 3 periods going backwards
            duration = end_date - start_date
            
            for i in range(3):
                period_end = end_date - (duration * i)
                period_start = period_end - duration
                # Don't go before an arbitrary early date
                period_start = max(period_start, date(2000, 1, 1))
                
                ranges.append((
                    period_start,
                    period_end,
                    f"{period_start.strftime('%d-%m-%Y')} to {period_end.strftime('%d-%m-%Y')}"
                ))
        
        return ranges
    
    @staticmethod
    def _get_week_ranges(today):
        """Handle WTD (Week To Date) filter - returns last 3 weeks"""
        ranges = []
        current_week_start = today - timedelta(days=today.weekday())
        
        for i in range(2, -1, -1):  # 2 weeks ago, 1 week ago, current week
            week_start = current_week_start - timedelta(weeks=i)
            
            if i == 0:
                # Current week: Monday to today
                week_end = today
            else:
                # Previous weeks: Monday to Saturday (full week)
                week_end = week_start + timedelta(days=5)
            
            ranges.append((
                week_start,
                week_end,
                f"Week {3 - i}"
            ))
        
        return ranges
    
    @staticmethod
    def _get_month_ranges(today):
        """Handle MTD (Month To Date) filter - returns last 3 months"""
        ranges = []
        current_month_start = today.replace(day=1)
        
        for i in range(2, -1, -1):  # 2 months ago, 1 month ago, current month
            month_start = (current_month_start - relativedelta(months=i))
            
            if i == 0:
                # Current month: 1st to today
                month_end = today
            else:
                # Previous months: full month
                month_end = month_start + relativedelta(months=1) - timedelta(days=1)
            
            ranges.append((
                month_start,
                month_end,
                month_start.strftime("%B %Y")
            ))
        
        return ranges
    
    @staticmethod
    def _get_year_ranges(today):
        """Handle YTD (Year To Date) filter - returns last 3 years"""
        ranges = []
        current_year = today.year
        
        for i in range(2, -1, -1):  # 2 years ago, 1 year ago, current year
            year = current_year - i
            year_start = date(year, 1, 1)
            
            if i == 0:
                # Current year: Jan 1 to today
                year_end = today
            else:
                # Previous years: full year
                year_end = date(year, 12, 31)
            
            ranges.append((
                year_start,
                year_end,
                str(year)
            ))
        
        return ranges
    
    @staticmethod
    def calculate_min_max(score_record, filter_type, start_date, end_date):
        """
        Calculate min/max values for a period based on filter type and score type
        
        Args:
            score_record: bizdom.score record
            filter_type: 'WTD', 'MTD', 'YTD', or 'Custom'
            start_date: Start date of the period
            end_date: End date of the period
        
        Returns:
            Tuple: (min_value, max_value) or (None, None) if not applicable
        """
        today = date.today()
        
        if filter_type == "WTD":
            # Calculate days in current week excluding Sundays
            days_in_current_week = sum(
                1 for d in range((end_date - start_date).days + 1)
                if (start_date + timedelta(days=d)).weekday() != 6
            )
            
            # Calculate days in current month excluding Sundays (for daily rate)
            current_week_start = today - timedelta(days=today.weekday())
            current_month_start = current_week_start.replace(day=1)
            days_in_month = Q1Helpers._get_days_in_month_excluding_sundays(
                current_month_start.year, current_month_start.month
            )
            
            if score_record.type == "percentage":
                daily_min = score_record.min_score_percentage / days_in_month
                daily_max = score_record.max_score_percentage / days_in_month
            elif score_record.type == "value":
                daily_min = score_record.min_score_number / days_in_month
                daily_max = score_record.max_score_number / days_in_month
            else:
                daily_min = daily_max = 0
            
            return (
                round(daily_min * days_in_current_week, 2),
                round(daily_max * days_in_current_week, 2)
            )
        
        elif filter_type == "MTD" or not filter_type:
            # Calculate days in current month excluding Sundays
            current_month_start = today.replace(day=1)
            days_in_month = Q1Helpers._get_days_in_month_excluding_sundays(
                current_month_start.year, current_month_start.month
            )
            days_up_to_today = Q1Helpers._get_days_up_to_date_excluding_sundays(
                current_month_start.year, current_month_start.month, today.day
            )
            
            if score_record.type == "percentage":
                daily_min = score_record.min_score_percentage / days_in_month
                daily_max = score_record.max_score_percentage / days_in_month
            elif score_record.type == "value":
                daily_min = score_record.min_score_number / days_in_month
                daily_max = score_record.max_score_number / days_in_month
            else:
                daily_min = daily_max = 0
            
            return (
                round(daily_min * days_up_to_today, 2),
                round(daily_max * days_up_to_today, 2)
            )
        
        elif filter_type == "YTD":
            # Calculate total days in current YTD excluding Sundays
            current_ytd_start = date(today.year, 1, 1)
            total_days_in_ytd = Q1Helpers._get_days_in_range_excluding_sundays(
                current_ytd_start, today
            )
            
            # Calculate days in current month excluding Sundays (for daily rate)
            current_month_start = today.replace(day=1)
            days_in_month = Q1Helpers._get_days_in_month_excluding_sundays(
                current_month_start.year, current_month_start.month
            )
            
            if score_record.type == "percentage":
                monthly_min_base = score_record.min_score_percentage or 0
                monthly_max_base = score_record.max_score_percentage or 0
            elif score_record.type == "value":
                monthly_min_base = score_record.min_score_number or 0
                monthly_max_base = score_record.max_score_number or 0
            else:
                monthly_min_base = monthly_max_base = 0
            
            return (
                round((monthly_min_base / days_in_month) * total_days_in_ytd, 2) if days_in_month > 0 else 0,
                round((monthly_max_base / days_in_month) * total_days_in_ytd, 2) if days_in_month > 0 else 0
            )
        
        # Custom or default - no min/max
        return None, None
    
    @staticmethod
    def _get_days_in_month_excluding_sundays(year, month):
        """Calculate the number of days in a month excluding Sundays"""
        total_days = calendar.monthrange(year, month)[1]
        sunday_count = 0
        for day in range(1, total_days + 1):
            if date(year, month, day).weekday() == 6:  # Sunday is 6
                sunday_count += 1
        return total_days - sunday_count
    
    @staticmethod
    def _get_days_up_to_date_excluding_sundays(year, month, end_day):
        """Calculate days from start of month up to end_day, excluding Sundays"""
        days_count = 0
        for day in range(1, end_day + 1):
            if date(year, month, day).weekday() != 6:  # Exclude Sundays
                days_count += 1
        return days_count
    
    @staticmethod
    def _get_days_in_range_excluding_sundays(start_date, end_date):
        """Calculate the number of days in a date range excluding Sundays"""
        days_count = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() != 6:  # Exclude Sundays
                days_count += 1
            current_date += timedelta(days=1)
        return days_count


