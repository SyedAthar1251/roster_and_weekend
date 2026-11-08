from hrms.hr.doctype.shift_schedule_assignment.shift_schedule_assignment import (
    ShiftScheduleAssignment as HRMSShiftScheduleAssignment,
)


class CustomShiftScheduleAssignment(HRMSShiftScheduleAssignment):
    def create_individual_assignment(self, shift_type, start_date, end_date):
        from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import create_shift_assignment

        create_shift_assignment(
            self.employee,
            self.company,
            shift_type,
            start_date,
            end_date,
            self.shift_status,
            self.shift_location,
            self.name,
            self.custom_weekend_policy,
        )
        self.db_set("create_shifts_after", end_date, update_modified=False)
