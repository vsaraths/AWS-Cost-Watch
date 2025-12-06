import boto3
from datetime import datetime, timedelta, timezone
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import time

# Initialize AWS clients
ce_client = boto3.client('ce', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')
rds_client = boto3.client('rds', region_name='us-east-1')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda', region_name='us-east-1')
dynamodb_client = boto3.client('dynamodb', region_name='us-east-1')

# AWS Free Tier Limits (Monthly)
FREE_TIER_LIMITS = {
    'Amazon Elastic Compute Cloud - Compute': {
        'name': 'EC2',
        'limit': 750,  # hours per month
        'unit': 'hours',
        'description': '750 hours t2.micro/t3.micro'
    },
    'Amazon Relational Database Service': {
        'name': 'RDS',
        'limit': 750,  # hours per month
        'unit': 'hours',
        'description': '750 hours db.t2.micro/db.t3.micro'
    },
    'Amazon Simple Storage Service': {
        'name': 'S3',
        'limit': 5,  # GB storage
        'unit': 'GB',
        'description': '5 GB storage, 20K GET, 2K PUT'
    },
    'AWS Lambda': {
        'name': 'Lambda',
        'limit': 1000000,  # requests per month
        'unit': 'requests',
        'description': '1M requests, 400K GB-seconds'
    },
    'Amazon DynamoDB': {
        'name': 'DynamoDB',
        'limit': 25,  # GB storage
        'unit': 'GB',
        'description': '25 GB storage, 25 RCU/WCU'
    },
    'Amazon CloudWatch': {
        'name': 'CloudWatch',
        'limit': 10,  # metrics
        'unit': 'metrics',
        'description': '10 metrics, 10 alarms, 1M API requests'
    },
    'Amazon Virtual Private Cloud': {
        'name': 'VPC',
        'limit': 0,  # Free
        'unit': 'free',
        'description': 'Always free'
    },
    'AWS Key Management Service': {
        'name': 'KMS',
        'limit': 20000,  # requests
        'unit': 'requests',
        'description': '20K free requests'
    },
    'Amazon Simple Notification Service': {
        'name': 'SNS',
        'limit': 1000,  # emails
        'unit': 'emails',
        'description': '1K emails, 1M mobile pushes'
    }
}

def get_running_resources():
    """Get all running AWS resources"""
    resources = {
        'ec2': [],
        'rds': [],
        's3': [],
        'lambda': [],
        'dynamodb': []
    }
    
    try:
        # EC2 Instances
        ec2_response = ec2_client.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )
        for reservation in ec2_response['Reservations']:
            for instance in reservation['Instances']:
                name = 'Unnamed'
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        name = tag['Value']
                
                resources['ec2'].append({
                    'name': name,
                    'id': instance['InstanceId'],
                    'type': instance['InstanceType'],
                    'launch_time': instance['LaunchTime'],
                    'free_tier': instance['InstanceType'] in ['t2.micro', 't3.micro']
                })
    except Exception as e:
        pass
    
    try:
        # RDS Instances
        rds_response = rds_client.describe_db_instances()
        for db in rds_response['DBInstances']:
            resources['rds'].append({
                'name': db['DBInstanceIdentifier'],
                'type': db['DBInstanceClass'],
                'engine': db['Engine'],
                'status': db['DBInstanceStatus'],
                'free_tier': db['DBInstanceClass'] in ['db.t2.micro', 'db.t3.micro']
            })
    except Exception as e:
        pass
    
    try:
        # S3 Buckets
        s3_response = s3_client.list_buckets()
        for bucket in s3_response['Buckets']:
            resources['s3'].append({
                'name': bucket['Name'],
                'created': bucket['CreationDate']
            })
    except Exception as e:
        pass
    
    try:
        # Lambda Functions
        lambda_response = lambda_client.list_functions()
        for func in lambda_response['Functions']:
            resources['lambda'].append({
                'name': func['FunctionName'],
                'runtime': func['Runtime'],
                'memory': func['MemorySize']
            })
    except Exception as e:
        pass
    
    try:
        # DynamoDB Tables
        dynamodb_response = dynamodb_client.list_tables()
        for table_name in dynamodb_response['TableNames']:
            resources['dynamodb'].append({
                'name': table_name
            })
    except Exception as e:
        pass
    
    return resources

def get_service_costs_current_month():
    """Get all service costs for current month"""
    today = datetime.now(timezone.utc).date()
    start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    
    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': start_of_month, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'SERVICE'}]
        )
        
        services = {}
        if response['ResultsByTime'] and len(response['ResultsByTime']) > 0:
            for group in response['ResultsByTime'][0].get('Groups', []):
                service_name = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                services[service_name] = cost
        
        return services
    except Exception as e:
        return {}

