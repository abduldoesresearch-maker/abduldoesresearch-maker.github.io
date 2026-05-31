import argparse
import os
import sys
from functools import lru_cache
from typing import List, Optional

import pandas as pd
from google.cloud import bigquery

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_PLOTTING = True
except ImportError:
    HAS_PLOTTING = False

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

PROJECT_ID = "alert-palace-457403-t8"
DATASET_ID = "cyclistic_data"
UPLOADED_MONTHS = [
    "202505",
    "202506",
    "202507",
    "202508",
    "202509",
    "202510",
    "202511",
    "202512",
    "202601",
    "202602",
    "202603",
    "202604",
]
OUTPUT_DIR = "analysis_outputs"
PLOT_DIR = os.path.join(OUTPUT_DIR, "plots")

client = bigquery.Client(project=PROJECT_ID)


def ensure_output_dirs() -> None:
    os.makedirs(PLOT_DIR, exist_ok=True)


@lru_cache(maxsize=None)
def build_union_query(months: Optional[str] = None) -> str:
    if months:
        selected_months = [m.strip() for m in months.split(",") if m.strip()]
    else:
        selected_months = UPLOADED_MONTHS
    table_queries = [
        f"SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.divvy_{month}`"
        for month in sorted(selected_months)
    ]
    return "\nUNION ALL\n".join(table_queries)


def run_query(query: str) -> pd.DataFrame:
    query_job = client.query(query)
    return query_job.result().to_dataframe()


