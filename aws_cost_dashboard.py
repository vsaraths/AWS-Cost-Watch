import boto3
from datetime import datetime, timedelta, timezone
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console
from rich.text import Text
from rich.align import Align
from rich.style import Style
import time
import math

# --- CONFIGURATION ---
REFRESH_RATE = 60  # Update every 1 minute
CURRENT_REGION_LIMIT = None # Set to ['us-east-1', 'us-west-2'] to limit scope, or None for ALL regions.

# --- "LIVE" PRICING DATABASE (Estimates) ---
# AWS Billing API has a 24h delay. We use this for Real-Time "Since Midnight" calculations.
# Add your most used instance types here.
PRICING_DB = {
    # EC2 (On-Demand / Hour)
    't2.micro': 0.0116, 't3.micro': 0.0104,
    't2.small': 0.0230, 't3.small': 0.0208,
    't2.medium': 0.0464, 't3.medium': 0.0416,
    'm5.large': 0.0960, 'c5.large': 0.0850,
    # RDS
    'db.t2.micro': 0.017, 'db.t3.micro': 0.017,
    'db.m5.large': 0.138,
}

# --- GLOBAL VARS ---
ce_client = boto3.client('ce', region_name='us-east-1')
session_start_time = datetime.now(timezone.utc)

def get_enabled_regions():
    if CURRENT_REGION_LIMIT: return CURRENT_REGION_LIMIT
    try:
        ec2 = boto3.client('ec2', region_name='us-east-1')
        return [r['RegionName'] for r in ec2.describe_regions()['Regions']]
    except:
        return ['us-east-1']

def get_yesterday_cost():
    """Get the confirmed billing amount for Yesterday"""
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    try:
        data = ce_client.get_cost_and_usage(
            TimePeriod={'Start': yesterday.strftime('%Y-%m-%d'), 'End': today.strftime('%Y-%m-%d')},
            Granularity='DAILY', Metrics=['UnblendedCost']
        )
        return float(data['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
    except:
        return 0.0

def get_live_status():
    """
    Scans all regions for running resources.
    Calculates 'Today's Cost' using: (Hours since Midnight) * (Instance Price)
    """
    resources = []
    total_hourly_burn = 0.0
    today_estimated_cost = 0.0
    
    # Calculate hours elapsed since Midnight UTC
    now_utc = datetime.now(timezone.utc)
    midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    hours_since_midnight = (now_utc - midnight_utc).total_seconds() / 3600

    regions = get_enabled_regions()

    for region in regions:
        try:
            ec2 = boto3.client('ec2', region_name=region)
            
            # Scan EC2
            instances = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
            for r in instances['Reservations']:
                for i in r['Instances']:
                    name = next((t['Value'] for t in i.get('Tags', []) if t['Key'] == 'Name'), 'Unnamed')
                    itype = i['InstanceType']
                    price = PRICING_DB.get(itype, 0.0) # Default to 0 if unknown
                    
                    # Cost logic: Price * Hours active today
                    # (We assume it's been running all day for the "Today" estimate to be safe, 
                    # or you could check LaunchTime for higher accuracy)
                    cost_today = price * hours_since_midnight
                    
                    resources.append({
                        'service': 'EC2',
                        'name': name,
                        'info': f"{itype} ({region})",
                        'price': price,
                        'cost_today': cost_today
                    })
                    total_hourly_burn += price
                    today_estimated_cost += cost_today

            # Scan RDS (Simplified for brevity)
            rds = boto3.client('rds', region_name=region)
            dbs = rds.describe_db_instances()
            for db in dbs['DBInstances']:
                dtype = db['DBInstanceClass']
                price = PRICING_DB.get(dtype, 0.0)
                cost_today = price * hours_since_midnight
                
                resources.append({
                    'service': 'RDS',
                    'name': db['DBInstanceIdentifier'],
                    'info': f"{dtype} ({region})",
                    'price': price,
                    'cost_today': cost_today
                })
                total_hourly_burn += price
                today_estimated_cost += cost_today

        except Exception:
            continue
            
    return resources, total_hourly_burn, today_estimated_cost

def make_layout():
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="inventory", ratio=3),
        Layout(name="analysis", ratio=2)
    )
    return layout

