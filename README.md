# Roster And Weekend

Standalone Frappe app extracted from CentralHrms. Needs **Frappe v15 + HRMS** on the site.

## What is inside

| Area | Contents |
|---|---|
| DocTypes | Roster Plan, Roster Plan Employee, Roster Pattern, Roster Pattern Day, Roster Entry, Roster Open Shift, Roster Swap Request, Roster Site Rule, Roster Settings, Weekend Policy (+ Day / Rotation / History), Week Off Swap |
| Desk pages / report / workspace | Roster Hub, Roster Report, Roster vs Actual, "Roster And Weekend" workspace |
| Roster board | Vue app (`roster/`, built into `roster_and_weekend/public/roster`), served at `/roster` |
| Weekend resolver | `roster_and_weekend.roster_and_weekend.weekend_policy` (`is_weekend`, `get_weekend_dates`, `resolve_weekend_policy`, `get_employee_weekend_policy`) |
| Overrides | Shift Type (roster + weekend aware auto attendance), Shift Assignment (default shift), Shift Schedule Assignment |
| Runtime patches | HRMS `get_number_of_leave_days`, Shift Assignment Tool, `hrms.api.roster` (all made Weekend Policy aware) |
| Scheduler | `alerts.run` every 5 min, `notify_weekend_bridge_cases` Sunday 18:00 |
| Roles / custom fields | Roster Manager, Roster Employee; custom fields on Shift Assignment, Shift Type, Shift Schedule Assignment (created on install and on every migrate) |

## Not included (stays in CentralHrms)

Leave Application weekend-bridge / sandwich logic, payroll and salary-slip weekend handling, holiday auto-creation,
Overtime Request / Over Time Slab doctypes, Employee `custom_allowed_shift_locations`, attendance logic / AMS sync.
Roster overtime generation (`overtime.generate`) needs the Overtime Request doctype and says so if it is missing.
Everything else works without CentralHrms.

## Install (local bench)

```bash
cd ~/frappe-bench
# put the folder in apps/ (or: bench get-app /path/to/roster_and_weekend)
bench pip install -e apps/roster_and_weekend      # or: ./env/bin/pip install -e apps/roster_and_weekend
bench --site yoursite.local install-app roster_and_weekend
bench --site yoursite.local migrate
bench build --app roster_and_weekend
bench restart
```

## Use a site WITHOUT the CentralHrms roster module

This app has the same DocType names, module name ("Roster And Weekend"), custom fields and overrides as the
roster/weekend part of CentralHrms. Do **not** install both on one site until the roster/weekend code has been
removed from CentralHrms. Test on a fresh site, or one running a CentralHrms version without this module.

## Tests

Pure unit tests (no site needed):
```bash
python -m unittest roster_and_weekend.roster_and_weekend.tests.test_cycle
python -m unittest roster_and_weekend.roster_and_weekend.tests.test_weekend_resolver
python -m unittest roster_and_weekend.roster_and_weekend.tests.test_shift_type_checks
python -m unittest roster_and_weekend.roster_and_weekend.tests.test_attendance_diagnosis
```
Integration tests need a site with 3 active employees, a Shift Type and a Shift Location:
```bash
bench --site yoursite.local run-tests --app roster_and_weekend
```

## Rebuilding the roster board

```bash
cd apps/roster_and_weekend/roster
yarn install   # or npm install
yarn build     # writes ../roster_and_weekend/public/roster and ../roster_and_weekend/www/roster.html
```

## Known issues carried over from CentralHrms (not introduced by the extraction)

`roster_and_weekend/doctype/week_off_swap/test_week_off_swap.py` and
`roster_and_weekend/doctype/weekend_policy/test_weekend_policy.py` patch helpers
(`_get_shift_type_for_employee_on_date`, `_get_approved_weekend_swap`) that the current `weekend_policy.py` no longer has,
so those two test files fail under `bench run-tests` until they are rewritten against the current resolver.
`before_request` redirect `/hr/roster` -> `/roster` is copied as-is from CentralHrms; the board is always reachable directly at `/roster`.