def quality_check(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT 'Total Rows' AS metric, COUNT(*) AS value FROM base
UNION ALL
SELECT 'Null started_at', COUNTIF(started_at IS NULL) FROM base
UNION ALL
SELECT 'Null ended_at', COUNTIF(ended_at IS NULL) FROM base
UNION ALL
SELECT 'Null member_casual', COUNTIF(member_casual IS NULL) FROM base
UNION ALL
SELECT 'Invalid duration (<=0)', COUNTIF(TIMESTAMP_DIFF(ended_at, started_at, SECOND) <= 0) FROM base
UNION ALL
SELECT 'Null start_station_name', COUNTIF(start_station_name IS NULL) FROM base
UNION ALL
SELECT 'Null end_station_name', COUNTIF(end_station_name IS NULL) FROM base
UNION ALL
SELECT 'Null rideable_type', COUNTIF(rideable_type IS NULL) FROM base
UNION ALL
SELECT 'Stationless ride share', ROUND(SUM(CASE WHEN start_station_name IS NULL OR end_station_name IS NULL THEN 1 ELSE 0 END)/COUNT(*)*100, 2) FROM base
"""
    return run_query(query)


def outlier_analysis(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT 'Rides > 24 hours' AS outlier_type, COUNT(*) AS count
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 86400
UNION ALL
SELECT 'Rides < 1 minute', COUNT(*)
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) < 60
  AND TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0
UNION ALL
SELECT 'Rides > 2 hours', COUNT(*)
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 7200
UNION ALL
SELECT 'Zero-duration rides', COUNT(*)
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) = 0
UNION ALL
SELECT 'Negative duration rides', COUNT(*)
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) < 0
"""
    return run_query(query)


def business_summary(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  COUNT(*) AS total_rides,
  ROUND(SUM(CASE WHEN member_casual = 'member' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS member_share_pct,
  ROUND(SUM(CASE WHEN member_casual = 'casual' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS casual_share_pct,
  ROUND(AVG(CASE WHEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0 THEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) / 60 ELSE NULL END), 1) AS avg_ride_minutes,
  ROUND(AVG(CASE WHEN member_casual = 'member' AND TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0 THEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) / 60 ELSE NULL END), 1) AS avg_member_minutes,
  ROUND(AVG(CASE WHEN member_casual = 'casual' AND TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0 THEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) / 60 ELSE NULL END), 1) AS avg_casual_minutes
FROM base
WHERE started_at IS NOT NULL AND ended_at IS NOT NULL
"""
    return run_query(query)


def conversion_opportunity(months: Optional[str] = None) -> pd.DataFrame:
    """
    Identifies casual ride patterns that suggest habitual use —
    these are the riders most likely to benefit from and convert to membership.
    Looks at: weekday riding, commute-hour riding, and ride frequency signals.
    """
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query}),
casual_rides AS (
    SELECT
        started_at,
        ended_at,
        EXTRACT(HOUR FROM started_at) AS hour,
        EXTRACT(DAYOFWEEK FROM started_at) AS day_of_week,
        TIMESTAMP_DIFF(ended_at, started_at, SECOND) / 60 AS ride_mins
    FROM base
    WHERE member_casual = 'casual'
      AND TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0
),
classified AS (
    SELECT
        ride_mins,
        CASE
            WHEN hour BETWEEN 7 AND 9 THEN true
            WHEN hour BETWEEN 16 AND 19 THEN true
            ELSE false
        END AS is_commute_hour,
        CASE
            WHEN day_of_week BETWEEN 2 AND 6 THEN true
            ELSE false
        END AS is_weekday,
        CASE
            WHEN ride_mins <= 30 THEN true
            ELSE false
        END AS is_short_ride
    FROM casual_rides
)
SELECT
    'Total casual rides' AS metric,
    COUNT(*) AS value,
    100.0 AS percentage
FROM classified
UNION ALL
SELECT
    'Rides during commute hours (7-9am, 4-7pm)',
    COUNT(*),
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM classified), 1)
FROM classified
WHERE is_commute_hour = true
UNION ALL
SELECT
    'Weekday rides',
    COUNT(*),
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM classified), 1)
FROM classified
WHERE is_weekday = true
UNION ALL
SELECT
    'Short rides under 30 mins',
    COUNT(*),
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM classified), 1)
FROM classified
WHERE is_short_ride = true
UNION ALL
SELECT
    'Commute-hour AND weekday (strongest signal)',
    COUNT(*),
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM classified), 1)
FROM classified
WHERE is_commute_hour = true
  AND is_weekday = true
UNION ALL
SELECT
    'All 3 signals: commute + weekday + short ride',
    COUNT(*),
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM classified), 1)
FROM classified
WHERE is_commute_hour = true
  AND is_weekday = true
  AND is_short_ride = true
"""
    return run_query(query)


def operational_summary(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  COUNT(*) AS total_rides,
  COUNT(DISTINCT start_station_name) AS unique_start_stations,
  COUNT(DISTINCT end_station_name) AS unique_end_stations,
  COUNT(DISTINCT rideable_type) AS unique_rideable_types,
  ROUND(SUM(CASE WHEN start_station_name IS NULL OR end_station_name IS NULL THEN 1 ELSE 0 END)/COUNT(*)*100, 2) AS stationless_pct,
  ROUND(SUM(CASE WHEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 7200 THEN 1 ELSE 0 END)/COUNT(*)*100, 2) AS long_ride_pct
FROM base
"""
    return run_query(query)


def risk_summary(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  'Data quality issues' AS metric,
  COUNT(*) AS count
FROM base
WHERE started_at IS NULL
   OR ended_at IS NULL
   OR member_casual IS NULL
   OR TIMESTAMP_DIFF(ended_at, started_at, SECOND) <= 0
UNION ALL
SELECT 'High-risk outlier rides', COUNT(*)
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 86400
UNION ALL
SELECT 'Stationless rides', COUNT(*)
FROM base
WHERE start_station_name IS NULL OR end_station_name IS NULL
UNION ALL
SELECT 'Invalid station sequences', COUNT(*)
FROM base
WHERE start_station_name = end_station_name
"""
    return run_query(query)


def weekday_weekend(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  CASE WHEN EXTRACT(DAYOFWEEK FROM started_at) IN (1, 7) THEN 'Weekend' ELSE 'Weekday' END AS day_type,
  member_casual,
  COUNT(*) AS total_rides,
  ROUND(AVG(TIMESTAMP_DIFF(ended_at, started_at, SECOND) / 60), 1) AS avg_ride_minutes
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0
GROUP BY day_type, member_casual
ORDER BY day_type, member_casual
"""
    return run_query(query)


def seasonal_trends(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  CASE
    WHEN EXTRACT(MONTH FROM started_at) IN (5, 6, 7) THEN 'Spring (May-Jul)'
    WHEN EXTRACT(MONTH FROM started_at) IN (8, 9, 10) THEN 'Summer (Aug-Oct)'
    WHEN EXTRACT(MONTH FROM started_at) IN (11, 12, 1) THEN 'Fall (Nov-Jan)'
    ELSE 'Winter (Feb-Apr)'
  END AS season,
  member_casual,
  COUNT(*) AS total_rides,
  ROUND(AVG(TIMESTAMP_DIFF(ended_at, started_at, SECOND) / 60), 1) AS avg_ride_minutes
FROM base
WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0
GROUP BY season, member_casual
ORDER BY season, member_casual
"""
    return run_query(query)


def hourly_patterns(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  EXTRACT(HOUR FROM started_at) AS hour,
  member_casual,
  COUNT(*) AS total_rides
FROM base
GROUP BY hour, member_casual
ORDER BY hour, member_casual
"""
    return run_query(query)


def top_stations(months: Optional[str] = None, limit: int = 20) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  start_station_name,
  member_casual,
  COUNT(*) AS total_rides
FROM base
WHERE start_station_name IS NOT NULL
GROUP BY start_station_name, member_casual
ORDER BY total_rides DESC
LIMIT {limit}
"""
    return run_query(query)


def member_stations(months: Optional[str] = None, limit: int = 10) -> pd.DataFrame:
    """
    Returns top start stations separately for members and casuals.
    Reveals whether each group clusters at different location types
    (e.g. transit hubs for members, tourist spots for casuals).
    """
    union_query = build_union_query(months)
    query = f"""
    WITH base AS ({union_query}),

    -- Step 1: Count rides per station per user type
    station_counts AS (
        SELECT
            start_station_name,
            member_casual,
            COUNT(*) AS total_rides
        FROM base
        WHERE start_station_name IS NOT NULL
        GROUP BY start_station_name, member_casual
    ),

    -- Step 2: Rank stations within each user type
    -- ROW_NUMBER assigns rank 1,2,3... per group
    ranked AS (
        SELECT
            start_station_name,
            member_casual,
            total_rides,
            ROW_NUMBER() OVER (
                PARTITION BY member_casual      -- restart ranking for each user type
                ORDER BY total_rides DESC       -- rank by most rides first
            ) AS rank
        FROM station_counts
    )

    -- Step 3: Keep only top N per user type
    SELECT
        rank,
        member_casual,
        start_station_name,
        total_rides
    FROM ranked
    WHERE rank <= {limit}
    ORDER BY member_casual, rank
    """
    return run_query(query)


def rideable_type_breakdown(months: Optional[str] = None) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  rideable_type,
  member_casual,
  COUNT(*) AS total_rides,
  ROUND(AVG(TIMESTAMP_DIFF(ended_at, started_at, SECOND) / 60), 1) AS avg_ride_minutes
FROM base
WHERE rideable_type IS NOT NULL
GROUP BY rideable_type, member_casual
ORDER BY rideable_type, member_casual
"""
    return run_query(query)


def route_popularity(months: Optional[str] = None, limit: int = 20) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT
  CONCAT(COALESCE(start_station_name, 'UNKNOWN'), ' -> ', COALESCE(end_station_name, 'UNKNOWN')) AS route,
  COUNT(*) AS total_rides
FROM base
GROUP BY route
ORDER BY total_rides DESC
LIMIT {limit}
"""
    return run_query(query)


def duration_distribution(months: Optional[str] = None, bins: Optional[List[int]] = None) -> pd.DataFrame:
    if bins is None:
        bins = [1, 5, 10, 20, 30, 60, 120]
    union_query = build_union_query(months)
    bids = []
    bids.append("WHEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) BETWEEN 1 AND 59 THEN '<1m'")
    for start, end in zip(bins, bins[1:]):
        bids.append(
            f"WHEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) BETWEEN {start * 60} AND {end * 60 - 1} THEN '{start}-{end}m'"
        )
    bids.append(f"WHEN TIMESTAMP_DIFF(ended_at, started_at, SECOND) >= {bins[-1] * 60} THEN '{bins[-1]}m+'")
    bucket_case = "\n        ".join(bids)
    query = f"""
WITH base AS ({union_query})
SELECT
  bucket,
  COUNT(*) AS total_rides
FROM (
  SELECT
    CASE
      {bucket_case}
      ELSE 'UNKNOWN'
    END AS bucket
  FROM base
  WHERE TIMESTAMP_DIFF(ended_at, started_at, SECOND) > 0
)
GROUP BY bucket
ORDER BY
  CASE bucket
    WHEN '<1m' THEN 1
    WHEN '1-5m' THEN 2
    WHEN '5-10m' THEN 3
    WHEN '10-20m' THEN 4
    WHEN '20-30m' THEN 5
    WHEN '30-60m' THEN 6
    WHEN '60-120m' THEN 7
    ELSE 8
  END
"""
    return run_query(query)


def preview(months: Optional[str] = None, limit: int = 20) -> pd.DataFrame:
    union_query = build_union_query(months)
    query = f"""
WITH base AS ({union_query})
SELECT *
FROM base
LIMIT {limit}
"""
    return run_query(query)


def custom_query(sql: str, months: Optional[str] = None) -> pd.DataFrame:
    if "{union_query}" in sql:
        query = sql.format(union_query=build_union_query(months))
    else:
        query = sql
    return run_query(query)


def save_dataframe(df: pd.DataFrame, name: str) -> None:
    ensure_output_dirs()
    path = os.path.join(OUTPUT_DIR, f"{name}.csv")
    df.to_csv(path, index=False)
    print(f"Saved table to {path}")


def save_plot(fig, name: str) -> None:
    if not HAS_PLOTTING:
        print("Plotting library is not installed. Install matplotlib to save plots.")
        return
    ensure_output_dirs()
    path = os.path.join(PLOT_DIR, f"{name}.png")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved plot to {path}")


def plot_hourly(months: Optional[str] = None) -> None:
    if not HAS_PLOTTING:
        print("Plotting unavailable: matplotlib is missing.")
        return
    df = hourly_patterns(months)
    if df.empty:
        print("No hourly data returned.")
        return

    fig, ax = plt.subplots(figsize=(14, 7))
    colors = {"member": "#1f77b4", "casual": "#ff7f0e"}

    for user_type in ["member", "casual"]:
        subset = df[df["member_casual"] == user_type]
        ax.plot(
            subset["hour"],
            subset["total_rides"],
            marker="o",
            linestyle="-",
            label=user_type.capitalize(),
            linewidth=3,
            color=colors[user_type],
        )
        ax.fill_between(
            subset["hour"],
            subset["total_rides"],
            alpha=0.15,
            color=colors[user_type],
        )

    rush_windows = [(6, 9), (16, 19)]
    for start, end in rush_windows:
        ax.axvspan(start, end, color="#dbe9ff", alpha=0.35)

    ax.set_title("Hourly Ride Demand: Commuter Peaks vs Leisure Usage", fontsize=16, fontweight="bold")
    ax.text(
        0.02,
        0.92,
        "Shaded bands show commuter windows (7-9am, 4-7pm).\nMembers dominate commute peaks; casuals show broader afternoon demand.",
        transform=ax.transAxes,
        fontsize=11,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )

    member_peak = df[df["member_casual"] == "member"].sort_values("total_rides", ascending=False).iloc[0]
    casual_peak = df[df["member_casual"] == "casual"].sort_values("total_rides", ascending=False).iloc[0]
    summary_text = (
        f"Member peak: {int(member_peak['hour'])}:00 ({member_peak['total_rides']:,} rides)\n"
        f"Casual peak: {int(casual_peak['hour'])}:00 ({casual_peak['total_rides']:,} rides)"
    )
    ax.text(
        0.98,
        0.12,
        summary_text,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=11,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )

    ax.set_xlabel("Hour of Day", fontsize=12)
    ax.set_ylabel("Total Rides", fontsize=12)
    ax.set_xticks(list(range(0, 24, 2)))
    ax.set_xlim(0, 23)
    ax.set_ylim(0, df["total_rides"].max() * 1.08)
    ax.grid(axis="y", alpha=0.3)

    member_peak_y = df[(df["member_casual"] == "member") & (df["hour"] == 8)]["total_rides"]
    casual_peak_y = df[(df["member_casual"] == "casual") & (df["hour"] == 15)]["total_rides"]
    member_peak_y = member_peak_y.iloc[0] if not member_peak_y.empty else df["total_rides"].max() * 0.6
    casual_peak_y = casual_peak_y.iloc[0] if not casual_peak_y.empty else df["total_rides"].max() * 0.45

    ax.annotate(
        "Morning commute",
        xy=(8, member_peak_y),
        xytext=(8, df["total_rides"].max() * 0.95),
        arrowprops={"arrowstyle": "->", "color": "#555555"},
        ha="center",
        color="#555555",
        fontsize=10,
    )

    ax.annotate(
        "Casual afternoon demand",
        xy=(15, casual_peak_y),
        xytext=(14, df["total_rides"].max() * 0.75),
        arrowprops={"arrowstyle": "->", "color": "#555555"},
        ha="center",
        color="#555555",
        fontsize=10,
    )

    ax.legend(title="User Type", fontsize=11)
    save_plot(fig, "hourly_patterns")


def plot_seasonal(months: Optional[str] = None) -> None:
    if not HAS_PLOTTING:
        print("Plotting unavailable: matplotlib is missing.")
        return
    df = seasonal_trends(months)
    if df.empty:
        print("No seasonal data returned.")
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    for user_type in df["member_casual"].unique():
        subset = df[df["member_casual"] == user_type]
        ax.bar(subset["season"], subset["total_rides"], alpha=0.7, label=user_type)
    ax.set_title("Seasonal Ride Volume by User Type")
    ax.set_ylabel("Total Rides")
    ax.set_xticklabels(df["season"].unique(), rotation=25, ha="right")
    ax.legend()
    save_plot(fig, "seasonal_trends")


def plot_stations(months: Optional[str] = None, limit: int = 20) -> None:
    if not HAS_PLOTTING:
        print("Plotting unavailable: matplotlib is missing.")
        return
    df = top_stations(months, limit)
    if df.empty:
        print("No station data returned.")
        return
    total = df.groupby("start_station_name")["total_rides"].sum().nlargest(limit)
    fig, ax = plt.subplots(figsize=(10, 8))
    total.plot(kind="barh", ax=ax)
    ax.set_title("Top Start Stations by Ride Volume")
    ax.set_xlabel("Total Rides")
    ax.invert_yaxis()
    save_plot(fig, "top_stations")


def plot_member_stations(months: Optional[str] = None, limit: int = 10) -> None:
    """
    Side-by-side horizontal bar charts comparing top stations
    for members vs casuals.
    """
    if not HAS_PLOTTING:
        print("Plotting unavailable: matplotlib is missing.")
        return

    df = member_stations(months, limit)
    if df.empty:
        print("No station data returned.")
        return

    # Split into two separate DataFrames
    members_df = df[df['member_casual'] == 'member'].copy()
    casuals_df = df[df['member_casual'] == 'casual'].copy()

    # Create side-by-side charts
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f'Top {limit} Start Stations: Members vs Casuals',
        fontsize=14,
        fontweight='bold'
    )

    # Members chart (left)
    ax1.barh(
        members_df['start_station_name'],
        members_df['total_rides'],
        color='steelblue'
    )
    ax1.set_title('Members', fontsize=12, color='steelblue')
    ax1.set_xlabel('Total Rides')
    ax1.invert_yaxis()
    ax1.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f'{int(x):,}')
    )

    # Casuals chart (right)
    ax2.barh(
        casuals_df['start_station_name'],
        casuals_df['total_rides'],
        color='coral'
    )
    ax2.set_title('Casuals', fontsize=12, color='coral')
    ax2.set_xlabel('Total Rides')
    ax2.invert_yaxis()
    ax2.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f'{int(x):,}')
    )

    save_plot(fig, "member_stations")


def plot_distribution(months: Optional[str] = None) -> None:
    if not HAS_PLOTTING:
        print("Plotting unavailable: matplotlib is missing.")
        return
    df = duration_distribution(months)
    if df.empty:
        print("No duration distribution data returned.")
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(df["bucket"], df["total_rides"], color="#4c72b0")
    ax.set_title("Ride Duration Distribution")
    ax.set_xlabel("Duration Bucket")
    ax.set_ylabel("Total Rides")
    ax.set_xticklabels(df["bucket"], rotation=45, ha="right")
    save_plot(fig, "duration_distribution")


def plot_command(name: str, months: Optional[str] = None, limit: int = 20) -> None:
    if name == "hourly":
        plot_hourly(months)
    elif name == "seasonal":
        plot_seasonal(months)
    elif name == "stations":
        plot_stations(months, limit)
    elif name == "member_stations":
        plot_member_stations(months, limit)
    elif name == "distribution":
        plot_distribution(months)
    else:
        print(f"No plot defined for '{name}'. Available: hourly, seasonal, stations, member_stations, distribution.")


def print_df(df: pd.DataFrame) -> None:
    if df.empty:
        print("No results returned.")
    else:
        print(df.to_string(index=False))


def parse_months(months_text: Optional[str]) -> Optional[str]:
    if not months_text:
        return None
    months = [m.strip() for m in months_text.split(",") if m.strip()]
    return ",".join(months) if months else None


def interactive_mode() -> None:
    commands = {
        "quality": quality_check,
        "outliers": outlier_analysis,
        "business": business_summary,
        "conversion": conversion_opportunity,
        "conversion_opportunity": conversion_opportunity,
        "operations": operational_summary,
        "risk": risk_summary,
        "weekday": weekday_weekend,
        "seasonal": seasonal_trends,
        "hourly": hourly_patterns,
        "stations": top_stations,
        "member_stations": member_stations,
        "rideable": rideable_type_breakdown,
        "routes": route_popularity,
        "distribution": duration_distribution,
        "preview": preview,
    }

    print("Divvy Data Explorer Agent")
    print("Type a command, or 'help' to list available commands.")

    while True:
        user_input = input("agent> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            break
        if user_input.lower() == "help":
            print("Available commands:")
            print("  quality, outliers, business, conversion, operations, risk")
            print("  weekday, seasonal, hourly, stations, member_stations, rideable, routes, distribution, preview")
            print("  custom <SQL>  - use {union_query} placeholder for dataset union")
            print("  plot <hourly|seasonal|stations|member_stations|distribution>")
            print("  months=<comma separated months>  - optional before command")
            print("  quit")
            continue

        months = None
        plot_command_text = None
        if user_input.startswith("months="):
            parts = user_input.split(None, 1)
            month_text = parts[0].split("=", 1)[1]
            months = parse_months(month_text)
            if len(parts) == 1:
                print("Specify a command after months=...")
                continue
            user_input = parts[1]

        if user_input.startswith("plot "):
            plot_command_text = user_input[len("plot "):].strip().split()[0]
            plot_command(plot_command_text, months)
            continue

        if user_input.startswith("custom "):
            sql = user_input[len("custom "):].strip()
            if not sql:
                print("Provide a SQL query after 'custom'.")
                continue
            try:
                print_df(custom_query(sql, months))
            except Exception as error:
                print(f"Query failed: {error}")
            continue

        cmd = user_input.split()[0]
        if cmd in commands:
            try:
                if cmd in {"stations", "routes", "member_stations"}:
                    df = commands[cmd](months=months, limit=10)
                else:
                    df = commands[cmd](months=months)
                print_df(df)
            except Exception as error:
                print(f"Command failed: {error}")
        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Divvy Data Explorer Agent")
    parser.add_argument("command", nargs="?", help="Analysis command to run")
    parser.add_argument("--months", help="Comma-separated months to include (e.g. 202505,202506)")
    parser.add_argument("--limit", type=int, default=20, help="Limit for station/route results")
    parser.add_argument("--sql", help="Custom SQL query. Use {union_query} placeholder to inject the union of tables.")
    parser.add_argument("--interactive", action="store_true", help="Start interactive agent mode")
    parser.add_argument("--plot", help="Plot an analysis chart. Options: hourly, seasonal, stations, member_stations, distribution")
    parser.add_argument("--save", action="store_true", help="Save query results to CSV in analysis_outputs/")
    args = parser.parse_args()

    months = parse_months(args.months)

    if args.interactive or args.command is None:
        interactive_mode()
        return

    command = args.command.lower()
    try:
        if command == "quality":
            df = quality_check(months)
        elif command == "outliers":
            df = outlier_analysis(months)
        elif command == "business":
            df = business_summary(months)
        elif command == "conversion":
            df = conversion_analysis(months)
        elif command == "conversion_opportunity":
            df = conversion_opportunity(months)
        elif command == "operations":
            df = operational_summary(months)
        elif command == "risk":
            df = risk_summary(months)
        elif command == "weekday":
            df = weekday_weekend(months)
        elif command == "seasonal":
            df = seasonal_trends(months)
        elif command == "hourly":
            df = hourly_patterns(months)
        elif command == "stations":
            df = top_stations(months, limit=args.limit)
        elif command == "member_stations":
            df = member_stations(months, limit=args.limit)
        elif command == "rideable":
            df = rideable_type_breakdown(months)
        elif command == "routes":
            df = route_popularity(months, limit=args.limit)
        elif command == "distribution":
            df = duration_distribution(months)
        elif command == "preview":
            df = preview(months, limit=args.limit)
        elif command == "custom":
            if not args.sql:
                raise ValueError("Provide --sql when using the custom command.")
            df = custom_query(args.sql, months)
        else:
            raise ValueError(f"Unknown command '{command}'.")
    except Exception as error:
        print(f"Error: {error}")
        sys.exit(1)

    print_df(df)

    if args.save:
        save_dataframe(df, command)

    if args.plot:
        plot_command(args.plot, months, limit=args.limit)


if __name__ == "__main__":
    main()
