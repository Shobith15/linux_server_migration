Linux Server Migration Dashboard
================================

This bundle follows the dashboard design in Appendix E of the project report,
with the service check made compatible with Ubuntu (service "cron") and
Arch/EndeavourOS (service "cronie").

Folder layout:
  scripts/make_source_baseline.py        run on source server
  baseline/source_baseline.json          generated on source, copied to destination
  backend/app.py                         run on destination server
  backend/templates/index.html           frontend served by Flask
  reports/                               generated report output

IMPORTANT:
- Verify the destination's actual data disk is /dev/sdb, partition /dev/sdb1,
  VG vg_migration, LVs lv_data (12 GB) and lv_backup (5 GB). These values are
  configured in backend/app.py to match the report.
- Create the baseline only after the final source-to-destination rsync is done.
- The dashboard is read-only except /api/report, which writes the report file.
- Flask is started with sudo for this lab and binds only to 127.0.0.1:5000.
  Do not expose this development server to an untrusted network.
