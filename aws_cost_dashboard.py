import boto3
import time
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import box
from botocore.exceptions import ClientError

class RealTimeAWSCostDashboard:
    def __init__(self):
        self.console = Console()
        self.console.clear()
        
        # Initialize all AWS clients
        self.init_clients()
        
        # Data storage
        self.data = {
            'ec2': {'instances': [], 'summary': {}},
            's3': {'buckets': [], 'summary': {}},
            'rds': {'instances': [], 'summary': {}},
            'lambda': {'functions': [], 'summary': {}},
            'cloudwatch': {'alarms': [], 'summary': {}},
            'regions': []
        }
        
        # Track refresh times
        self.last_refresh = None
        self.scan_count = 0
        
        # Show initialization
        self.show_init()
    
    def init_clients(self):
        """Initialize all AWS clients"""
        self.console.print("[bold blue]Initializing AWS Clients...[/bold blue]")
        
        # Test credentials
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            self.account_id = identity['Account']
            self.account_arn = identity['Arn']
            self.console.print(f"[green]✓ Authenticated as: {identity['Arn']}[/green]")
        except Exception as e:
            self.console.print(f"[red]✗ Authentication failed: {e}[/red]")
            raise
        
        # Initialize service clients
        try:
            # EC2 client for region discovery
            self.ec2_client = boto3.client('ec2', region_name='us-east-1')
            
            # Get all regions
            response = self.ec2_client.describe_regions()
            self.all_regions = [r['RegionName'] for r in response['Regions']]
            self.console.print(f"[green]✓ Found {len(self.all_regions)} AWS regions[/green]")
            
            # Test a few regions for accessibility
            self.enabled_regions = []
            test_regions = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'eu-west-1']
            
            for region in test_regions:
                try:
                    ec2_test = boto3.client('ec2', region_name=region)
                    ec2_test.describe_instances(MaxResults=1)
                    self.enabled_regions.append(region)
                    self.console.print(f"[dim]  ✓ {region} accessible[/dim]")
                except:
                    pass
            
            if not self.enabled_regions:
                self.enabled_regions = ['us-east-1']
            
            self.console.print(f"[green]✓ Using {len(self.enabled_regions)} regions for scanning[/green]")
            
        except Exception as e:
            self.console.print(f"[yellow]⚠ Region discovery limited: {e}[/yellow]")
            self.enabled_regions = ['us-east-1']
    
    def show_init(self):
        """Show initialization sequence"""
        self.console.print("\n[bold green]AWS COSTWATCH - REAL-TIME DASHBOARD[/bold green]")
        self.console.print("[dim]Loading real-time data from AWS...[/dim]\n")
        
        # Initial scan
        self.scan_all_resources()
        self.last_refresh = datetime.now(timezone.utc)
        
        self.console.print(f"[green]✓ Initial scan complete: Found {self.get_total_resources()} resources[/green]")
        time.sleep(2)
    
    def get_ec2_instances(self, region):
        """Get REAL EC2 instances from AWS"""
        instances = []
        try:
            ec2 = boto3.client('ec2', region_name=region)
            response = ec2.describe_instances()
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    # Get instance name
                    name = 'No-Name'
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                            break
                    
                    # Calculate uptime
                    launch_time = instance.get('LaunchTime', datetime.now(timezone.utc))
                    uptime_hours = (datetime.now(timezone.utc) - launch_time).total_seconds() / 3600
                    uptime_days = uptime_hours / 24
                    
                    # Determine if free tier eligible
                    instance_type = instance['InstanceType']
                    free_tier = instance_type in ['t2.micro', 't3.micro', 't2.nano', 't3.nano']
                    
                    # Calculate estimated cost (real pricing)
                    hourly_rate = self.get_ec2_hourly_rate(instance_type)
                    total_cost = hourly_rate * uptime_hours
                    monthly_cost = hourly_rate * 24 * 30
                    
                    instances.append({
                        'id': instance['InstanceId'],
                        'name': name[:25],
                        'type': instance_type,
                        'state': instance['State']['Name'],
                        'region': region,
                        'launch_time': launch_time,
                        'uptime_hours': uptime_hours,
                        'uptime_days': uptime_days,
                        'hourly_rate': hourly_rate,
                        'total_cost': total_cost,
                        'monthly_cost': monthly_cost,
                        'free_tier': free_tier,
                        'vpc_id': instance.get('VpcId', 'N/A'),
                        'subnet_id': instance.get('SubnetId', 'N/A'),
                        'public_ip': instance.get('PublicIpAddress', 'None'),
                        'private_ip': instance.get('PrivateIpAddress', 'None')
                    })
            
            return instances
            
        except Exception as e:
            self.console.print(f"[yellow]EC2 Error in {region}: {e}[/yellow]")
            return []
    
    def get_s3_buckets(self):
        """Get REAL S3 buckets from AWS"""
        buckets = []
        try:
            s3 = boto3.client('s3')
            response = s3.list_buckets()
            
            for bucket in response['Buckets']:
                try:
                    # Get bucket location
                    location = s3.get_bucket_location(Bucket=bucket['Name'])
                    region = location.get('LocationConstraint')
                    if region is None or region == '':
                        region = 'us-east-1'
                    
                    # Try to get bucket size (simplified - real implementation would use CloudWatch)
                    bucket_age = (datetime.now(timezone.utc) - bucket['CreationDate']).total_seconds() / 86400
                    
                    # Estimate cost based on typical usage
                    estimated_monthly_cost = 0.023 * 10  # Assume 10GB at $0.023/GB
                    
                    buckets.append({
                        'name': bucket['Name'],
                        'region': region,
                        'created': bucket['CreationDate'].strftime('%Y-%m-%d'),
                        'age_days': int(bucket_age),
                        'estimated_monthly': estimated_monthly_cost
                    })
                    
                except Exception as e:
                    continue  # Skip buckets we can't access
            
            return buckets
            
        except Exception as e:
            self.console.print(f"[yellow]S3 Error: {e}[/yellow]")
            return []
    
    def get_rds_instances(self, region):
        """Get REAL RDS instances from AWS"""
        instances = []
        try:
            rds = boto3.client('rds', region_name=region)
            response = rds.describe_db_instances()
            
            for db in response['DBInstances']:
                # Calculate uptime
                create_time = db.get('InstanceCreateTime', datetime.now(timezone.utc))
                uptime_hours = (datetime.now(timezone.utc) - create_time).total_seconds() / 3600
                
                # Check if free tier
                db_class = db['DBInstanceClass']
                free_tier = db_class in ['db.t2.micro', 'db.t3.micro']
                
                # Get estimated cost
                hourly_rate = self.get_rds_hourly_rate(db_class)
                monthly_cost = hourly_rate * 24 * 30
                total_cost = hourly_rate * uptime_hours
                
                instances.append({
                    'id': db['DBInstanceIdentifier'],
                    'engine': db['Engine'],
                    'class': db_class,
                    'status': db['DBInstanceStatus'],
                    'region': region,
                    'storage': db.get('AllocatedStorage', 0),
                    'multi_az': db.get('MultiAZ', False),
                    'create_time': create_time,
                    'uptime_hours': uptime_hours,
                    'hourly_rate': hourly_rate,
                    'monthly_cost': monthly_cost,
                    'total_cost': total_cost,
                    'free_tier': free_tier
                })
            
            return instances
            
        except Exception as e:
            # RDS might not be available in all regions or permissions might be limited
            return []
    
    def get_lambda_functions(self, region):
        """Get REAL Lambda functions from AWS"""
        functions = []
        try:
            lambda_client = boto3.client('lambda', region_name=region)
            response = lambda_client.list_functions()
            
            for func in response['Functions']:
                # Estimate cost (simplified)
                estimated_monthly = 0.0000002 * 100000  # Assume 100K invocations
                
                functions.append({
                    'name': func['FunctionName'],
                    'runtime': func['Runtime'],
                    'memory': func['MemorySize'],
                    'region': region,
                    'last_modified': func['LastModified'],
                    'code_size_mb': func['CodeSize'] / (1024*1024),
                    'estimated_monthly': estimated_monthly
                })
            
            return functions
            
        except Exception as e:
            return []
    
    def get_cloudwatch_alarms(self, region):
        """Get REAL CloudWatch alarms from AWS"""
        alarms = []
        try:
            cloudwatch = boto3.client('cloudwatch', region_name=region)
            response = cloudwatch.describe_alarms()
            
            for alarm in response.get('MetricAlarms', []):
                alarms.append({
                    'name': alarm['AlarmName'],
                    'state': alarm['StateValue'],
                    'metric': alarm.get('MetricName', 'Unknown'),
                    'region': region
                })
            
            return alarms
            
        except Exception as e:
            return []
    
    def get_ec2_hourly_rate(self, instance_type):
        """Get REAL EC2 pricing (simplified)"""
        # Real AWS pricing for common instance types
        pricing = {
            't2.nano': 0.0058, 't3.nano': 0.0052,
            't2.micro': 0.0116, 't3.micro': 0.0104,
            't2.small': 0.023, 't3.small': 0.0208,
            't2.medium': 0.0464, 't3.medium': 0.0416,
            'm5.large': 0.096, 'm5.xlarge': 0.192,
            'c5.large': 0.085, 'c5.xlarge': 0.170,
            'r5.large': 0.126, 'r5.xlarge': 0.252,
            'i3.large': 0.156, 'i3.xlarge': 0.312
        }
        return pricing.get(instance_type, 0.05)  # Default if not found
    
    def get_rds_hourly_rate(self, db_class):
        """Get REAL RDS pricing (simplified)"""
        pricing = {
            'db.t2.micro': 0.017, 'db.t3.micro': 0.016,
            'db.t2.small': 0.034, 'db.t3.small': 0.032,
            'db.t2.medium': 0.068, 'db.t3.medium': 0.064,
            'db.m5.large': 0.171, 'db.m5.xlarge': 0.342,
            'db.r5.large': 0.228, 'db.r5.xlarge': 0.456
        }
        return pricing.get(db_class, 0.045)  # Default
    
    def scan_all_resources(self):
        """Scan ALL AWS resources in REAL-TIME"""
        self.scan_count += 1
        start_time = time.time()
        
        # Reset data
        self.data = {
            'ec2': {'instances': [], 'summary': {}},
            's3': {'buckets': [], 'summary': {}},
            'rds': {'instances': [], 'summary': {}},
            'lambda': {'functions': [], 'summary': {}},
            'cloudwatch': {'alarms': [], 'summary': {}},
            'regions': self.enabled_regions
        }
        
        # Scan S3 (global)
        self.console.print(f"[dim]Scan #{self.scan_count}: Fetching S3 buckets...[/dim]", end="")
        self.data['s3']['buckets'] = self.get_s3_buckets()
        self.console.print(f" [green]{len(self.data['s3']['buckets'])} found[/green]")
        
        # Scan each region
        for region in self.enabled_regions:
            self.console.print(f"[dim]  Scanning {region}...[/dim]")
            
            # EC2
            ec2_instances = self.get_ec2_instances(region)
            self.data['ec2']['instances'].extend(ec2_instances)
            
            # RDS
            rds_instances = self.get_rds_instances(region)
            self.data['rds']['instances'].extend(rds_instances)
            
            # Lambda
            lambda_funcs = self.get_lambda_functions(region)
            self.data['lambda']['functions'].extend(lambda_funcs)
            
            # CloudWatch
            cw_alarms = self.get_cloudwatch_alarms(region)
            self.data['cloudwatch']['alarms'].extend(cw_alarms)
        
        # Calculate summaries
        self.calculate_summaries()
        
        scan_time = time.time() - start_time
        self.last_refresh = datetime.now(timezone.utc)
        
        self.console.print(f"[green]✓ Scan completed in {scan_time:.1f}s[/green]")
    
    def calculate_summaries(self):
        """Calculate real-time summaries"""
        # EC2 Summary
        ec2_instances = self.data['ec2']['instances']
        running_ec2 = [i for i in ec2_instances if i['state'] == 'running']
        stopped_ec2 = [i for i in ec2_instances if i['state'] != 'running']
        
        self.data['ec2']['summary'] = {
            'total': len(ec2_instances),
            'running': len(running_ec2),
            'stopped': len(stopped_ec2),
            'free_tier': sum(1 for i in ec2_instances if i.get('free_tier', False)),
            'hourly_cost': sum(i['hourly_rate'] for i in running_ec2),
            'monthly_cost': sum(i['monthly_cost'] for i in running_ec2),
            'total_cost': sum(i['total_cost'] for i in ec2_instances)
        }
        
        # S3 Summary
        s3_buckets = self.data['s3']['buckets']
        self.data['s3']['summary'] = {
            'total': len(s3_buckets),
            'estimated_monthly': sum(b.get('estimated_monthly', 0) for b in s3_buckets)
        }
        
        # RDS Summary
        rds_instances = self.data['rds']['instances']
        running_rds = [i for i in rds_instances if i['status'] == 'available']
        
        self.data['rds']['summary'] = {
            'total': len(rds_instances),
            'running': len(running_rds),
            'free_tier': sum(1 for i in rds_instances if i.get('free_tier', False)),
            'monthly_cost': sum(i['monthly_cost'] for i in running_rds),
            'total_cost': sum(i['total_cost'] for i in rds_instances)
        }
        
        # Lambda Summary
        lambda_funcs = self.data['lambda']['functions']
        self.data['lambda']['summary'] = {
            'total': len(lambda_funcs),
            'estimated_monthly': sum(f.get('estimated_monthly', 0) for f in lambda_funcs)
        }
        
        # CloudWatch Summary
        cw_alarms = self.data['cloudwatch']['alarms']
        alarm_states = {}
        for alarm in cw_alarms:
            state = alarm['state']
            alarm_states[state] = alarm_states.get(state, 0) + 1
        
        self.data['cloudwatch']['summary'] = {
            'total': len(cw_alarms),
            'states': alarm_states
        }
    
    def get_total_resources(self):
        """Get total number of resources"""
        return (len(self.data['ec2']['instances']) + 
                len(self.data['s3']['buckets']) + 
                len(self.data['rds']['instances']) + 
                len(self.data['lambda']['functions']))
    
    def get_total_monthly_cost(self):
        """Get total estimated monthly cost"""
        return (self.data['ec2']['summary']['monthly_cost'] + 
                self.data['s3']['summary']['estimated_monthly'] + 
                self.data['rds']['summary']['monthly_cost'] + 
                self.data['lambda']['summary']['estimated_monthly'])
    
    def create_header(self):
        """Create dashboard header"""
        header = """
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║                  A W S   C O S T W A T C H                           ║
║              [ REAL-TIME Resource Monitor v2.0 ]                      ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
"""
        return Panel(Align.center(Text(header, style="bold green")), border_style="green")
    
    def create_cost_summary_panel(self):
        """Create REAL cost summary panel"""
        total_monthly = self.get_total_monthly_cost()
        ec2_summary = self.data['ec2']['summary']
        rds_summary = self.data['rds']['summary']
        
        table = Table(box=box.ROUNDED, expand=True, show_header=False)
        table.add_column("Metric", style="dim", width=20)
        table.add_column("Value", justify="right", style="bold")
        
        # Current rates
        table.add_row("Current Hourly", f"${ec2_summary['hourly_cost']:.3f}/hr")
        table.add_row("Projected Daily", f"${ec2_summary['hourly_cost'] * 24:.2f}/day")
        table.add_row("Projected Monthly", f"[bold red]${total_monthly:.2f}/month[/]")
        table.add_row("", "")
        
        # Cumulative costs
        table.add_row("EC2 Lifetime", f"${ec2_summary['total_cost']:.2f}")
        table.add_row("RDS Lifetime", f"${rds_summary['total_cost']:.2f}")
        table.add_row("", "")
        
        # Free tier usage
        free_tier_hours = sum(i['uptime_hours'] for i in self.data['ec2']['instances'] 
                             if i.get('free_tier', False))
        free_tier_percent = min((free_tier_hours / 750) * 100, 100)
        
        if free_tier_percent > 0:
            color = "green" if free_tier_percent < 80 else "yellow" if free_tier_percent < 95 else "red"
            table.add_row("Free Tier Used", f"[{color}]{free_tier_percent:.1f}%[/]")
        
        return Panel(table, title="💰 REAL-TIME COST ESTIMATES", border_style="yellow")
    
    def create_resources_panel(self):
        """Create REAL resources panel"""
        ec2 = self.data['ec2']['summary']
        s3 = self.data['s3']['summary']
        rds = self.data['rds']['summary']
        lamb = self.data['lambda']['summary']
        cw = self.data['cloudwatch']['summary']
        
        table = Table(box=box.SIMPLE, expand=True, show_header=False)
        table.add_column("Service", style="bold", width=12)
        table.add_column("Active", justify="right", width=8)
        table.add_column("Status", style="cyan", width=15)
        
        table.add_row("🖥️ EC2", str(ec2['running']), f"{ec2['total']} total")
        table.add_row("🗄️ RDS", str(rds['running']), f"{rds['total']} total")
        table.add_row("📦 S3", str(s3['total']), "All regions")
        table.add_row("λ Lambda", str(lamb['total']), "Functions")
        table.add_row("📊 CloudWatch", str(cw['total']), "Alarms")
        table.add_row("", "", "")
        
        # Regions
        table.add_row("🌍 Regions", str(len(self.data['regions'])), "Active")
        
        # Total resources
        total = self.get_total_resources()
        table.add_row("[bold]TOTAL[/]", f"[bold]{total}[/]", "Resources")
        
        return Panel(table, title="📊 REAL-TIME RESOURCES", border_style="cyan")
    
    def create_ec2_table(self):
        """Create REAL EC2 instances table"""
        instances = self.data['ec2']['instances']
        
        if not instances:
            return Panel("No EC2 instances found", title="🖥️ EC2 INSTANCES", border_style="white")
        
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Name", style="bold", width=15)
        table.add_column("Type", width=10)
        table.add_column("State", justify="center", width=8)
        table.add_column("Uptime", width=10)
        table.add_column("Cost", justify="right", width=12)
        
        # Show running instances first
        running = [i for i in instances if i['state'] == 'running']
        other = [i for i in instances if i['state'] != 'running']
        
        for instance in (running + other)[:6]:  # Show max 6
            # State color
            if instance['state'] == 'running':
                state_color = "green"
                state_icon = "▶"
            else:
                state_color = "yellow"
                state_icon = "⏸"
            
            # Uptime format
            if instance['uptime_days'] > 1:
                uptime = f"{instance['uptime_days']:.0f}d"
            else:
                uptime = f"{instance['uptime_hours']:.0f}h"
            
            # Free tier indicator
            name = instance['name']
            if instance.get('free_tier', False):
                name = f"🎁 {name}"
            
            table.add_row(
                name,
                instance['type'],
                f"[{state_color}]{state_icon} {instance['state'][:3]}[/]",
                uptime,
                f"${instance['total_cost']:.2f}"
            )
        
        return Panel(table, title="🖥️ REAL EC2 INSTANCES", border_style="white")
    
    def create_s3_table(self):
        """Create REAL S3 buckets table"""
        buckets = self.data['s3']['buckets']
        
        if not buckets:
            return Panel("No S3 buckets found", title="📦 S3 BUCKETS", border_style="blue")
        
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Bucket", style="bold", width=20)
        table.add_column("Region", width=10)
        table.add_column("Age", justify="right", width=8)
        table.add_column("Cost Est", justify="right", width=12)
        
        for bucket in buckets[:5]:  # Show max 5
            table.add_row(
                bucket['name'][:20],
                bucket['region'],
                f"{bucket['age_days']}d",
                f"${bucket.get('estimated_monthly', 0):.2f}"
            )
        
        return Panel(table, title="📦 REAL S3 BUCKETS", border_style="blue")
    
    def create_status_panel(self):
        """Create REAL status panel"""
        now = datetime.now(timezone.utc)
        
        if self.last_refresh:
            refresh_ago = (now - self.last_refresh).total_seconds()
            if refresh_ago < 60:
                refresh_text = f"[green]{int(refresh_ago)}s ago[/]"
            else:
                refresh_text = f"[yellow]{int(refresh_ago/60)}m ago[/]"
        else:
            refresh_text = "[red]Never[/]"
        
        status = Text()
        status.append(f"[dim]Account:[/] [white]{self.account_id}[/]\n")
        status.append(f"[dim]Last Scan:[/] {refresh_text}\n")
        status.append(f"[dim]Scan Count:[/] [cyan]{self.scan_count}[/]\n")
        status.append(f"[dim]Active Regions:[/] {len(self.data['regions'])}\n")
        
        # Alerts
        total_cost = self.get_total_monthly_cost()
        if total_cost > 100:
            status.append(f"[dim]Status:[/] [red blink]HIGH COST (${total_cost:.0f}/mo)[/]")
        elif total_cost > 50:
            status.append(f"[dim]Status:[/] [yellow]MEDIUM COST (${total_cost:.0f}/mo)[/]")
        else:
            status.append(f"[dim]Status:[/] [green]NORMAL (${total_cost:.0f}/mo)[/]")
        
        return Panel(status, title="⚡ REAL-TIME STATUS", border_style="green")
    
    def create_layout(self):
        """Create dashboard layout"""
        layout = Layout(name="root")
        
        # Header
        layout.split(
            Layout(name="header", size=13),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Main content
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # Left panels
        layout["left"].split(
            Layout(name="costs", ratio=1),
            Layout(name="resources", ratio=1)
        )
        
        # Right panels
        layout["right"].split(
            Layout(name="ec2", ratio=1),
            Layout(name="s3", ratio=1),
            Layout(name="status", size=8)
        )
        
        return layout
    
    def update_dashboard(self, layout):
        """Update dashboard with REAL data"""
        # Update data
        self.scan_all_resources()
        
        # Update panels
        layout["header"].update(self.create_header())
        layout["costs"].update(self.create_cost_summary_panel())
        layout["resources"].update(self.create_resources_panel())
        layout["ec2"].update(self.create_ec2_table())
        layout["s3"].update(self.create_s3_table())
        layout["status"].update(self.create_status_panel())
        
        # Footer
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_resources = self.get_total_resources()
        total_monthly = self.get_total_monthly_cost()
        
        footer = f"🔄 Scan #{self.scan_count} | 📦 {total_resources} Resources | 💰 ${total_monthly:.2f}/mo | ⏱️ {now} | Ctrl+C to exit"
        layout["footer"].update(Panel(Align.center(footer), style="dim"))
    
    def run(self):
        """Run the REAL-TIME dashboard"""
        # Create layout
        layout = self.create_layout()
        
        # Initial update
        self.update_dashboard(layout)
        
        # Start live dashboard
        try:
            with Live(layout, refresh_per_second=1, screen=True) as live:
                while True:
                    self.update_dashboard(layout)
                    time.sleep(60)  # Update every 60 seconds
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Dashboard stopped[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")

def main():
    """Main entry point"""
    try:
        dashboard = RealTimeAWSCostDashboard()
        dashboard.run()
    except KeyboardInterrupt:
        print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        print(f"\n[red]Fatal error: {e}[/red]")

if __name__ == "__main__":
    main()
