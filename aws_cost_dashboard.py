import boto3
from datetime import datetime, timedelta, timezone
from rich.console import Console

# Initialize AWS Cost Explorer client
client = boto3.client('ce')

def get_total_cost():
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=1)).strftime('%Y-%m-%d')  # yesterday
    end = today.strftime('%Y-%m-%d')                          # today

    response = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='DAILY',
        Metrics=['UnblendedCost']
    )
    return response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']

def show_total_cost():
    console = Console()
    total_cost = get_total_cost()
    console.print(f"[bold green]Current AWS Account Cost (yesterday): ${total_cost}[/bold green]")

if __name__ == "__main__":
    show_total_cost()
