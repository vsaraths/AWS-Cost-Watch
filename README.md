# 🟢 AWS CostWatch v8.1 – DevOps + FinOps Dashboard  

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![AWS](https://img.shields.io/badge/AWS-Boto3-orange.svg)
![Version](https://img.shields.io/badge/Version-v8.1-green.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Stable-success.svg)

---

## 📘 Overview  

**AWS CostWatch v8.1** is a real-time **AWS cost and resource monitoring dashboard** built for DevOps & FinOps engineers.  
It visualizes AWS resource utilization, spending, and inefficiencies using a **terminal-based live dashboard** (powered by `rich`).  

The tool helps teams **monitor costs**, **detect idle or orphaned resources**, and **understand data transfer patterns** —  
all in one clean, classic green command-line interface.  

---

## 🧩 Key Features  

### 💵 FinOps Insights
- **Per-Instance Daily Cost Panel** – Shows daily cost of every running EC2, RDS, and Lambda resource.  
- **Service Cost Breakdown** – Visualize cost by AWS service via Cost Explorer.  
- **Budget Overview** – Pulls budget usage from AWS Budgets API.  

### 💤 Optimization Detection
- **Idle Resource Estimator** – Detects EC2/RDS instances with CPU < 5% using CloudWatch metrics.  
- **Zombie Resource Detection** – Finds unused or stopped resources consuming costs.  
- **Ephemeral Resource Tracking** – Detects resources that were spun up and deleted quickly.  

### 📦 Storage & Data
- **EBS Snapshot Cleanup** – Lists orphaned and old snapshots (age > 30 days).  
- **S3 Cost Estimation** – Estimates cost for all S3 buckets based on usage tiers.  

### 🌍 Network & Transfer Costs
- **Detailed Data Transfer Matrix** – Breaks down *North–South* (internet) and *East–West* (inter-region) costs.  
- **Regional Matrix View** – Visualize which regions exchange the most traffic.  

### ⚡ Live Dashboard
- Built with the [`rich`](https://github.com/Textualize/rich) library.  
- **Auto-refreshes every 10 minutes** (configurable).  
- SQLite-based cost history for 7-scan trend charts.  
- Classic green-themed terminal UI.  

---

## 🖼️ Dashboard Preview  

*(Add a screenshot here — example placeholder below)*  
![AWS CostWatch v8.1 Dashboard](assets/dashboard_preview.png)

---

## ⚙️ Setup  

### 🧱 Requirements  
- Python 3.9 or later  
- AWS CLI configured with valid credentials  
- IAM permissions for:
  - `ec2:Describe*`
  - `rds:Describe*`
  - `s3:ListAllMyBuckets`
  - `lambda:ListFunctions`
  - `cloudwatch:GetMetricStatistics`
  - `ce:GetCostAndUsage`
  - `budgets:DescribeBudgets`
  - `cloudtrail:LookupEvents`

### 📦 Install dependencies  
```bash
pip install boto3 rich sqlite-utils
🚀 Run the dashboard
python3 aws_costwatch_v8.py

bash
Copy code
python3 aws_costwatch_v8.py

It will:

Run an initial scan instantly.

Display the real-time terminal dashboard.

Auto-refresh every 10 minutes.

🧭 Dashboard Panels
Section Description
💰 Cost Summary  Current, daily, and projected monthly costs.
🖥️ Active Resources Running EC2, RDS, and Lambda instances with daily cost.
💤 Idle Resources  Resources with low CPU/network activity (potential waste).
📦 Snapshot Cleanup  Orphaned or old EBS snapshots.
🌍 Data Transfer Matrix  Inter-region and internet egress costs.
📊 Service Breakdown Top 10 services by cost.
⚡ Status Panel  Account, region count, next scan time, and overall health.
🗃️ Data Storage

All scans are stored locally in an SQLite database:

aws_costwatch.db


You can query it manually:

sqlite3 aws_costwatch.db "SELECT * FROM scans ORDER BY id DESC LIMIT 5;"

🧠 FinOps Best Practices Supported
Section	Description
💰 Cost Summary	Current, daily, and projected monthly costs.
🖥️ Active Resources	Running EC2, RDS, and Lambda instances with daily cost.
💤 Idle Resources	Resources with low CPU/network activity (potential waste).
📦 Snapshot Cleanup	Orphaned or old EBS snapshots.
🌍 Data Transfer Matrix	Inter-region and internet egress costs.
📊 Service Breakdown	Top 10 services by cost.
⚡ Status Panel	Account, region count, next scan time, and overall health.

🗃️ Data Storage
All scans are stored locally in an SQLite database:

Copy code
aws_costwatch.db
You can query it manually:

bash
Copy code
sqlite3 aws_costwatch.db "SELECT * FROM scans ORDER BY id DESC LIMIT 5;"

🧠 FinOps Best Practices Supported

✅ Detect and clean up idle resources
✅ Estimate cross-region transfer costs
✅ Right-size EC2/RDS workloads
✅ Track cost anomalies between scans
✅ Optimize storage and snapshot retention

📈 Release History
Version Date  Highlights
v8.1  2025-12-18  Added daily cost panel, idle resource estimator, EBS cleanup, and transfer matrix
v8.0  2025-12-10  Real-time dashboard, SQLite persistence, budget support
v7.x  2025-11 Early costwatch prototypes

🧰 Tech Stack
Component Purpose
Python (boto3)  AWS API integration
Rich  Terminal dashboard UI
SQLite3 Local persistence
CloudWatch / Cost Explorer  Metrics and cost data
AWS Budgets API Budget tracking

🧑‍💻 Author

👤 Sarath V
DevOps & Cloud Engineer
🔗 GitHub Profile

📧 (optional)

⚖️ License

This project is licensed under the MIT License – see the LICENSE
 file for details.

💬 Contributing

Pull requests are welcome!
Please open an issue first to discuss proposed changes.

git checkout -b feature/my-new-feature
git commit -m "Add new feature"
git push origin feature/my-new-feature

🌟 Support
Version	Date	Highlights
v8.1	2025-12-18	Added daily cost panel, idle resource estimator, EBS cleanup, and transfer matrix
v8.0	2025-12-10	Real-time dashboard, SQLite persistence, budget support
v7.x	2025-11	Early costwatch prototypes

If you find this project useful, please ⭐ it on GitHub and share it with other FinOps engineers!
Together we can make AWS cost visibility easy and automated.

“You can’t optimize what you don’t measure. CostWatch helps you measure precisely.”

— Sarath V