def get_daily_service_costs():
    """Get yesterday's service costs"""
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    
    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'SERVICE'}]
        )
        
        services = []
        if response['ResultsByTime'] and len(response['ResultsByTime']) > 0:
            for group in response['ResultsByTime'][0].get('Groups', []):
                service_name = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                if cost > 0.001:
                    services.append((service_name, cost))
        
        services.sort(key=lambda x: x[1], reverse=True)
        return services
    except Exception as e:
        return []

def get_monthly_total():
    """Get month-to-date total"""
    today = datetime.now(timezone.utc).date()
    start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    
    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': start_of_month, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost']
        )
        
        if response['ResultsByTime']:
            return float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
        return 0.0
    except Exception as e:
        return 0.0

def calculate_month_projection(monthly_cost):
    """Project end-of-month cost"""
    today = datetime.now(timezone.utc).date()
    days_elapsed = today.day
    days_in_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    total_days = days_in_month.day
    
    if days_elapsed > 0:
        daily_avg = monthly_cost / days_elapsed
        projected = daily_avg * total_days
        return projected, daily_avg
    return 0, 0

def show_retro_dashboard():
    console = Console()
    console.clear()
    
    # Header
    header = """
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║     █████╗ ██╗    ██╗███████╗     ██████╗ ██████╗ ███████╗████████╗ ║
    ║    ██╔══██╗██║    ██║██╔════╝    ██╔════╝██╔═══██╗██╔════╝╚══██╔══╝ ║
    ║    ███████║██║ █╗ ██║███████╗    ██║     ██║   ██║███████╗   ██║    ║
    ║    ██╔══██║██║███╗██║╚════██║    ██║     ██║   ██║╚════██║   ██║    ║
    ║    ██║  ██║╚███╔███╔╝███████║    ╚██████╗╚██████╔╝███████║   ██║    ║
    ║    ╚═╝  ╚═╝ ╚══╝╚══╝ ╚══════╝     ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝    ║
    ║                                                                       ║
    ║               W A T C H   S Y S T E M   v2.0                         ║
    ║               [ DevOps Free Tier Monitor ]                           ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """
    console.print(header, style="bold green")
    console.print()
    
    # Loading animation
    console.print("    [bold yellow]>>> SCANNING AWS ACCOUNT...[/bold yellow]", end="")
    time.sleep(0.3)
    console.print(" [bold green]OK[/bold green]")
    
    console.print("    [bold yellow]>>> CHECKING FREE TIER STATUS...[/bold yellow]", end="")
    resources = get_running_resources()
    service_costs = get_service_costs_current_month()
    time.sleep(0.3)
    console.print(" [bold green]OK[/bold green]")
    
    console.print("    [bold yellow]>>> CALCULATING PROJECTIONS...[/bold yellow]", end="")
    monthly_total = get_monthly_total()
    projected, daily_avg = calculate_month_projection(monthly_total)
    time.sleep(0.3)
    console.print(" [bold green]OK[/bold green]")
    
    console.print()
    console.print("    " + "─" * 71)
    console.print()
    
    # Cost Summary
    console.print("    ╔═══════════════════════════════════════════════════════════════════╗")
    console.print("    ║                [bold yellow]💰 COST SUMMARY - ALERT SYSTEM 💰[/bold yellow]              ║")
    console.print("    ╠═══════════════════════════════════════════════════════════════════╣")
    console.print(f"    ║                                                                   ║")
    console.print(f"    ║  Month-to-Date:          [cyan]${monthly_total:>10.2f}[/cyan]                       ║")
    console.print(f"    ║  Daily Average:          [yellow]${daily_avg:>10.2f}[/yellow]                       ║")
    console.print(f"    ║  Projected Month-End:    [bold {'red' if projected > 10 else 'green'}]${projected:>10.2f}[/bold {'red' if projected > 10 else 'green'}]                       ║")
    console.print(f"    ║                                                                   ║")
    
    if projected > 10:
        console.print("    ║  [bold red blink]⚠ WARNING: EXCEEDING FREE TIER! ⚠[/bold red blink]                    ║")
    else:
        console.print("    ║  [bold green]✓ WITHIN SAFE LIMITS[/bold green]                                      ║")
    
    console.print("    ╚═══════════════════════════════════════════════════════════════════╝")
    console.print()
    
    # Active Resources by Service
    console.print("    ╔═══════════════════════════════════════════════════════════════════╗")
    console.print("    ║            [bold cyan]🖥️  ACTIVE RESOURCES BY SERVICE 🖥️[/bold cyan]                ║")
    console.print("    ╠═══════════════════════════════════════════════════════════════════╣")
    
    # EC2
    if resources['ec2']:
        console.print(f"    ║                                                                   ║")
        console.print(f"    ║  [bold white]EC2 INSTANCES:[/bold white] {len(resources['ec2'])} running                               ║")
        for ec2 in resources['ec2']:
            tier_status = "[green]FREE TIER ✓[/green]" if ec2['free_tier'] else "[red]PAID[/red]"
            console.print(f"    ║    • {ec2['name'][:20]:20} {ec2['type']:12} {tier_status}  ║")
    
    # RDS
    if resources['rds']:
        console.print(f"    ║                                                                   ║")
        console.print(f"    ║  [bold white]RDS DATABASES:[/bold white] {len(resources['rds'])} active                               ║")
        for rds in resources['rds']:
            tier_status = "[green]FREE TIER ✓[/green]" if rds['free_tier'] else "[red]PAID[/red]"
            console.print(f"    ║    • {rds['name'][:20]:20} {rds['type']:12} {tier_status}  ║")
    
    # S3
    if resources['s3']:
        console.print(f"    ║                                                                   ║")
        console.print(f"    ║  [bold white]S3 BUCKETS:[/bold white] {len(resources['s3'])} buckets                                  ║")
        for s3 in resources['s3'][:3]:
            console.print(f"    ║    • {s3['name'][:50]:50}            ║")
    
    # Lambda
    if resources['lambda']:
        console.print(f"    ║                                                                   ║")
        console.print(f"    ║  [bold white]LAMBDA FUNCTIONS:[/bold white] {len(resources['lambda'])} functions                        ║")
    
    # DynamoDB
    if resources['dynamodb']:
        console.print(f"    ║                                                                   ║")
        console.print(f"    ║  [bold white]DYNAMODB TABLES:[/bold white] {len(resources['dynamodb'])} tables                            ║")
    
    if not any(resources.values()):
        console.print("    ║              [bold green]>>> NO ACTIVE RESOURCES <<<[/bold green]                    ║")
    
    console.print("    ╚═══════════════════════════════════════════════════════════════════╝")
    console.print()
    
    # Service Costs & Free Tier Status
    console.print("    ╔═══════════════════════════════════════════════════════════════════╗")
    console.print("    ║         [bold magenta]📊 SERVICE COSTS & FREE TIER STATUS 📊[/bold magenta]             ║")
    console.print("    ╠═══════════════════════════════════════════════════════════════════╣")
    
    if service_costs:
        sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
        
        for service, cost in sorted_services[:10]:
            if cost > 0.01:
                # Check if service has free tier
                free_tier_info = FREE_TIER_LIMITS.get(service, {})
                short_name = free_tier_info.get('name', service[:20])
                
                # Determine status
                if cost > 1.0:
                    status = "[bold red]EXCEEDING[/bold red]"
                elif cost > 0.10:
                    status = "[yellow]CAUTION[/yellow]"
                else:
                    status = "[green]OK[/green]"
                
                console.print(f"    ║ {short_name[:25]:25} │ ${cost:>7.2f} │ {status:11} ║")
                
                if free_tier_info:
                    console.print(f"    ║   [dim]{free_tier_info['description'][:50]:50}[/dim]  ║")
    else:
        console.print("    ║               [dim]No charges detected this month[/dim]               ║")
    
    console.print("    ╚═══════════════════════════════════════════════════════════════════╝")
    console.print()
    
    # Recommendations
    console.print("    ╔═══════════════════════════════════════════════════════════════════╗")
    console.print("    ║                  [bold green]💡 RECOMMENDATIONS 💡[/bold green]                       ║")
    console.print("    ╠═══════════════════════════════════════════════════════════════════╣")
    
    recommendations = []
    
    # Check for non-free tier EC2
    non_free_ec2 = [ec2 for ec2 in resources['ec2'] if not ec2['free_tier']]
    if non_free_ec2:
        recommendations.append("⚠ You have non-free tier EC2 instances running!")
        recommendations.append(f"  Consider switching to t2.micro or t3.micro")
    
    # Check for RDS
    if resources['rds']:
        recommendations.append("⚠ RDS can be expensive! Monitor usage carefully")
    
    # Check if monthly cost > $5
    if projected > 5:
        recommendations.append("⚠ Projected cost exceeds typical free tier usage")
        recommendations.append("  Review and terminate unused resources")
    
    if not recommendations:
        recommendations.append("✓ All systems optimal! Continue monitoring.")
    
    for rec in recommendations:
        console.print(f"    ║ {rec[:65]:65} ║")
    
    console.print("    ╚═══════════════════════════════════════════════════════════════════╝")
    console.print()
    
    # Footer
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    console.print(f"    [dim]>>> LAST UPDATE: {timestamp}[/dim]")
    console.print(f"    [dim]>>> MONITORING ALL AWS SERVICES | FREE TIER TRACKING ACTIVE[/dim]")
    console.print()

if __name__ == "__main__":
    show_retro_dashboard()