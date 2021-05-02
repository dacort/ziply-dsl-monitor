from parse import StatsTable, Uptime
from datetime import datetime

st = StatsTable(open("status_page.html").read())


def test_banner_parse():

    # Make sure the banner got parsed right
    assert st.banner_stats != {}
    assert "WAN Conn" in st.banner_stats
    assert st.banner_stats.get("WAN Conn") == "Connected"


def test_line_info_parse():
    assert st.line_info != {}
    assert "Mode" in st.line_info
    assert st.line_info.get("Mode")[0] == "ADSL2+"
    assert st.line_info.get("Uptime")[0] == "00:00:02:26"


def test_line_stats_parse():
    assert st.line_stats != {}
    assert "Super Frame Errors" in st.line_stats
    assert type(st.line_stats.get("Super Frame Errors")) == list

    sf = st.line_stats.get("Super Frame Errors")[0]
    assert sf.stat_name == "Super Frame Errors"
    assert sf.downstream_value == 0.0

    sf = st.line_stats.get("Super Frame Errors")[1]
    assert sf.stat_name == "Super Frame Errors"
    assert sf.downstream_value == 1.0

def test_old_vs_new_uptime():
    time_str_1 = st.find_line_desc_by_name('Uptime')[0]
    t1 = datetime.strptime(time_str_1, "00:%H:%M:%S")
    g2 = Uptime(time_str=time_str_1)
    assert t1.hour == g2.hours
    assert t1.minute == g2.minutes
    assert t1.second == g2.seconds

def test_uptime_parse():
    time_str_1 = '00:03:56:24'
    d1 = Uptime(time_str=time_str_1)
    assert d1.days == 0
    assert d1.hours == 3
    assert d1.minutes == 56
    assert d1.seconds == 24
    assert d1.total_seconds() == 14184

    d2 = Uptime("01:22:08:09")
    assert d2.days == 1
    assert d2.hours == 22
    assert d2.minutes == 8
    assert d2.seconds == 9
    assert d2.total_seconds() == 166089

