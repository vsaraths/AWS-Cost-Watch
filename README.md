AWS CostWatch - Real-Time AWS Resource & Cost Monitor


🚀 Overview
AWS CostWatch is a real-time dashboard that monitors your AWS resources, tracks free tier usage, and provides cost estimates without requiring AWS Cost Explorer. It provides immediate visibility into your AWS spending and resource utilization.

## 🎯 Purpose
AWS CostWatch was created to help **AWS learners, DevOps beginners, and cloud enthusiasts** understand their real-time resource usage and avoid unexpected bills.  

✨ Features
📊 Real-Time Monitoring
EC2 Instances: Monitor running/stopped instances, uptime, and costs
S3 Buckets: Track bucket creation dates, regions, and storage costs
RDS Databases: Monitor database instances and costs
Lambda Functions: Track function counts and execution estimates
CloudWatch Alarms: Monitor alarm states and metrics

💰 Cost Tracking
Real-time cost estimates using AWS pricing
Free tier usage tracking (750 hours for EC2/RDS)
Projected monthly and yearly cost estimates
Lifetime cost calculations for each resource

🚨 Alert System
High-cost alerts when spending exceeds thresholds

Free tier usage warnings
Resource state monitoring
Multi-level alerts (Critical/Warning/Info)

📈 Dashboard Features
Live auto-refresh every 60 seconds
Multi-region scanning (us-east-1, us-east-2, us-west-1, etc.)
Progress bars for free tier usage
Detailed resource breakdowns

🛠️ Installation
Prerequisites
Python 3.8 or higher

AWS Account with IAM credentials

AWS CLI configured

Step 1: Clone the Repository

git clone https://github.com/vsaraths/AWS-Cost-Watch.git
cd AWS-Cost-Watch
Step 2: Install Dependencies

pip install -r requirements.txt

Required Packages:

boto3 - AWS SDK for Python
rich - Terminal formatting and dashboard UI
botocore - AWS CLI core library

Step 3: Configure AWS Credentials

aws configure
Enter your:

AWS Access Key ID
AWS Secret Access Key
Default region (e.g., us-east-1)
Default output format (e.g., json)

Step 4: Run the Dashboard

python aws_cost_dashboard.py
🔧 IAM Permissions Required
Create an IAM policy with the following permissions:

json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CostWatchPermissions",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeRegions",
                "ec2:DescribeVolumes",
                "ec2:DescribeAddresses",
                "ec2:DescribeNatGateways",
                "s3:ListBuckets",
                "s3:GetBucketLocation",
                "rds:DescribeDBInstances",
                "lambda:ListFunctions",
                "cloudwatch:DescribeAlarms",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
📁 Project Structure
text
AWS-Cost-Watch/
├── aws_cost_dashboard.py     # Main dashboard application
├── requirements.txt          # Python dependencies
├── README.md                # This file
├── LICENSE                  # MIT License
└── screenshots/             # Dashboard screenshots
🎯 Usage
Starting the Dashboard

python aws_cost_dashboard.py
Dashboard Components
Header: AWS CostWatch title and version

Cost Estimates: Real-time cost projections
Resources: Active resource counts
EC2 Instances: Detailed instance information
S3 Buckets: Bucket details and costs
Status Panel: System and AWS status
Footer: Update timestamp and controls

Controls
Auto-refresh: Updates every 60 seconds

Exit: Press Ctrl+C to exit the dashboard

🔍 How It Works
Cost Estimation
Uses AWS published pricing for each service

Calculates costs based on:
Instance type (EC2/RDS)
Uptime (hours running)
Storage size (S3/EBS)
Function counts (Lambda)
Projects monthly costs based on current usage patterns

Free Tier Tracking
Tracks t2/t3.micro instances for EC2
Tracks db.t2/t3.micro instances for RDS
Monitors 750-hour monthly limit
Shows percentage usage with progress bars

Multi-Region Support
Automatically discovers enabled regions
Scans multiple regions simultaneously
Aggregates data from all regions

🚨 Alerts and Warnings
Cost Alerts
Red: Monthly cost > $100
Yellow: Monthly cost > $50
Green: Monthly cost < $50

