# Sample data (synthetic)

**Everything in this folder is synthetic.** The companies (Northwind Dental, Fabrikam Legal,
Contoso Logistics, Tailspin Clinic, Adatum Accounting) are well-known fictional names, and
every host, error and number was written by hand to exercise the rules engine. Nothing here
comes from a real client environment.

| File | Format | Shows |
| --- | --- | --- |
| `veeam_jobs.csv` | Veeam-style job CSV, multiple nights | VSS/SQL writer streak, repository full, CBT reset, RPC timeout, access denied, ransomware extension on a "successful" job |
| `cove_devices.csv` | Cove-style device CSV | timeouts with RPO breach, offline laptop, over quota, locked files, a stale "Completed" device |
| `datto_agents.json` | Datto BCDR-style agent JSON | screenshot verification failure, ransom-note indicator, expired licence |
| `m365_generic.json` | RecoveryPilot generic JSON | expired Microsoft 365 token, healthy OneDrive job |
| `config.example.yaml` | Settings | per-client RPO and tier, LLM options |

The sample timestamps are around 20 October 2026, so run with `--as-of 2026-10-20T08:00:00Z`
to get the results shown in the main README.
