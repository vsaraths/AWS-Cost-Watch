#!/usr/bin/env python3
# ===========================================================
#  Advanced AWS CostWatch v8 (DevOps + FinOps Edition)
#  Author: Sarath V
#  Mode  : Production-Optimized (Classic Green Theme)
# ===========================================================

import boto3
import time
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich import box
from concurrent.futures import ThreadPoolExecutor

# -----------------------------------------------------------
#  Logging setup
# -----------------------------------------------------------
LOG_FILE = "aws_costwatch.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.info("=== Starting AWS CostWatch v8 ===")

# -----------------------------------------------------------
#  SQLite setup
# -----------------------------------------------------------
DB_FILE = "aws_costwatch.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    total_resources INTEGER,
    total_monthly REAL,
    north_south REAL,
    east_west REAL,
    zombies INTEGER,
    ephemerals INTEGER
);
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS ephemeral_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT,
    service TEXT,
    region TEXT,
    user TEXT,
    created TEXT,
    deleted TEXT,
    lifetime REAL
);
""")
conn.commit()

# -----------------------------------------------------------
#  Main Class
# -----------------------------------------------------------
class AdvancedAWSCostWatch:
    def __init__(self):
        self.console = Console()
        self.console.clear()
        self.account_id = None
        self.account_alias = None
        self.enabled_regions = []
        self.refresh_interval = 600  # seconds (10 min)
        self.scan_count = 0
        self.last_refresh = None
        self.data = {}
        self.now_utc = lambda: datetime.now(timezone.utc)
        self.init_banner()
        self.init_clients()
        self.scan_all_resources()  # immediate scan
        self.run_dashboard()

    # -------------------------------------------------------
    #  Banner
    # -------------------------------------------------------
    def init_banner(self):
        banner = """