def generate_dashboard(yesterday_cost):
    layout = make_layout()
    
    # --- HEADER ---
    title = Text("AWS COSTWATCH: SENTINEL", style="bold white on #005f00")
    subtitle = Text(" Real-Time Instance Tracking & Daily Forecasting ", style="white on #005f00")
    layout["header"].update(Panel(Align.center(Text.assemble(title, subtitle)), style="#005f00"))

    # --- FETCH LIVE DATA ---
    resources, hourly_burn, today_est = get_live_status()
    
    # --- FORECAST CALCULATION ---
    # Forecast = (Cost So Far) + (Burn Rate * Hours Remaining in Day)
    now_utc = datetime.now(timezone.utc)
    hours_remaining = 24 - now_utc.hour
    forecast_today = today_est + (hourly_burn * hours_remaining)
    
    # Diff vs Yesterday
    diff = forecast_today - yesterday_cost
    diff_color = "red" if diff > 0 else "green"
    diff_symbol = "▲" if diff > 0 else "▼"

    # --- LEFT PANEL: INVENTORY ---
    inv_table = Table(expand=True, box=None, padding=(0,1))
    inv_table.add_column("Service", style="cyan")
    inv_table.add_column("Resource Name", style="bold white")
    inv_table.add_column("Type/Region", style="dim")
    inv_table.add_column("Cost Today", justify="right", style="yellow")
    
    for r in resources:
        inv_table.add_row(
            r['service'], 
            r['name'], 
            r['info'], 
            f"${r['cost_today']:.3f}"
        )
    
    if not resources:
        inv_table.add_row("-", "[dim]No active resources detected[/]", "-", "-")

    layout["inventory"].update(
        Panel(inv_table, title="[bold]LIVE RESOURCE TRACKER[/]", border_style="blue")
    )

    # --- RIGHT PANEL: ALERTS & FORECAST ---
    
    # 1. Today's Alert Box
    today_text = Text()
    today_text.append("Spent Since Midnight:\n", style="dim")
    today_text.append(f"${today_est:.3f}\n", style="bold yellow size(16)")
    today_text.append(f"Current Burn: ${hourly_burn:.3f}/hr", style="dim white")
    
    today_panel = Panel(Align.center(today_text), title="[bold yellow]⚠ TODAY'S BILL[/]", border_style="yellow")

    # 2. Forecast Box
    fc_text = Text()
    fc_text.append("Forecast (End of Day):\n", style="dim")
    fc_text.append(f"${forecast_today:.3f}\n", style="bold white size(16)")
    fc_text.append(f"Vs Yesterday (${yesterday_cost:.2f}):\n", style="dim")
    fc_text.append(f"{diff_symbol} ${abs(diff):.3f}", style=f"bold {diff_color}")
    
    fc_panel = Panel(Align.center(fc_text), title="[bold cyan]PREDICTION[/]", border_style="cyan")

    # 3. Session Timer
    elapsed = datetime.now(timezone.utc) - session_start_time
    # Simplified session cost based on current burn
    session_cost = hourly_burn * (elapsed.total_seconds() / 3600)
    
    alert_text = Text.from_markup(
        f"[bold]Monitor Active:[/bold] {str(elapsed).split('.')[0]}\n"
        f"[bold]Session Cost:[/bold] [red]${session_cost:.4f}[/]"
    )
    alert_panel = Panel(alert_text, title="SESSION ALERT", border_style="white")

    # Combine Right Panel
    analysis_layout = Layout()
    analysis_layout.split(
        Layout(today_panel, ratio=1),
        Layout(fc_panel, ratio=1),
        Layout(alert_panel, size=4)
    )
    layout["analysis"].update(analysis_layout)

    # --- FOOTER ---
    layout["footer"].update(Panel(f"Scanning All Regions | Last Update: {datetime.now().strftime('%H:%M:%S')} | Prices are estimates", style="dim"))

    return layout

if __name__ == "__main__":
    console = Console()
    console.clear()
    
    # Initial fetch of yesterday's historical data (only needs to happen once)
    console.print("[yellow]Fetching historical data...[/]")
    yesterday_cost = get_yesterday_cost()
    
    with Live(generate_dashboard(yesterday_cost), refresh_per_second=1, screen=True) as live:
        while True:
            live.update(generate_dashboard(yesterday_cost))
            time.sleep(REFRESH_RATE)