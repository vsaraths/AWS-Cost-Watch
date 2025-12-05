import boto3
from rich.console import Console
from rich.table import Table
from datetime import datetime

# Initialize AWS Cost Explorer client
client = boto3.client('ce')

def get_service_costs():
    today = datetime.utcnow().date()
    start = today.strftime('%Y-%m-%d')
    end = (today + timedelta(days=1)).strftime('%Y-%m-%d')  # next day

    response = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='DAILY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )
    return response['ResultsByTime'][0]['Groups']

def show_dashboard():
    console = Console()
    table = Table(title="AWS Cost Dashboard")

    table.add_column("Service", style="cyan")
    table.add_column("Usage (Today)", style="magenta")
    table.add_column("Cost (USD)", style="green")

    # Demo rows (replace later with per-service queries)
    table.add_row("EC2", "3 hours", "$0.0348")
    table.add_row("S3", "2 GB stored", "$0.05")
    table.add_row("Lambda", "1200 requests", "$0.0024")

    total_cost = get_total_cost()
    table.add_row("TOTAL", "-", f"${total_cost}")

    console.print(table)

if __name__ == "__main__":
    show_dashboard()
