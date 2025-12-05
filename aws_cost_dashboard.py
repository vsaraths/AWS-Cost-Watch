import boto3
from rich.console import Console
from rich.table import Table
from datetime import datetime, timedelta

# Initialize AWS Cost Explorer client
client = boto3.client('ce')

def get_service_costs():
    today = datetime.utcnow().date()
    start = (today - timedelta(days=1)).strftime('%Y-%m-%d')  # yesterday
    end = today.strftime('%Y-%m-%d')                          # today

    response = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='DAILY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )
    return response['ResultsByTime'][0]['Groups']

def get_total_cost():
    today = datetime.utcnow().date()
    start = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')

    response = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='DAILY',
        Metrics=['UnblendedCost']
    )
    return response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']

def show_dashboard():
    console = Console()
    table = Table(title="AWS Cost Dashboard")

    table.add_column("Service", style="cyan")
    table.add_column("Cost (USD)", style="green")

    service_costs = get_service_costs()
    total = 0.0

    for group in service_costs:
        service = group['Keys'][0]
        amount = float(group['Metrics']['UnblendedCost']['Amount'])
        table.add_row(service, f"${amount:.4f}")
        total += amount

    # Add total row
    table.add_row("TOTAL", f"${total:.4f}")

    console.print(table)

if __name__ == "__main__":
    show_dashboard()
