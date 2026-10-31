# Linux Server Migration and Verification Dashboard

## 1. Project Overview

This project focuses on migrating data and configurations from one Linux server to another Linux server.

It uses a source server and a destination server to demonstrate how server migration can be performed and verified.

A web-based dashboard is developed using Python Flask to monitor the migration process and check whether important configurations and files have been transferred correctly.

The main objective is to make Linux server migration easier to monitor, manage and verify.

## 2. Objectives

- Migrate files and data from a source Linux server to a destination Linux server.
- Maintain file integrity during migration.
- Verify user and group configurations.
- Check file permissions and access control.
- Monitor storage and backup-related configurations.
- Provide a centralized dashboard to view migration progress and verification results.

## 3. System Architecture

The project consists of three main components:

**1. Source Server**
- Contains the original data.
- Stores the source directory (`/srv/company`).
- Generates a baseline containing system and file information.

**2. Destination Server**
- Receives the migrated files and configurations.
- Performs migration verification checks.
- Hosts the Flask dashboard backend.

**3. Web Dashboard**
- Provides a graphical interface for monitoring migration.
- Displays verification results.
- Shows whether individual checks have passed or require attention.

## 4. Technologies Used

| Technology | Purpose |
|---|---|
| Linux (Ubuntu) | Server operating system |
| Python | Automation and backend logic |
| Flask | Web dashboard backend |
| HTML, CSS, JavaScript | Dashboard interface |
| SSH | Secure communication between servers |
| SCP | Transfer of baseline files |
| Rsync | File synchronization |
| LVM | Storage management |
| SHA-256 | File integrity verification |
| ACL | File access control |

## 5. How the Project Works

The migration and verification process follows these steps:

1. **Source Baseline Generation:** A Python script collects important information from the source server, including hostname, users, groups, directory entries and SHA-256 file hashes.

2. **Baseline Transfer:** The generated baseline information is securely transferred to the destination server using SCP.

3. **Data Migration:** Files and required configurations are transferred from the source server to the destination server.

4. **Migration Verification:** The destination server checks the migrated environment against the source baseline.

5. **Dashboard Monitoring:** The Flask application displays the results of different verification checks through a web interface.

6. **Final Status:** The dashboard displays the overall migration verification status based on the completed checks.

## 6. Dashboard Features

The dashboard includes the following verification categories:

- Storage verification
- User and group verification
- Migration verification
- Access control verification
- Backup verification
- Security verification
- Log verification
- Final migration report

The dashboard performs 23 verification checks.

**Status Indicators:**
- **VERIFIED:** All required verification checks have passed.
- **ATTENTION:** One or more checks require attention.

## 7. Project Structure

The project contains the following important components:

```text
migration-dashboard-bundle/
│
├── backend/
│   └── app.py
│
├── index.html
│
├── make_source_baseline.py
│
└── README.md
```

## 8. Running the Dashboard

### Prerequisites

- Two Linux servers (source and destination).
- Python 3.
- Flask.
- SSH connectivity between the servers.
- Required migration utilities such as Rsync and LVM.

### Steps

**Step 1: Generate the source baseline**

Run the baseline generation script on the source server.

```bash
python3 make_source_baseline.py
```

**Step 2: Transfer the baseline**

Transfer the generated baseline file to the destination server using SCP.

**Step 3: Start the dashboard**

On the destination server, run:

```bash
sudo python3 backend/app.py
```

**Step 4: Access the dashboard**

To access the dashboard securely from another machine, establish an SSH tunnel:

```bash
ssh -N -L 5003:127.0.0.1:5000 USER@192.168.56.20
```

Replace `USER` with the destination server's username.

Open Firefox and navigate to:

```text
http://127.0.0.1:5003
```

The migration dashboard will be displayed in the browser.

## 9. Expected Outcome

The project provides a centralized way to monitor and verify Linux server migration.

Instead of manually checking every configuration and file, administrators can use the dashboard to view verification results and identify areas that require attention.

The project demonstrates practical applications of Linux system administration, server migration, automation, networking and web development.

## 10. Conclusion

This project demonstrates a structured approach to Linux server migration and verification.

By combining Linux administration tools, Python automation and a web-based dashboard, it makes the migration process easier to monitor and validate.

It also provides practical experience in server management, secure file transfer, data integrity checking and system verification.

---

**Project:** Linux Server Migration and Verification Dashboard  
**Repository:** [linux_server_migration](https://github.com/Shobith15/linux_server_migration)
