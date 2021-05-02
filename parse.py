from dataclasses import dataclass
from datetime import datetime, timedelta
from time import sleep
import argparse

import requests
from bs4 import BeautifulSoup, element
from prometheus_client import Gauge, Enum, start_http_server


@dataclass
class LineStat:
    """Keep track of a line stat"""

    stat_name: str
    downstream_value: float
    upstream_value: float

    def total(self) -> float:
        return self.downstream_value + self.upstream_value


@dataclass
class Uptime:
    """Keep track of line uptime"""

    days: int
    hours: int
    minutes: int
    seconds: int

    def __init__(self, time_str: str) -> None:
        [self.days, self.hours, self.minutes, self.seconds] = [
            int(val) for val in time_str.split(":")
        ]

    def total_seconds(self):
        return timedelta(
            days=self.days, hours=self.hours, minutes=self.minutes, seconds=self.seconds
        ).total_seconds()


@dataclass
class DSLStats:
    """Class for keeping track of DSL stats."""

    link1_hec_errors: LineStat = LineStat(
        stat_name="link1_hec_errors", downstream_value=0.0, upstream_value=0.0
    )
    link2_hec_errors: LineStat = LineStat(
        stat_name="link2_hec_errors", downstream_value=0.0, upstream_value=0.0
    )
    link1_superframe_errors: LineStat = LineStat(
        stat_name="link1_superframe_errors", downstream_value=0.0, upstream_value=0.0
    )
    link2_superframe_errors: LineStat = LineStat(
        stat_name="link2_superframe_errors", downstream_value=0.0, upstream_value=0.0
    )
    link1_total_err_seconds: LineStat = LineStat(
        stat_name="link1_total_err_seconds", downstream_value=0.0, upstream_value=0.0
    )
    link2_total_err_seconds: LineStat = LineStat(
        stat_name="link2_total_err_seconds", downstream_value=0.0, upstream_value=0.0
    )
    link1_sn_margin_db: LineStat = LineStat(
        stat_name="link1_sn_margin", downstream_value=0.0, upstream_value=0.0
    )
    link2_sn_margin_db: LineStat = LineStat(
        stat_name="link2_sn_margin", downstream_value=0.0, upstream_value=0.0
    )

    link1_uptime: int = 0
    link2_uptime: int = 0
    wan_status: str = "Offline"  # Can be one of Offline, Down, Connected


class StatsTable:
    def __init__(self, html: str) -> None:
        self.html = html
        self.banner_stats = {}
        self.line_info = {}
        self.line_stats = {}

        self._parse_stats_page()

    def find_banner_stat_by_name(self, name: str):
        return self.banner_stats.get(name)

    def find_line_desc_by_name(self, name: str, line_index: int = None):
        val = self.line_info.get(name)
        if line_index is not None:
            return val[line_index]
        else:
            return val

    def find_line_stat_by_name(self, name: str, line_index: int = None):
        val = self.line_stats.get(name)
        if line_index is not None:
            return val[line_index]
        else:
            return val

    def _parse_stats_page(self):
        """
        Parse the xDSL stats page from an Arris NVG443B DSL modem.

        There are two important tables on the page:
        1. A table at the top that has overal WAN information, particularly if it is connected or not.
        2. A table in the middle that is composed of two sections:
            - 3 columns wide: overall line status for each line including status and uptime
            - 5 columns wide: different upstream/downstream stats for each line

        We parse all of those tables and create a lookup dictionary for the different stats.
        """
        soup = BeautifulSoup(self.html, "html.parser")
        tables = soup.find_all("table")
        banner_table = tables[0]
        line_stats_table = tables[1]

        self.banner_stats = self._parse_banner(banner_table)
        self.line_info = self._parse_line_info(line_stats_table)
        self.line_stats = self._parse_line_stats(line_stats_table)

    def _parse_banner(self, table: element.Tag):
        banner_data = {}

        for td in table.find_all("td"):
            [name, value] = [s.text.rstrip(":") for s in td.find_all("span")]
            banner_data[name] = value

        return banner_data

    def _parse_line_info(self, table: element.Tag):
        line_status_data = {}
        # Row 0 is the header
        # Then we just need to fine all rows with length == 3
        line_status_rows = [
            x.find_all("td") for x in table.find_all("tr") if len(x.find_all("td")) == 3
        ]

        for row in line_status_rows:
            [name, line1_val, line2_val] = [s.text.rstrip(":") for s in row]
            line_status_data[name] = [line1_val, line2_val]

        return line_status_data

    def _parse_line_stats(self, table: element.Tag):
        line_stats_data = {}

        # We want to pull out every row that has 5 columns.
        # Row0 is the header and we can assume the following:
        # Columns 1-2 are for Line 1, 3-4 are for Line 2
        # Columns 1,3 are Downstream, 2,4 are Upstream
        # e.g.
        # Stat name | Link 1 Downstream | Link 1 Upstream | Link 2 Down | Link 2 Up
        # Finally, we ignore "Trellis Coding" because we don't care about and it's the only non-numeric stat
        line_stats_rows = [
            x.find_all("td") for x in table.find_all("tr") if len(x.find_all("td")) == 5
        ][1:]

        for row in line_stats_rows:
            [name, l1_down_val, l1_up_val, l2_down_val, l2_up_val] = [
                s.text.rstrip(":") for s in row
            ]
            if name == "Trellis Coding":
                pass
            line_stats_data[name] = [
                LineStat(
                    stat_name=name,
                    downstream_value=float(l1_down_val),
                    upstream_value=float(l1_up_val),
                ),
                LineStat(
                    stat_name=name,
                    downstream_value=float(l2_down_val),
                    upstream_value=float(l2_up_val),
                ),
            ]

        return line_stats_data


