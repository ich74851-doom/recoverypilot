<!-- Generated from the SYNTHETIC sample data in examples/ with:
     recoverypilot triage examples/*.csv examples/*.json -c examples/config.example.yaml --as-of 2026-10-20T08:00:00Z --llm -o markdown -->

# Backup incident triage report

- **Generated:** 2026-10-25 23:10 UTC by RecoveryPilot 0.1.0
- **Evaluated as of:** 2026-10-20 08:00 UTC
- **Sources:** cove_devices.csv, veeam_jobs.csv, datto_agents.json, m365_generic.json
- **Jobs evaluated:** 20 (healthy: 5)
- **Findings:** 15 | **RPO breaches:** 9

| Priority | Count |
| --- | --- |
| P1 | 5 |
| P2 | 5 |
| P3 | 2 |
| P4 | 3 |

## AI summary (mock)

[mock provider] 15 backup incident(s) across 5 client(s). 5 P1 incident(s) need action first. Highest: RANSOM-001 on FAB-FS01 (ransomware, score 90). Categories: agent, application, cbt, credentials, file-access, licensing, network, ransomware, rpo, storage, verification.

## Findings

| Priority | Score | Rule | Client | Host | Vendor | Since last success | RPO |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 90 | RANSOM-001 | Fabrikam Legal | FAB-FS01 | veeam | 2.3h | ok (12h) |
| P1 | 90 | RANSOM-002 | Tailspin Clinic | TSC-FS02 | datto | 1h | ok (24h) |
| P1 | 90 | STOR-001 | Fabrikam Legal | FAB-APP01 | veeam | 55h | breached (12h) |
| P1 | 86 | APP-001 | Northwind Dental | NWD-SQL01 | veeam | 54.3h | breached (24h) |
| P1 | 85 | RPO-001 | Fabrikam Legal | FAB-LT02 | cove | 86.7h | breached (12h) |
| P2 | 76 | AUTH-001 | Contoso Logistics | contoso-logistics.example | m365-backup | 53.5h | breached (24h) |
| P2 | 75 | AUTH-001 | Adatum Accounting | ADA-APP02 | veeam | 178.4h | breached (48h) |
| P2 | 65 | STOR-001 | Adatum Accounting | ADA-FS01 | cove | 54.8h | breached (48h) |
| P2 | 65 | NET-001 | Tailspin Clinic | TSC-PM01 | cove | 75h | breached (24h) |
| P2 | 60 | VERIFY-001 | Contoso Logistics | CTL-SQL02 | datto | 2h | ok (24h) |
| P3 | 53 | AGENT-001 | Adatum Accounting | ADA-LT07 | cove | 134h | breached (48h) |
| P3 | 51 | NET-001 | Contoso Logistics | CTL-WEB01 | veeam | 29.3h | breached (24h) |
| P4 | 35 | LICENSE-001 | Adatum Accounting | ADA-SQL01 | datto | 27h | ok (48h) |
| P4 | 25 | LOCK-001 | Northwind Dental | NWD-WS03 | cove | 4h | ok (24h) |
| P4 | 20 | CBT-001 | Contoso Logistics | CTL-HV01 | veeam | 3.8h | ok (24h) |

### [P1] Known ransomware / encryption extensions in protected data: Fabrikam Legal / FAB-FS01

- **Rule:** `RANSOM-001` (ransomware, base severity critical)
- **Job:** veeam / File Server Daily / status `success`
- **Message:** Processing finished. Data change rate significantly above average.
- **Evidence:** suspicious extensions observed: .akira; change rate 63% >= 40%
- **Score:** severity 80 + client_tier 10 = **90**
- **Also matched:** RANSOM-003
- **AI note:** Start with the RANSOM-001 remediation steps for FAB-FS01.

**Remediation**

1. Do NOT delete or prune any restore points; pause retention/cleanup jobs for this client.
2. Escalate to the security/SOC on-call and follow the ransomware recovery runbook.
3. Isolate the affected host from the network (EDR isolation or switch port), do not power it off.
4. Identify the last clean restore point by browsing file versions before the first suspicious change.
5. Verify immutable / offsite copies are intact before any restore activity.
6. Compare against the job's normal change rate and any scheduled maintenance or migrations.
7. Spot-check recently modified files on the host for unreadable content or new extensions.
8. Check EDR/AV consoles for alerts on the host in the same time window.
9. If unexplained, protect the previous restore point (lock/immutable copy) before the next run.

References: https://github.com/ich74851-doom/dr-runbooks

### [P1] Ransom note indicators in job log: Tailspin Clinic / TSC-FS02

- **Rule:** `RANSOM-002` (ransomware, base severity critical)
- **Job:** datto / TSC-SIRIS01 agent backup / status `warning`
- **Message:** Backup completed with 1204 files skipped. New file HOW_TO_DECRYPT.txt detected in 37 folders.
- **Evidence:** message matches /HOW[_-]?TO[_-]?(RECOVER|DECRYPT|RESTORE)/; change rate 71.4% >= 40%; status=warning; message matches /files? (were )?skipped/
- **Score:** severity 80 + client_tier 10 = **90**
- **Also matched:** RANSOM-003, LOCK-001
- **AI note:** Start with the RANSOM-002 remediation steps for TSC-FS02.

**Remediation**

1. Treat as an active security incident; escalate to the security/SOC on-call immediately.
2. Preserve restore points and logs; suspend retention and any automated cleanup.
3. Isolate the host and check for lateral movement before restoring anything.
4. Compare against the job's normal change rate and any scheduled maintenance or migrations.
5. Spot-check recently modified files on the host for unreadable content or new extensions.
6. Check EDR/AV consoles for alerts on the host in the same time window.
7. If unexplained, protect the previous restore point (lock/immutable copy) before the next run.
8. Identify the skipped files; if they matter (PSTs, databases) protect them with VSS or app-aware backup.
9. Exclude transient / temp paths that do not need protecting.

References: https://github.com/ich74851-doom/dr-runbooks

### [P1] Backup target / repository out of space or over quota: Fabrikam Legal / FAB-APP01

- **Rule:** `STOR-001` (storage, base severity high)
- **Job:** veeam / Application Servers / status `failed`
- **Message:** Error: Not enough free space on backup repository FAB-REPO01 (free 11.9 GB, required 85.3 GB)
- **Evidence:** status=failed; message matches /not enough (free )?(disk )?space/; RPO 12h breached (55.0h since last success)
- **Score:** severity 55 + rpo_breach 20 + failure_streak 5 + client_tier 10 = **90**
- **Also matched:** RPO-001
- **AI note:** Start with the STOR-001 remediation steps for FAB-APP01. It has failed 2 runs in a row, so check what changed.

**Remediation**

1. Check repository / target free space and the growth trend for this client.
2. Review retention settings and remove orphaned or expired restore points per policy.
3. If over a cloud quota, raise the quota or adjust the selection with the client's approval.
4. Re-run the job once space is confirmed and verify the chain completed.
5. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
6. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
7. Check the schedule is enabled and not stuck behind a long-running job.

### [P1] Application-aware processing failure (SQL / Exchange): Northwind Dental / NWD-SQL01

- **Rule:** `APP-001` (application, base severity high)
- **Job:** veeam / SQL Nightly / status `failed`
- **Message:** Failed to prepare guest for hot backup: SqlServerWriter is in a failed state. VSS_E_WRITERERROR_RETRYABLE (0x800423f3)
- **Evidence:** status=failed; message matches /SqlServerWriter|SQL Server VSS Writer/; message matches /VSS_E_[A-Z_]+/; RPO 24h breached (54.3h since last success)
- **Score:** severity 55 + rpo_breach 16 + failure_streak 5 + client_tier 10 = **86**
- **Also matched:** VSS-001, RPO-001
- **AI note:** Start with the APP-001 remediation steps for NWD-SQL01. It has failed 2 runs in a row, so check what changed.

**Remediation**

1. Check the guest credentials used for application-aware processing.
2. Run `vssadmin list writers` in the guest and confirm the SQL/Exchange writer is stable.
3. Check SQL/Exchange logs for backups taken by other tools that break the log chain.
4. Confirm transaction log growth is under control until a successful backup truncates it.
5. Run `vssadmin list writers` and note any writer not in a Stable / No error state.
6. Restart the service that owns the failed writer (e.g. SQL Writer, Hyper-V VMMS, WMI) out of hours.
7. Check shadow storage with `vssadmin list shadowstorage` and free space on the source volume.
8. Look for overlapping snapshot schedules (other backup agents, AV, Windows Server Backup).
9. Review Application log events from VSS (8193, 12289, 12293) around the job start time.
10. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
11. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
12. Check the schedule is enabled and not stuck behind a long-running job.

### [P1] RPO breached / no recent successful backup: Fabrikam Legal / FAB-LT02

- **Rule:** `RPO-001` (rpo, base severity high)
- **Job:** cove / Files and Folders / status `success`
- **Message:** -
- **Evidence:** RPO 12h breached (86.7h since last success)
- **Score:** severity 55 + rpo_breach 20 + client_tier 10 = **85**
- **AI note:** Start with the RPO-001 remediation steps for FAB-LT02.

**Remediation**

1. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
2. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
3. Check the schedule is enabled and not stuck behind a long-running job.

### [P2] Credential or permission failure: Contoso Logistics / contoso-logistics.example

- **Rule:** `AUTH-001` (credentials, base severity high)
- **Job:** m365-backup / Exchange Online mailboxes / status `failed`
- **Message:** Authentication failed: token has expired. Re-authorize the Microsoft 365 application.
- **Evidence:** status=failed; message matches /authentication (failed|failure)/; RPO 24h breached (53.5h since last success)
- **Score:** severity 55 + rpo_breach 16 + client_tier 5 = **76**
- **Also matched:** RPO-001
- **AI note:** Start with the AUTH-001 remediation steps for contoso-logistics.example.

**Remediation**

1. Check whether the backup service account password was changed or has expired.
2. Update the stored credential in the backup console and test it against the host.
3. Confirm the account still has local admin / required role permissions.
4. For Microsoft 365 jobs, re-authorise the app registration or consent if the token expired.
5. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
6. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
7. Check the schedule is enabled and not stuck behind a long-running job.

### [P2] Credential or permission failure: Adatum Accounting / ADA-APP02

- **Rule:** `AUTH-001` (credentials, base severity high)
- **Job:** veeam / App Server Weekly / status `failed`
- **Message:** Guest processing: Access is denied. Logon failure: unknown user name or bad password
- **Evidence:** status=failed; message matches /access (is )?denied/; RPO 48h breached (178.4h since last success)
- **Score:** severity 55 + rpo_breach 20 = **75**
- **Also matched:** RPO-001
- **AI note:** Start with the AUTH-001 remediation steps for ADA-APP02.

**Remediation**

1. Check whether the backup service account password was changed or has expired.
2. Update the stored credential in the backup console and test it against the host.
3. Confirm the account still has local admin / required role permissions.
4. For Microsoft 365 jobs, re-authorise the app registration or consent if the token expired.
5. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
6. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
7. Check the schedule is enabled and not stuck behind a long-running job.

### [P2] Backup target / repository out of space or over quota: Adatum Accounting / ADA-FS01

- **Rule:** `STOR-001` (storage, base severity high)
- **Job:** cove / Files and Folders / status `failed`
- **Message:** Storage quota exceeded.
- **Evidence:** status=failed; message matches /quota (exceeded|reached)/; RPO 48h breached (54.8h since last success)
- **Score:** severity 55 + rpo_breach 10 = **65**
- **Also matched:** RPO-001
- **AI note:** Start with the STOR-001 remediation steps for ADA-FS01.

**Remediation**

1. Check repository / target free space and the growth trend for this client.
2. Review retention settings and remove orphaned or expired restore points per policy.
3. If over a cloud quota, raise the quota or adjust the selection with the client's approval.
4. Re-run the job once space is confirmed and verify the chain completed.
5. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
6. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
7. Check the schedule is enabled and not stuck behind a long-running job.

### [P2] Network / connectivity timeout: Tailspin Clinic / TSC-PM01

- **Rule:** `NET-001` (network, base severity medium)
- **Job:** cove / System State / status `failed`
- **Message:** Timeout while waiting for storage node response; connection reset by peer
- **Evidence:** status=failed; message matches /timed? ?out/; RPO 24h breached (75.0h since last success)
- **Score:** severity 35 + rpo_breach 20 + client_tier 10 = **65**
- **Also matched:** RPO-001
- **AI note:** Start with the NET-001 remediation steps for TSC-PM01.

**Remediation**

1. Confirm the host and the backup server / gateway can reach each other on the required ports.
2. Check for ISP outages, VPN tunnel drops or firewall changes in the job window.
3. Check DNS resolution of the host name from the backup server.
4. If recurrent at the same time, look for bandwidth contention with other scheduled jobs.
5. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
6. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
7. Check the schedule is enabled and not stuck behind a long-running job.

### [P2] Recovery point verification failed: Contoso Logistics / CTL-SQL02

- **Rule:** `VERIFY-001` (verification, base severity high)
- **Job:** datto / CTL-SIRIS01 agent backup / status `warning`
- **Message:** Screenshot verification failed.
- **Evidence:** message matches /screenshot verification failed/
- **Score:** severity 55 + client_tier 5 = **60**
- **AI note:** Start with the VERIFY-001 remediation steps for CTL-SQL02.

**Remediation**

1. Treat the latest recovery point as unproven until a test boot or file-level restore succeeds.
2. Run a manual verification / test restore of the latest point.
3. If corruption is reported, run a storage-level health check and an active full if required.

References: https://github.com/ich74851-doom/hyperv-vmware-restore-validation

### [P3] Backup agent offline or job did not start: Adatum Accounting / ADA-LT07

- **Rule:** `AGENT-001` (agent, base severity medium)
- **Job:** cove / Files and Folders / status `missed`
- **Message:** Device offline: backup agent not responding
- **Evidence:** status=missed; message matches /agent (is )?(offline|not responding|unreachable)/; RPO 48h breached (134.0h since last success)
- **Score:** severity 35 + rpo_breach 18 = **53**
- **Also matched:** RPO-001
- **AI note:** Start with the AGENT-001 remediation steps for ADA-LT07.

**Remediation**

1. Check the device is powered on and online in the RMM.
2. Restart the backup agent service and confirm it reconnects to the console.
3. Confirm the schedule is enabled and not blocked by a maintenance window.
4. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
5. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
6. Check the schedule is enabled and not stuck behind a long-running job.

### [P3] Network / connectivity timeout: Contoso Logistics / CTL-WEB01

- **Rule:** `NET-001` (network, base severity medium)
- **Job:** veeam / Web Tier / status `failed`
- **Message:** Failed to connect to guest: The RPC server is unavailable. (0x800706BA)
- **Evidence:** status=failed; message matches /RPC server is unavailable/; RPO 24h breached (29.3h since last success)
- **Score:** severity 35 + rpo_breach 11 + client_tier 5 = **51**
- **Also matched:** RPO-001
- **AI note:** Start with the NET-001 remediation steps for CTL-WEB01.

**Remediation**

1. Confirm the host and the backup server / gateway can reach each other on the required ports.
2. Check for ISP outages, VPN tunnel drops or firewall changes in the job window.
3. Check DNS resolution of the host name from the backup server.
4. If recurrent at the same time, look for bandwidth contention with other scheduled jobs.
5. Confirm when the last good recovery point was created and tell the client owner if the SLA is at risk.
6. Run the job manually once the underlying cause is fixed and confirm a new restore point exists.
7. Check the schedule is enabled and not stuck behind a long-running job.

### [P4] Licensing or subscription problem: Adatum Accounting / ADA-SQL01

- **Rule:** `LICENSE-001` (licensing, base severity medium)
- **Job:** datto / ADA-ALTO01 agent backup / status `failed`
- **Message:** Backup failed: license has expired for this protected agent
- **Evidence:** message matches /licen[cs]e (has )?(expired|exceeded|invalid)/
- **Score:** severity 35 = **35**
- **AI note:** Start with the LICENSE-001 remediation steps for ADA-SQL01.

**Remediation**

1. Check licence allocation in the vendor console for this client.
2. Reclaim licences from decommissioned devices or raise a purchase request.

### [P4] Files skipped because they were locked or in use: Northwind Dental / NWD-WS03

- **Rule:** `LOCK-001` (file-access, base severity low)
- **Job:** cove / Files and Folders / status `warning`
- **Message:** 3 files skipped: the process cannot access the file because it is being used by another process (archive.pst)
- **Evidence:** status=warning; message matches /being used by another process/
- **Score:** severity 15 + client_tier 10 = **25**
- **AI note:** Start with the LOCK-001 remediation steps for NWD-WS03.

**Remediation**

1. Identify the skipped files; if they matter (PSTs, databases) protect them with VSS or app-aware backup.
2. Exclude transient / temp paths that do not need protecting.

### [P4] Changed block tracking reset or unavailable: Contoso Logistics / CTL-HV01

- **Rule:** `CBT-001` (cbt, base severity low)
- **Job:** veeam / Hyper-V Cluster / status `warning`
- **Message:** Changed block tracking reset for VM disk; full read performed
- **Evidence:** status=warning; message matches /changed block tracking/
- **Score:** severity 15 + client_tier 5 = **20**
- **AI note:** Start with the CBT-001 remediation steps for CTL-HV01.

**Remediation**

1. Expect a longer, full-read incremental on the next run; check it fits the backup window.
2. If CBT resets repeatedly, reset CBT on the VM during a maintenance window.