╔══════════════════════════════════════════════════════════╗
║     ADVANCED AWS COSTWATCH v8 (LIVE)                     ║
║     DevOps + FinOps Real-Time Dashboard                  ║
╚══════════════════════════════════════════════════════════╝
"""
        self.console.print(Align.center(Text(banner, style="bold green")))
        self.console.print(
            "[dim]Initializing environment and AWS service clients...[/dim]\n"
        )

    # -------------------------------------------------------
    #  AWS Client Initialization
    # -------------------------------------------------------
    def init_clients(self):
        try:
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            self.account_id = identity["Account"]
            iam = boto3.client("iam")
            try:
                alias_resp = iam.list_account_aliases()
                self.account_alias = (
                    alias_resp["AccountAliases"][0]
                    if alias_resp["AccountAliases"]
                    else self.account_id
                )
            except Exception:
                self.account_alias = self.account_id
            self.console.print(
                f"[green]✓ Authenticated as {self.account_alias} ({self.account_id})[/green]"
            )
        except Exception as e:
            self.console.print(f"[red]✗ AWS Authentication failed: {e}[/red]")
            raise

        try:
            ec2 = boto3.client("ec2", region_name="us-east-1")
            regions = ec2.describe_regions()["Regions"]
            self.enabled_regions = [r["RegionName"] for r in regions]
            self.console.print(
                f"[green]✓ Loaded {len(self.enabled_regions)} AWS regions[/green]"
            )
        except Exception as e:
            self.enabled_regions = ["us-east-1"]
            self.console.print(
                f"[yellow]⚠ Region discovery limited: {e}[/yellow]"
            )

    # -------------------------------------------------------
    #  EC2 Instance Fetcher
    # -------------------------------------------------------
    def get_ec2_instances(self, region):
        instances = []
        try:
            ec2 = boto3.client("ec2", region_name=region)
            resp = ec2.describe_instances()
            for res in resp["Reservations"]:
                for i in res["Instances"]:
                    state = i["State"]["Name"]
                    itype = i["InstanceType"]
                    name = next(
                        (t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"),
                        i["InstanceId"],
                    )
                    launch = i["LaunchTime"]
                    uptime = (self.now_utc() - launch).total_seconds() / 3600
                    hourly = self.get_ec2_hourly_rate(itype)
                    total = hourly * uptime
                    monthly = hourly * 24 * 30
                    instances.append(
                        {
                            "id": i["InstanceId"],
                            "name": name,
                            "type": itype,
                            "state": state,
                            "region": region,
                            "hourly": hourly,
                            "monthly": monthly,
                            "total": total,
                        }
                    )
        except Exception as e:
            logging.warning(f"EC2 fetch error {region}: {e}")
        return instances

    # -------------------------------------------------------
    #  Simple EC2 price map
    # -------------------------------------------------------
    def get_ec2_hourly_rate(self, itype):
        p = {
            "t3.micro": 0.0104,
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            "m5.large": 0.096,
            "c5.large": 0.085,
        }
        return p.get(itype, 0.05)
    # -------------------------------------------------------
    #  RDS Instances
    # -------------------------------------------------------
    def get_rds_instances(self, region):
        items = []
        try:
            rds = boto3.client("rds", region_name=region)
            resp = rds.describe_db_instances()
            for db in resp["DBInstances"]:
                cls = db["DBInstanceClass"]
                status = db["DBInstanceStatus"]
                create_time = db["InstanceCreateTime"]
                uptime = (self.now_utc() - create_time).total_seconds() / 3600
                hourly = self.get_rds_hourly_rate(cls)
                monthly = hourly * 24 * 30
                total = hourly * uptime
                items.append(
                    {
                        "id": db["DBInstanceIdentifier"],
                        "class": cls,
                        "engine": db["Engine"],
                        "status": status,
                        "region": region,
                        "hourly": hourly,
                        "monthly": monthly,
                        "total": total,
                    }
                )
        except Exception as e:
            logging.warning(f"RDS fetch error {region}: {e}")
        return items

    def get_rds_hourly_rate(self, cls):
        p = {
            "db.t3.micro": 0.016,
            "db.t3.small": 0.032,
            "db.t3.medium": 0.064,
            "db.m5.large": 0.171,
        }
        return p.get(cls, 0.05)

    # -------------------------------------------------------
    #  S3 Buckets
    # -------------------------------------------------------
    def get_s3_buckets(self):
        items = []
        try:
            s3 = boto3.client("s3")
            resp = s3.list_buckets()
            for b in resp["Buckets"]:
                region = "us-east-1"
                try:
                    loc = s3.get_bucket_location(Bucket=b["Name"])
                    region = loc.get("LocationConstraint") or "us-east-1"
                except Exception:
                    pass
                age = (self.now_utc() - b["CreationDate"]).days
                est_cost = 0.023 * 10  # assume 10 GB
                items.append(
                    {
                        "name": b["Name"],
                        "region": region,
                        "age": age,
                        "monthly": est_cost,
                    }
                )
        except Exception as e:
            logging.warning(f"S3 fetch error: {e}")
        return items

    # -------------------------------------------------------
    #  Lambda Functions
    # -------------------------------------------------------
    def get_lambda_functions(self, region):
        items = []
        try:
            lam = boto3.client("lambda", region_name=region)
            resp = lam.list_functions()
            for fn in resp["Functions"]:
                est_month = 0.0000002 * 100000
                items.append(
                    {
                        "name": fn["FunctionName"],
                        "runtime": fn["Runtime"],
                        "region": region,
                        "size": fn["CodeSize"],
                        "monthly": est_month,
                    }
                )
        except Exception as e:
            logging.warning(f"Lambda fetch error {region}: {e}")
        return items

    # -------------------------------------------------------
    #  CloudTrail — ephemeral resource detection
    # -------------------------------------------------------
    def get_ephemeral_resources(self):
        events = []
        try:
            ct = boto3.client("cloudtrail")
            start = self.now_utc() - timedelta(minutes=10)
            resp = ct.lookup_events(StartTime=start, MaxResults=50)
            create_map = {}
            delete_map = {}
            for ev in resp.get("Events", []):
                ename = ev["EventName"]
                rid = ev.get("Resources", [{}])[0].get("ResourceName", "")
                if not rid:
                    continue
                if any(k in ename for k in ["RunInstances", "CreateFunction", "CreateBucket"]):
                    create_map[rid] = ev
                if any(k in ename for k in ["TerminateInstances", "DeleteFunction", "DeleteBucket"]):
                    delete_map[rid] = ev
            for rid in create_map:
                if rid in delete_map:
                    t1 = create_map[rid]["EventTime"]
                    t2 = delete_map[rid]["EventTime"]
                    life = (t2 - t1).total_seconds()
                    if life < 600:
                        events.append(
                            {
                                "resource_id": rid,
                                "service": "unknown",
                                "user": create_map[rid].get("Username", ""),
                                "created": t1,
                                "deleted": t2,
                                "lifetime": life,
                            }
                        )
                        cursor.execute(
                            "INSERT INTO ephemeral_events (resource_id,service,region,user,created,deleted,lifetime)"
                            " VALUES (?,?,?,?,?,?,?)",
                            (
                                rid,
                                "unknown",
                                "global",
                                create_map[rid].get("Username", ""),
                                t1.isoformat(),
                                t2.isoformat(),
                                life,
                            ),
                        )
            conn.commit()
        except Exception as e:
            logging.warning(f"CloudTrail ephemeral scan failed: {e}")
        return events

    # -------------------------------------------------------
    #  Cost Explorer & Budgets
    # -------------------------------------------------------
    def get_cost_explorer_data(self):
        data = {
            "total_this": 0.0,
            "total_last": 0.0,
            "services": {},
            "transfer_ns": 0.0,
            "transfer_ew": 0.0,
        }
        try:
            ce = boto3.client("ce")
            today = datetime.utcnow().date()
            start_this = today.replace(day=1)
            start_last = (start_this - timedelta(days=1)).replace(day=1)
            end_last = start_this - timedelta(days=1)
            this_p = {"Start": str(start_this), "End": str(today)}
            last_p = {"Start": str(start_last), "End": str(end_last)}
            for period, label in [(this_p, "total_this"), (last_p, "total_last")]:
                resp = ce.get_cost_and_usage(
                    TimePeriod=period,
                    Granularity="MONTHLY",
                    Metrics=["UnblendedCost"],
                    GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
                )
                amt = 0.0
                for r in resp["ResultsByTime"][0]["Groups"]:
                    service = r["Keys"][0]
                    val = float(r["Metrics"]["UnblendedCost"]["Amount"])
                    amt += val
                    if label == "total_this":
                        data["services"][service] = val
                data[label] = amt

            resp = ce.get_cost_and_usage(
                TimePeriod=this_p,
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
            )
            for g in resp["ResultsByTime"][0]["Groups"]:
                ut = g["Keys"][0]
                cost = float(g["Metrics"]["UnblendedCost"]["Amount"])
                if "DataTransfer" in ut or "Transfer" in ut:
                    if any(k in ut for k in ["Out", "Internet", "Regional"]):
                        data["transfer_ns"] += cost
                    else:
                        data["transfer_ew"] += cost
        except Exception as e:
            logging.warning(f"Cost Explorer error: {e}")
        return data

    def get_budget_status(self):
        budgets = []
        try:
            b = boto3.client("budgets")
            resp = b.describe_budgets(AccountId=self.account_id)
            for bud in resp.get("Budgets", []):
                name = bud["BudgetName"]
                limit = float(bud["BudgetLimit"]["Amount"])
                actual = bud.get("CalculatedSpend", {}).get("ActualSpend", {}).get("Amount", 0)
                actual = float(actual)
                perc = (actual / limit * 100) if limit else 0
                budgets.append(
                    {"name": name, "limit": limit, "actual": actual, "perc": perc}
                )
        except Exception as e:
            logging.warning(f"Budget fetch error: {e}")
        return budgets
    # -------------------------------------------------------
    #  ZOMBIE RESOURCE DETECTION
    # -------------------------------------------------------
    def detect_zombie_resources(self, ec2_list, ebs_list):
        zombies = []
        for i in ec2_list:
            if i["state"] != "running":
                zombies.append(i)
        for v in ebs_list:
            if not v.get("attachments"):
                zombies.append(v)
        return zombies

    # -------------------------------------------------------
    #  SCAN ALL REGIONS
    # -------------------------------------------------------
    def scan_all_resources(self):
        self.scan_count += 1
        start = time.time()
        self.console.print(f"[dim]🔍 Starting Scan #{self.scan_count}...[/dim]")
        ec2_all, rds_all, lam_all, s3_all = [], [], [], []
        eph_events = self.get_ephemeral_resources()
        try:
            with ThreadPoolExecutor(max_workers=10) as ex:
                futs = [ex.submit(self.get_ec2_instances, r) for r in self.enabled_regions]
                for f in futs:
                    ec2_all += f.result()
                futs = [ex.submit(self.get_rds_instances, r) for r in self.enabled_regions]
                for f in futs:
                    rds_all += f.result()
                futs = [ex.submit(self.get_lambda_functions, r) for r in self.enabled_regions]
                for f in futs:
                    lam_all += f.result()
            s3_all = self.get_s3_buckets()
        except Exception as e:
            logging.error(f"Scan failed: {e}")

        ebs_all = []
        try:
            for region in self.enabled_regions:
                ec2 = boto3.client("ec2", region_name=region)
                vols = ec2.describe_volumes()
                for v in vols["Volumes"]:
                    ebs_all.append(
                        {
                            "id": v["VolumeId"],
                            "region": region,
                            "size": v["Size"],
                            "attachments": v.get("Attachments", []),
                            "monthly": v["Size"] * 0.10,
                        }
                    )
        except Exception as e:
            logging.warning(f"EBS fetch issue: {e}")

        cost_data = self.get_cost_explorer_data()
        budgets = self.get_budget_status()
        zombies = self.detect_zombie_resources(ec2_all, ebs_all)

        total_month = (
            sum(i["monthly"] for i in ec2_all)
            + sum(i["monthly"] for i in rds_all)
            + sum(i["monthly"] for i in s3_all)
            + sum(i["monthly"] for i in lam_all)
            + sum(i["monthly"] for i in ebs_all)
        )

        cursor.execute(
            "INSERT INTO scans (timestamp,total_resources,total_monthly,north_south,east_west,zombies,ephemerals)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                datetime.utcnow().isoformat(),
                len(ec2_all) + len(rds_all) + len(s3_all) + len(lam_all),
                total_month,
                cost_data["transfer_ns"],
                cost_data["transfer_ew"],
                len(zombies),
                len(eph_events),
            ),
        )
        conn.commit()

        self.data = {
            "ec2": ec2_all,
            "rds": rds_all,
            "s3": s3_all,
            "lambda": lam_all,
            "ebs": ebs_all,
            "ephemeral": eph_events,
            "zombies": zombies,
            "cost": cost_data,
            "budgets": budgets,
        }
        self.last_refresh = datetime.now(timezone.utc)
        elapsed = time.time() - start
        self.console.print(f"[green]✓ Scan #{self.scan_count} completed in {elapsed:.1f}s[/green]")
        logging.info(f"Scan {self.scan_count} completed in {elapsed:.1f}s")

    # -------------------------------------------------------
    #  COST TREND CHART (ASCII)
    # -------------------------------------------------------
    def create_trend_panel(self):
        rows = cursor.execute(
            "SELECT timestamp,total_monthly FROM scans ORDER BY id DESC LIMIT 7"
        ).fetchall()
        if not rows:
            return Panel("No historical data", title="📈 COST TREND", border_style="green")
        max_cost = max(r[1] for r in rows)
        lines = []
        for r in reversed(rows):
            date = r[0].split("T")[0]
            val = r[1]
            bar = "■" * int((val / max_cost) * 40)
            lines.append(f"${val:6.2f} |{bar}")
        return Panel("\n".join(lines), title="📈 COST TREND (LAST 7 SCANS)", border_style="green")

    # -------------------------------------------------------
    #  COST SUMMARY PANEL
    # -------------------------------------------------------
    def create_cost_summary_panel(self):
        c = self.data["cost"]
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right", style="bold")
        table.add_row("This Month", f"${c['total_this']:.2f}")
        table.add_row("Last Month", f"${c['total_last']:.2f}")
        table.add_row("North–South", f"${c['transfer_ns']:.2f}")
        table.add_row("East–West", f"${c['transfer_ew']:.2f}")
        total_month = (
            self.data["cost"]["total_this"] + self.data["cost"]["transfer_ns"] + self.data["cost"]["transfer_ew"]
        )
        table.add_row("Projected Monthly", f"[bold red]${total_month:.2f}[/]")
        return Panel(table, title="💰 COST SUMMARY", border_style="yellow")

    # -------------------------------------------------------
    #  SERVICE BREAKDOWN PANEL
    # -------------------------------------------------------
    def create_service_breakdown(self):
        c = self.data["cost"]["services"]
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Service", style="dim")
        table.add_column("Cost", justify="right", style="bold")
        for svc, val in sorted(c.items(), key=lambda x: x[1], reverse=True)[:8]:
            table.add_row(svc[:20], f"${val:.2f}")
        return Panel(table, title="📊 SERVICE COST BREAKDOWN", border_style="green")

    # -------------------------------------------------------
    #  BUDGET STATUS PANEL
    # -------------------------------------------------------
    def create_budget_panel(self):
        buds = self.data["budgets"]
        if not buds:
            return Panel("No budgets found", title="💵 BUDGET STATUS", border_style="green")
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Budget", style="dim")
        table.add_column("Limit", justify="right")
        table.add_column("Used", justify="right")
        table.add_column("%", justify="right")
        for b in buds:
            color = "green"
            if b["perc"] > 90:
                color = "red"
            elif b["perc"] > 75:
                color = "yellow"
            table.add_row(
                b["name"][:20],
                f"${b['limit']:.2f}",
                f"${b['actual']:.2f}",
                f"[{color}]{b['perc']:.1f}%[/]",
            )
        return Panel(table, title="💵 BUDGET STATUS", border_style="yellow")
    # -------------------------------------------------------
    #  EPHEMERAL / ZOMBIE PANEL
    # -------------------------------------------------------
    def create_resource_health_panel(self):
        eph = self.data["ephemeral"]
        zomb = self.data["zombies"]
        text = Text()
        text.append(f"[bold green]Ephemeral:[/] {len(eph)}  ")
        text.append(f"[bold yellow]Zombies:[/] {len(zomb)}\n\n")

        if eph:
            text.append("[bold]Short-lived resources:[/]\n")
            for e in eph[:5]:
                life_m = e["lifetime"] / 60
                text.append(f"  {e['resource_id']} ({life_m:.1f} min)\n")
        if zomb:
            text.append("\n[bold]Idle resources:[/]\n")
            for z in zomb[:5]:
                text.append(f"  {z.get('id', z.get('name','?'))} ({z.get('region','?')})\n")

        return Panel(text, title="🧟 RESOURCE HEALTH", border_style="red")

    # -------------------------------------------------------
    #  STATUS PANEL
    # -------------------------------------------------------
    def create_status_panel(self):
        now = datetime.now(timezone.utc)
        next_scan = (self.last_refresh + timedelta(seconds=self.refresh_interval)).strftime("%H:%M UTC")
        total_resources = (
            len(self.data["ec2"]) + len(self.data["rds"]) + len(self.data["s3"]) + len(self.data["lambda"])
        )
        total_cost = self.data["cost"]["total_this"] + self.data["cost"]["transfer_ns"] + self.data["cost"]["transfer_ew"]
        txt = Text()
        txt.append(f"[dim]Account:[/] {self.account_alias}\n")
        txt.append(f"[dim]Regions:[/] {len(self.enabled_regions)}\n")
        txt.append(f"[dim]Resources:[/] {total_resources}\n")
        txt.append(f"[dim]Next Scan:[/] [cyan]{next_scan}[/]\n")
        txt.append(f"[dim]Scan Count:[/] {self.scan_count}\n")
        status = "NORMAL"
        color = "green"
        if total_cost > 100:
            status, color = "HIGH COST", "red"
        elif total_cost > 50:
            status, color = "MEDIUM", "yellow"
        txt.append(f"[dim]Status:[/] [{color}]{status}[/]")
        return Panel(txt, title="⚡ STATUS", border_style="green")

    # -------------------------------------------------------
    #  DASHBOARD LAYOUT
    # -------------------------------------------------------
    def create_layout(self):
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=2),
        )
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        layout["left"].split(
            Layout(name="cost"),
            Layout(name="service"),
            Layout(name="trend"),
        )
        layout["right"].split(
            Layout(name="budget"),
            Layout(name="health"),
            Layout(name="status"),
        )
        return layout

    # -------------------------------------------------------
    #  UPDATE DASHBOARD
    # -------------------------------------------------------
    def update_dashboard(self, layout):
        layout["header"].update(
            Align.center(Text("AWS COSTWATCH v8 - DevOps + FinOps Dashboard", style="bold green"))
        )
        layout["cost"].update(self.create_cost_summary_panel())
        layout["service"].update(self.create_service_breakdown())
        layout["trend"].update(self.create_trend_panel())
        layout["budget"].update(self.create_budget_panel())
        layout["health"].update(self.create_resource_health_panel())
        layout["status"].update(self.create_status_panel())

        next_scan = (self.last_refresh + timedelta(seconds=self.refresh_interval)).strftime("%H:%M UTC")
        total_resources = (
            len(self.data["ec2"]) + len(self.data["rds"]) + len(self.data["s3"]) + len(self.data["lambda"])
        )
        total_monthly = (
            self.data["cost"]["total_this"] + self.data["cost"]["transfer_ns"] + self.data["cost"]["transfer_ew"]
        )
        footer_text = (
            f"🔄 Scan #{self.scan_count} | Next: {next_scan} | "
            f"📦 {total_resources} Resources | 💰 ${total_monthly:.2f}/mo | "
            f"⏱️ {datetime.utcnow().strftime('%H:%M:%S UTC')}"
        )
        layout["footer"].update(Align.center(footer_text))

    # -------------------------------------------------------
    #  RUN DASHBOARD LOOP
    # -------------------------------------------------------
    def run_dashboard(self):
        layout = self.create_layout()
        self.update_dashboard(layout)
        try:
            with Live(layout, refresh_per_second=1, screen=True) as live:
                while True:
                    time.sleep(self.refresh_interval)
                    self.scan_all_resources()
                    self.update_dashboard(layout)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Dashboard stopped by user[/yellow]")
        except Exception as e:
            self.console.print(f"[red]Fatal error: {e}[/red]")
            logging.error(f"Fatal error: {e}")

# -----------------------------------------------------------
#  ENTRY POINT
# -----------------------------------------------------------
if __name__ == "__main__":
    try:
        AdvancedAWSCostWatch()
    except Exception as e:
        print(f"Startup error: {e}")
# ===========================================================
#  COSTWATCH v8.1  -  FinOps Enhancements (Part A)
# ===========================================================
import statistics

# -----------------------------------------------------------
#  Add-on class to extend the existing AdvancedAWSCostWatch
# -----------------------------------------------------------
def patch_v81_features():

    def get_idle_resources(self):
        """Detect idle EC2 / RDS resources using CloudWatch metrics"""
        idle_list = []
        cw = boto3.client("cloudwatch")
        try:
            # --- EC2 ---
            for i in [x for x in self.data.get("ec2", []) if x["state"] == "running"]:
                try:
                    m = cw.get_metric_statistics(
                        Namespace="AWS/EC2",
                        MetricName="CPUUtilization",
                        Dimensions=[{"Name": "InstanceId", "Value": i["id"]}],
                        StartTime=datetime.utcnow() - timedelta(hours=3),
                        EndTime=datetime.utcnow(),
                        Period=300,
                        Statistics=["Average"],
                    )
                    if m["Datapoints"]:
                        avg_cpu = statistics.mean(dp["Average"] for dp in m["Datapoints"])
                        if avg_cpu < 5:
                            idle_list.append(
                                {
                                    "id": i["id"],
                                    "type": i["type"],
                                    "region": i["region"],
                                    "metric": "CPU < 5%",
                                    "avg": avg_cpu,
                                }
                            )
                except Exception:
                    continue

            # --- RDS ---
            for r in [x for x in self.data.get("rds", []) if x["status"] == "available"]:
                try:
                    m = cw.get_metric_statistics(
                        Namespace="AWS/RDS",
                        MetricName="CPUUtilization",
                        Dimensions=[{"Name": "DBInstanceIdentifier", "Value": r["id"]}],
                        StartTime=datetime.utcnow() - timedelta(hours=3),
                        EndTime=datetime.utcnow(),
                        Period=300,
                        Statistics=["Average"],
                    )
                    if m["Datapoints"]:
                        avg_cpu = statistics.mean(dp["Average"] for dp in m["Datapoints"])
                        if avg_cpu < 5:
                            idle_list.append(
                                {
                                    "id": r["id"],
                                    "type": r["class"],
                                    "region": r["region"],
                                    "metric": "CPU < 5%",
                                    "avg": avg_cpu,
                                }
                            )
                except Exception:
                    continue
        except Exception as e:
            logging.warning(f"Idle resource check failed: {e}")
        return idle_list

    def create_idle_panel(self):
        idle = self.get_idle_resources()
        if not idle:
            return Panel("No idle resources detected", title="💤 IDLE RESOURCES", border_style="green")
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Resource", style="dim")
        table.add_column("Type")
        table.add_column("Region")
        table.add_column("Metric")
        table.add_column("Avg", justify="right")
        for r in idle[:10]:
            table.add_row(r["id"][:12], r["type"], r["region"], r["metric"], f"{r['avg']:.1f}%")
        return Panel(table, title="💤 IDLE RESOURCES", border_style="yellow")

    def create_active_resources_panel(self):
        """Show currently running EC2/RDS/Lambda with daily cost"""
        active_rows = []
        for i in [x for x in self.data.get("ec2", []) if x["state"] == "running"]:
            active_rows.append(
                (
                    i["name"][:18],
                    i["type"],
                    i["region"],
                    "running",
                    i["hourly"] * 24,
                )
            )
        for r in [x for x in self.data.get("rds", []) if x["status"] == "available"]:
            active_rows.append(
                (
                    r["id"][:18],
                    r["class"],
                    r["region"],
                    "available",
                    r["hourly"] * 24,
                )
            )
        for l in self.data.get("lambda", []):
            active_rows.append(
                (
                    l["name"][:18],
                    "lambda",
                    l["region"],
                    "active",
                    l["monthly"] / 30,
                )
            )
        if not active_rows:
            return Panel("No active resources", title="🖥️ ACTIVE RESOURCES", border_style="green")

        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Name", style="bold")
        table.add_column("Type", style="dim")
        table.add_column("Region")
        table.add_column("State")
        table.add_column("Daily Cost", justify="right")
        for row in active_rows[:10]:
            table.add_row(row[0], row[1], row[2], row[3], f"${row[4]:.2f}/day")
        return Panel(table, title="🖥️ ACTIVE RESOURCES (DAILY COST)", border_style="green")

    # Bind the new methods to the class
    AdvancedAWSCostWatch.get_idle_resources = get_idle_resources
    AdvancedAWSCostWatch.create_idle_panel = create_idle_panel
    AdvancedAWSCostWatch.create_active_resources_panel = create_active_resources_panel

# Apply patch
patch_v81_features()
print("[v8.1] Active resource and idle detection features loaded.")
# ===========================================================
#  COSTWATCH v8.1  -  FinOps Enhancements (Part B)
# ===========================================================

def patch_v81_part_b():

    def get_snapshot_cleanup(self):
        """Detect orphaned / old EBS snapshots"""
        items = []
        try:
            for region in self.enabled_regions:
                ec2 = boto3.client("ec2", region_name=region)
                resp = ec2.describe_snapshots(OwnerIds=["self"])
                for s in resp["Snapshots"]:
                    vol = s.get("VolumeId")
                    age = (datetime.now(timezone.utc) - s["StartTime"]).days
                    if not vol or age > 30:
                        items.append(
                            {
                                "id": s["SnapshotId"],
                                "volume": vol or "None",
                                "age": age,
                                "region": region,
                                "state": s["State"],
                            }
                        )
        except Exception as e:
            logging.warning(f"Snapshot scan error: {e}")
        return items

    def create_snapshot_cleanup_panel(self):
        snaps = self.get_snapshot_cleanup()
        if not snaps:
            return Panel("No snapshot cleanup candidates", title="📦 SNAPSHOT CLEANUP", border_style="green")
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Snapshot", style="dim")
        table.add_column("Age (d)", justify="right")
        table.add_column("Volume")
        table.add_column("Region")
        for s in sorted(snaps, key=lambda x: x["age"], reverse=True)[:8]:
            table.add_row(s["id"], str(s["age"]), s["volume"], s["region"])
        return Panel(table, title="📦 SNAPSHOT CLEANUP CANDIDATES", border_style="yellow")

    def create_transfer_matrix(self):
        """Detailed Data Transfer Matrix (East-West / North-South)"""
        ce = boto3.client("ce")
        today = datetime.utcnow().date()
        start = today.replace(day=1)
        try:
            resp = ce.get_cost_and_usage(
                TimePeriod={"Start": str(start), "End": str(today)},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
            )
        except Exception as e:
            logging.warning(f"Transfer matrix error: {e}")
            return Panel("Unable to fetch transfer data", title="🌍 DATA TRANSFER MATRIX", border_style="red")

        rows = []
        for g in resp["ResultsByTime"][0]["Groups"]:
            ut = g["Keys"][0]
            cost = float(g["Metrics"]["UnblendedCost"]["Amount"])
            if cost <= 0:
                continue
            if "DataTransfer" in ut or "Transfer" in ut:
                direction = "North–South" if any(k in ut for k in ["Out", "Internet"]) else "East–West"
                parts = ut.split("-")
                src = parts[0] if parts else "unknown"
                dst = "Internet" if "Internet" in ut else parts[2] if len(parts) > 2 else "internal"
                rows.append((src, dst, direction, cost))

        if not rows:
            return Panel("No transfer cost data", title="🌍 DATA TRANSFER MATRIX", border_style="green")

        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("From")
        table.add_column("To")
        table.add_column("Direction")
        table.add_column("Cost ($)", justify="right")
        for r in rows[:8]:
            table.add_row(r[0], r[1], r[2], f"{r[3]:.2f}")
        return Panel(table, title="🌍 DATA TRANSFER MATRIX", border_style="yellow")

    # --- Patch the methods into the class ---
    AdvancedAWSCostWatch.get_snapshot_cleanup = get_snapshot_cleanup
    AdvancedAWSCostWatch.create_snapshot_cleanup_panel = create_snapshot_cleanup_panel
    AdvancedAWSCostWatch.create_transfer_matrix = create_transfer_matrix

    # --- Extend the dashboard layout ---
    original_update_dashboard = AdvancedAWSCostWatch.update_dashboard

    def update_dashboard_v81(self, layout):
        original_update_dashboard(self, layout)

        # Insert new panels into right side
        layout["health"].update(self.create_snapshot_cleanup_panel())
        layout["status"].update(self.create_transfer_matrix())

        # Insert Active/Idle panels into left side
        layout["cost"].update(self.create_active_resources_panel())
        layout["trend"].update(self.create_idle_panel())

    AdvancedAWSCostWatch.update_dashboard = update_dashboard_v81

# Apply Part B patch
patch_v81_part_b()
print("[v8.1] Snapshot cleanup + data transfer matrix loaded.")
