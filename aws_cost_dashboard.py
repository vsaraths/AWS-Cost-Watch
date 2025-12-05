import boto3
from datetime import datetime, timedelta, timezone
from rich.console import Console
from rich.table import Table

# Initialize AWS Cost Explorer client
client = boto3.client('ce', region_name='us-east-1')

def get_total_cost():
    """Get yesterday's AWS cost"""
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=1)).strftime('%Y-%m-%d')  # yesterday
    end = today.strftime('%Y-%m-%d')                          # today
    
    try:
        response = client.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )
        
        if response['ResultsByTime']:
            return float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
        return 0.0
    except Exception as e:
        print(f"Error fetching cost data: {e}")
        return None

def get_monthly_cost():
    """Get current month's cost so far"""
    today = datetime.now(timezone.utc).date()
    start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    
    try:
        response = client.get_cost_and_usage(
            TimePeriod={'Start': start_of_month, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost']
        )
        
        if response['ResultsByTime']:
            return float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
        return 0.0
    except Exception as e:
        print(f"Error fetching monthly cost: {e}")
        return None

def get_cost_by_service():
    """Get yesterday's cost breakdown by service"""
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    
    try:
        response = client.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'SERVICE', 'Key': 'SERVICE'}]
        )
        
        services = []
        if response['ResultsByTime']:
            for group in response['ResultsByTime'][0]['Groups']:
                service_name = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                if cost > 0.01:  # Only show services with cost > $0.01
                    services.append((service_name, cost))
        
        # Sort by cost (highest first)
        services.sort(key=lambda x: x[1], reverse=True)
        return services
    except Exception as e:
        print(f"Error fetching service costs: {e}")
        return []

def show_dashboard():
    console = Console()
    
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]       AWS COST DASHBOARD[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    # Get costs
    yesterday_cost = get_total_cost()
    monthly_cost = get_monthly_cost()
    services = get_cost_by_service()
    
    # Display yesterday's cost
    if yesterday_cost is not None:
        console.print(f"[bold green]💰 Yesterday's Cost: ${yesterday_cost:.2f}[/bold green]")
    
    # Display month-to-date cost
    if monthly_cost is not None:
        console.print(f"[bold yellow]📊 Month-to-Date Cost: ${monthly_cost:.2f}[/bold yellow]\n")
    
    # Display cost by service
    if services:
        table = Table(title="Yesterday's Top Services", show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan", width=40)
        table.add_column("Cost", justify="right", style="green")
        table.add_column("% of Total", justify="right", style="yellow")
        
        total = sum(cost for _, cost in services)
        
        for service, cost in services[:10]:  # Show top 10
            percentage = (cost / total * 100) if total > 0 else 0
            table.add_row(service, f"${cost:.2f}", f"{percentage:.1f}%")
        
        console.print(table)
    
    console.print(f"\n[dim]Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}[/dim]\n")

if __name__ == "__main__":
    show_dashboard()