def get_stats() -> str:
    r = requests.get("http://192.168.254.254/cgi-bin/dslstatistics.ha", timeout=3)
    return r.text


def parse_stats() -> DSLStats:
    try:
        content = get_stats()
        st = StatsTable(content)
    except:
        # The server is down hard :( Return nothing
        return None

    t1 = st.find_line_desc_by_name("Uptime")[0]
    t2 = st.find_line_desc_by_name("Uptime")[1]
    return DSLStats(
        link1_uptime=Uptime(t1).total_seconds(),
        link2_uptime=Uptime(t2).total_seconds(),
        wan_status=st.find_banner_stat_by_name("WAN Conn"),
        link1_hec_errors=st.find_line_stat_by_name("HEC Errors", 0),
        link2_hec_errors=st.find_line_stat_by_name("HEC Errors", 1),
        link1_superframe_errors=st.find_line_stat_by_name("Super Frame Errors", 0),
        link2_superframe_errors=st.find_line_stat_by_name("Super Frame Errors", 1),
        link1_total_err_seconds=st.find_line_stat_by_name("Total ES", 0),
        link2_total_err_seconds=st.find_line_stat_by_name("Total ES", 1),
        link1_sn_margin_db=st.find_line_stat_by_name("SN Margin (dB)", 0),
        link2_sn_margin_db=st.find_line_stat_by_name("SN Margin (dB)", 1),
    )


def poll_stats(step_seconds: int = 1):
    uptime_l1 = Gauge("link1_uptime", "Uptime of Link1")
    uptime_l2 = Gauge("link2_uptime", "Uptime of Link2")
    connection_state = Enum(
        "connection_state", "WAN Connection", states=["Connected", "Offline", "Down"]
    )
    superframe_errors = Gauge(
        "superframe_error_count", "Super Frame Eerrors", ["link", "direction"]
    )
    hec_errors = Gauge("hec_error_count", "HEC Errors", ["link", "direction"])
    total_err_seconds = Gauge("total_err_seconds", "Total ES", ["link", "direction"])
    sn_margin_db = Gauge("sn_margin_db", "SN Margin (dB)", ["link", "direction"])

    while True:
        stats = parse_stats()
        print(stats)
        if stats is not None:
            uptime_l1.set(stats.link1_uptime)
            uptime_l2.set(stats.link2_uptime)
            connection_state.state(stats.wan_status)
            superframe_errors.labels("Link 1", "Downstream").set(
                stats.link1_superframe_errors.downstream_value
            )
            superframe_errors.labels("Link 1", "Upstream").set(
                stats.link1_superframe_errors.upstream_value
            )
            superframe_errors.labels("Link 2", "Downstream").set(
                stats.link2_superframe_errors.downstream_value
            )
            superframe_errors.labels("Link 2", "Upstream").set(
                stats.link2_superframe_errors.upstream_value
            )

            hec_errors.labels("Link 1", "Downstream").set(
                stats.link1_hec_errors.downstream_value
            )
            hec_errors.labels("Link 1", "Upstream").set(
                stats.link1_hec_errors.upstream_value
            )
            hec_errors.labels("Link 2", "Downstream").set(
                stats.link2_hec_errors.downstream_value
            )
            hec_errors.labels("Link 2", "Upstream").set(
                stats.link2_hec_errors.upstream_value
            )

            total_err_seconds.labels("Link 1", "Downstream").set(
                stats.link1_total_err_seconds.downstream_value
            )
            total_err_seconds.labels("Link 1", "Upstream").set(
                stats.link1_total_err_seconds.upstream_value
            )
            total_err_seconds.labels("Link 2", "Downstream").set(
                stats.link2_total_err_seconds.downstream_value
            )
            total_err_seconds.labels("Link 2", "Upstream").set(
                stats.link2_total_err_seconds.upstream_value
            )

            sn_margin_db.labels("Link 1", "Downstream").set(
                stats.link1_sn_margin_db.downstream_value
            )
            sn_margin_db.labels("Link 1", "Upstream").set(
                stats.link1_sn_margin_db.upstream_value
            )
            sn_margin_db.labels("Link 2", "Downstream").set(
                stats.link2_sn_margin_db.downstream_value
            )
            sn_margin_db.labels("Link 2", "Upstream").set(
                stats.link2_sn_margin_db.upstream_value
            )

        sleep(step_seconds)


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor my shitty DSL.")
    parser.add_argument(
        "--serve", help="Run a Prometheus endpoint", action="store_true"
    )
    parser.add_argument(
        "--oneshot", help="Only one one data retrieval loop", action="store_true"
    )
    parser.add_argument(
        "--interval",
        help="Interval in seconds at which to poll the endpoint",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--port",
        help="Port on which to run the Prometheus endpoint",
        type=int,
        default=8000,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.oneshot:
        print(parse_stats())
        exit()

    if args.serve:
        # Start up the server to expose the metrics.
        print(f"Starting prometheus server on port {args.port}")
        start_http_server(args.port)

    # Continuously poll the DSL server
    poll_stats(args.interval)