Free Tier Alerts
Red: >95% of free tier used
Yellow: >80% of free tier used
Green: <80% of free tier used
Resource Alerts
Zombie EBS volumes (unattached)
Orphaned Elastic IPs
Non-free tier instances running

📊 Sample Output

AWS CostWatch - Real-Time Dashboard

💰 COST ESTIMATES
├── Current Hourly: $0.035/hr
├── Projected Daily: $0.84/day
└── Projected Monthly: $25.20/month

📊 RESOURCES
├── 🖥️ EC2: 3 running (5 total)
├── 🗄️ RDS: 1 running (1 total)
├── 📦 S3: 12 buckets
└── λ Lambda: 8 functions

🖥️ EC2 INSTANCES
├── web-server-1 | t3.micro | running 45d | $14.85
├── db-backup-1 | t2.micro | running 30d | $9.89
└── test-instance | m5.large | stopped 5d | $12.50
🔄 Refresh Schedule
Full scan: Every 60 seconds

Data types: All AWS resources
Regions: All enabled AWS regions
Cost updates: Real-time calculations

🛡️ Security
Data Privacy
No data leaves your local machine
All calculations done locally
AWS credentials never transmitted
Only read-only API calls made

Best Practices
Use IAM roles with minimal permissions
Regularly rotate AWS credentials
Monitor dashboard usage
Review cost alerts promptly

🚀 Performance
Optimization Features
Regional client caching
Intelligent error handling
Parallel region scanning
Progress tracking
Memory-efficient data structures

System Requirements
CPU: Minimal (single-threaded)

Memory: <100MB
Network: Broadband internet
Storage: <10MB

📈 Future Enhancements
Planned Features
Cost Explorer integration (when enabled)

EBS volume size tracking
Data transfer cost calculations
Cost-saving recommendations
Historical cost trending
Email/Slack notifications
Web dashboard interface
Multi-account support

Current Limitations
Estimated costs (not actual billing)
No VPC flow log analysis
Limited CloudWatch metric integration
No support for AWS Organizations

🤝 Contributing
How to Contribute
Fork the repository

Create a feature branch

Make your changes
Submit a pull request
Development Setup

# Clone your fork
git clone https://github.com/YOUR-USERNAME/AWS-Cost-Watch.git

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
Code Style
Follow PEP 8 guidelines

Use type hints where possible
Add docstrings for functions
Include error handling

🐛 Troubleshooting
Common Issues
1. AWS Credentials Error
text
Error: Unable to locate credentials
Solution: Run aws configure and enter valid credentials.

2. Permission Denied
text
ClientError: An error occurred (UnauthorizedOperation)...
Solution: Ensure IAM user has required permissions.

3. No Data Showing
text
No resources found
Solution: Check if you have resources in the scanned regions.

4. Cost Explorer Not Enabled
text
Cost Explorer API not enabled
Solution: This is expected. The dashboard uses estimated costs.

Debug Mode
For detailed logging, add debug prints in the code:

python
# Enable debug output
import logging
logging.basicConfig(level=logging.DEBUG)
📚 Documentation
API Reference
The dashboard uses these AWS API calls:

describe_instances() - Get EC2 instances
list_buckets() - Get S3 buckets
describe_db_instances() - Get RDS instances
list_functions() - Get Lambda functions
describe_alarms() - Get CloudWatch alarms

Pricing Reference
Uses AWS On-Demand pricing for:

EC2 Pricing
RDS Pricing
S3 Pricing
Lambda Pricing

📄 License
MIT License - See LICENSE file for details.

🙏 Acknowledgments
AWS Boto3 Team - Python AWS SDK

Rich Library - Beautiful terminal formatting

AWS Free Tier - Cost monitoring target

📞 Support
Issues and Questions
GitHub Issues: Create an issue

Email: vsarath732@gmail.com

Feature Requests
Submit feature requests through GitHub Issues with the "enhancement" label.

🌟 Star History
If you find this project useful, please give it a star! ⭐

Made with ❤️ for the AWS Community

Monitor your cloud costs before they monitor you!
