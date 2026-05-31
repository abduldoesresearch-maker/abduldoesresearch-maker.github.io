import pandas as pd
import os

# ── Configuration ─────────────────────────────
DATA_DIR = r"C:\Users\abdul\bellabeat-case-study\data\raw"
OUTPUT_DIR = r"C:\Users\abdul\bellabeat-case-study\output"
PLOT_DIR = os.path.join(OUTPUT_DIR, "plots")

os.makedirs(PLOT_DIR, exist_ok=True)

# ── Load the 3 key datasets ───────────────────
print("Loading data...")

daily = pd.read_csv(os.path.join(DATA_DIR, "dailyActivity_merged.csv"))
sleep = pd.read_csv(os.path.join(DATA_DIR, "sleepDay_merged.csv"))
weight = pd.read_csv(os.path.join(DATA_DIR, "weightLogInfo_merged.csv"))

# ── Convert dates ─────────────────────────────
daily['ActivityDate'] = pd.to_datetime(daily['ActivityDate'])
sleep['SleepDay'] = pd.to_datetime(sleep['SleepDay'], format='mixed')
weight['Date'] = pd.to_datetime(weight['Date'], format='mixed')

# ── Quick profile ─────────────────────────────
print("\n── DAILY ACTIVITY ──────────────────────")
print(f"Rows: {len(daily)}")
print(f"Unique users: {daily['Id'].nunique()}")
print(f"Date range: {daily['ActivityDate'].min()} → {daily['ActivityDate'].max()}")
print(f"\nNulls per column:\n{daily.isnull().sum()}")
print(f"\nKey stats:")
print(daily[['TotalSteps','TotalDistance','SedentaryMinutes','Calories']].describe().round(1))

print("\n── SLEEP ───────────────────────────────")
print(f"Rows: {len(sleep)}")
print(f"Unique users: {sleep['Id'].nunique()}")
print(f"Nulls:\n{sleep.isnull().sum()}")

print("\n── WEIGHT ──────────────────────────────")
print(f"Rows: {len(weight)}")
print(f"Unique users: {weight['Id'].nunique()}")
print(f"Nulls:\n{weight.isnull().sum()}")

print("\n✅ Data loaded and profiled successfully")

# ══════════════════════════════════════════════
# PHASE 3: CLEAN
# ══════════════════════════════════════════════

print("\n── CLEANING ────────────────────────────")

# Remove duplicates
daily_clean = daily.drop_duplicates()
sleep_clean = sleep.drop_duplicates()
weight_clean = weight.drop_duplicates()

print(f"Daily rows after dedup: {len(daily_clean)} (removed {len(daily) - len(daily_clean)})")
print(f"Sleep rows after dedup: {len(sleep_clean)} (removed {len(sleep) - len(sleep_clean)})")
print(f"Weight rows after dedup: {len(weight_clean)} (removed {len(weight) - len(weight_clean)})")

# Add useful columns
daily_clean = daily_clean.copy()
daily_clean['TotalActiveMinutes'] = (
    daily_clean['VeryActiveMinutes'] +
    daily_clean['FairlyActiveMinutes'] +
    daily_clean['LightlyActiveMinutes']
)
daily_clean['DayOfWeek'] = daily_clean['ActivityDate'].dt.day_name()
daily_clean['WeekNumber'] = daily_clean['ActivityDate'].dt.isocalendar().week

# Add sleep efficiency
sleep_clean = sleep_clean.copy()
sleep_clean['SleepEfficiency'] = (
    sleep_clean['TotalMinutesAsleep'] /
    sleep_clean['TotalTimeInBed'] * 100
).round(1)

# Merge daily + sleep for combined analysis
merged = pd.merge(
    daily_clean,
    sleep_clean[['Id', 'SleepDay', 'TotalMinutesAsleep',
                 'TotalTimeInBed', 'SleepEfficiency']],
    left_on=['Id', 'ActivityDate'],
    right_on=['Id', 'SleepDay'],
    how='left'
)

print(f"\nMerged dataset: {len(merged)} rows")
print(f"Users with sleep data: {merged['TotalMinutesAsleep'].notna().sum()} days matched")

# Save cleaned files
daily_clean.to_csv(
    r"C:\Users\abdul\bellabeat-case-study\data\processed\daily_clean.csv",
    index=False
)
sleep_clean.to_csv(
    r"C:\Users\abdul\bellabeat-case-study\data\processed\sleep_clean.csv",
    index=False
)
merged.to_csv(
    r"C:\Users\abdul\bellabeat-case-study\data\processed\merged_daily_sleep.csv",
    index=False
)
print("\n✅ Cleaned files saved to processed folder")

# ══════════════════════════════════════════════
# PHASE 4: ANALYSE
# ══════════════════════════════════════════════

print("\n── ANALYSIS ────────────────────────────")

# 1. Activity level segmentation
print("\n1. USER ACTIVITY SEGMENTS")
daily_user = daily_clean.groupby('Id').agg(
    avg_steps=('TotalSteps', 'mean'),
    avg_calories=('Calories', 'mean'),
    avg_active_mins=('TotalActiveMinutes', 'mean'),
    avg_sedentary=('SedentaryMinutes', 'mean')
).round(1)

# Segment users by average steps
def segment(steps):
    if steps < 5000:   return 'Sedentary'
    elif steps < 7500: return 'Low Active'
    elif steps < 10000: return 'Fairly Active'
    else:              return 'Very Active'

daily_user['Segment'] = daily_user['avg_steps'].apply(segment)
print(daily_user['Segment'].value_counts())
print(f"\nAvg steps by segment:\n{daily_user.groupby('Segment')['avg_steps'].mean().round(0)}")

# 2. Day of week patterns
print("\n2. DAY OF WEEK PATTERNS")
day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
dow = daily_clean.groupby('DayOfWeek').agg(
    avg_steps=('TotalSteps', 'mean'),
    avg_calories=('Calories', 'mean'),
    avg_sedentary=('SedentaryMinutes', 'mean')
).round(1)
dow = dow.reindex(day_order)
print(dow)

# 3. Sleep analysis
print("\n3. SLEEP ANALYSIS")
print(f"Avg minutes asleep: {sleep_clean['TotalMinutesAsleep'].mean():.0f} ({sleep_clean['TotalMinutesAsleep'].mean()/60:.1f} hrs)")
print(f"Avg time in bed:    {sleep_clean['TotalTimeInBed'].mean():.0f} ({sleep_clean['TotalTimeInBed'].mean()/60:.1f} hrs)")
print(f"Avg sleep efficiency: {sleep_clean['SleepEfficiency'].mean():.1f}%")
print(f"Users sleeping < 7hrs: {(sleep_clean.groupby('Id')['TotalMinutesAsleep'].mean() < 420).sum()} of {sleep_clean['Id'].nunique()}")

# 4. Steps vs Calories correlation
print("\n4. STEPS vs CALORIES CORRELATION")
corr = daily_clean['TotalSteps'].corr(daily_clean['Calories'])
print(f"Correlation: {corr:.3f}")
print("(1.0 = perfect, 0 = no relationship)")

# 5. Feature usage summary
print("\n5. FEATURE ENGAGEMENT SUMMARY")
print(f"Activity tracking: {daily_clean['Id'].nunique()} users (100%)")
print(f"Sleep tracking:    {sleep_clean['Id'].nunique()} users ({sleep_clean['Id'].nunique()/daily_clean['Id'].nunique()*100:.0f}%)")
print(f"Weight logging:    {weight_clean['Id'].nunique()} users ({weight_clean['Id'].nunique()/daily_clean['Id'].nunique()*100:.0f}%)")

print("\n✅ Analysis complete")

# ══════════════════════════════════════════════
# PHASE 5: VISUALISATIONS
# ══════════════════════════════════════════════
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

plt.style.use('dark_background')
CORAL  = '#E8634A'
STEEL  = '#4A90C4'
GOLD   = '#F5A623'
GREEN  = '#00C896'
MUTED  = '#7A99C8'
BG     = '#162447'

# ── PLOT 1: Activity Segments ─────────────────
fig, ax = plt.subplots(figsize=(8, 5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

segments = daily_user['Segment'].value_counts()
seg_order = ['Sedentary', 'Low Active', 'Fairly Active', 'Very Active']
colors = [CORAL, GOLD, STEEL, GREEN]
vals = [segments.get(s, 0) for s in seg_order]

bars = ax.bar(seg_order, vals, color=colors, width=0.6, edgecolor='none')
for bar, val in zip(bars, vals):
    ax.text(bar.get_x() + bar.get_width()/2,
            bar.get_height() + 0.2,
            f'{val} users\n({val/33*100:.0f}%)',
            ha='center', va='bottom', fontsize=10, color='white')

ax.set_title('User Activity Segments', fontsize=14,
             fontweight='bold', color='white', pad=15)
ax.set_ylabel('Number of Users', color=MUTED)
ax.tick_params(colors='white')
ax.spines[:].set_visible(False)
ax.set_ylim(0, 13)
plt.tight_layout()
plt.savefig(r"C:\Users\abdul\bellabeat-case-study\output\plots\activity_segments.png",
            dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: activity_segments.png")

# ── PLOT 2: Day of Week Steps ─────────────────
fig, ax = plt.subplots(figsize=(10, 5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

day_colors = [CORAL if d == 'Sunday' else
              GOLD  if d == 'Monday' else
              STEEL for d in day_order]

bars = ax.bar(day_order, dow['avg_steps'],
              color=day_colors, width=0.6, edgecolor='none')

for bar, val in zip(bars, dow['avg_steps']):
    ax.text(bar.get_x() + bar.get_width()/2,
            bar.get_height() + 50,
            f'{val:,.0f}', ha='center', va='bottom',
            fontsize=9, color='white')

ax.axhline(10000, color=GREEN, linestyle='--',
           linewidth=1.2, label='WHO 10K target')
ax.axhline(dow['avg_steps'].mean(), color=GOLD,
           linestyle=':', linewidth=1, label='Weekly avg')

ax.set_title('Average Steps by Day of Week',
             fontsize=14, fontweight='bold', color='white', pad=15)
ax.set_ylabel('Average Steps', color=MUTED)
ax.tick_params(colors='white')
ax.spines[:].set_visible(False)
ax.legend(facecolor=BG, labelcolor='white', fontsize=9)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(
    lambda x, _: f'{int(x):,}'))
plt.tight_layout()
plt.savefig(r"C:\Users\abdul\bellabeat-case-study\output\plots\steps_by_day.png",
            dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: steps_by_day.png")

# ── PLOT 3: Sleep Distribution ────────────────
fig, ax = plt.subplots(figsize=(8, 5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

sleep_hrs = sleep_clean.groupby('Id')['TotalMinutesAsleep'].mean() / 60

ax.hist(sleep_hrs, bins=8, color=STEEL,
        edgecolor=BG, linewidth=2, alpha=0.9)
ax.axvline(7, color=CORAL, linestyle='--',
           linewidth=2, label='7hr minimum (NHS)')
ax.axvline(sleep_hrs.mean(), color=GOLD,
           linestyle=':', linewidth=1.5,
           label=f'Average: {sleep_hrs.mean():.1f}hrs')

ax.set_title('Average Sleep per User',
             fontsize=14, fontweight='bold', color='white', pad=15)
ax.set_xlabel('Hours of Sleep', color=MUTED)
ax.set_ylabel('Number of Users', color=MUTED)
ax.tick_params(colors='white')
ax.spines[:].set_visible(False)
ax.legend(facecolor=BG, labelcolor='white', fontsize=9)
plt.tight_layout()
plt.savefig(r"C:\Users\abdul\bellabeat-case-study\output\plots\sleep_distribution.png",
            dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: sleep_distribution.png")

# ── PLOT 4: Feature Engagement ────────────────
fig, ax = plt.subplots(figsize=(7, 5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

features = ['Activity\nTracking', 'Sleep\nTracking', 'Weight\nLogging']
users = [33, 24, 8]
pcts = [100, 73, 24]
colors = [GREEN, STEEL, CORAL]

bars = ax.bar(features, pcts, color=colors,
              width=0.5, edgecolor='none')
for bar, u, p in zip(bars, users, pcts):
    ax.text(bar.get_x() + bar.get_width()/2,
            bar.get_height() + 1.5,
            f'{u} users ({p}%)',
            ha='center', va='bottom',
            fontsize=10, color='white')

ax.set_title('Feature Engagement Rate',
             fontsize=14, fontweight='bold', color='white', pad=15)
ax.set_ylabel('% of Users', color=MUTED)
ax.set_ylim(0, 120)
ax.tick_params(colors='white')
ax.spines[:].set_visible(False)
plt.tight_layout()
plt.savefig(r"C:\Users\abdul\bellabeat-case-study\output\plots\feature_engagement.png",
            dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: feature_engagement.png")

# ── PLOT 5: Steps vs Calories Scatter ─────────
fig, ax = plt.subplots(figsize=(8, 5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

ax.scatter(daily_clean['TotalSteps'],
           daily_clean['Calories'],
           color=STEEL, alpha=0.4, s=20, edgecolors='none')

# Trend line
z = np.polyfit(daily_clean['TotalSteps'],
               daily_clean['Calories'], 1)
p = np.poly1d(z)
x_line = np.linspace(daily_clean['TotalSteps'].min(),
                     daily_clean['TotalSteps'].max(), 100)
ax.plot(x_line, p(x_line), color=GOLD,
        linewidth=2, label=f'Trend (r={corr:.2f})')

ax.set_title('Steps vs Calories Burned',
             fontsize=14, fontweight='bold', color='white', pad=15)
ax.set_xlabel('Total Steps', color=MUTED)
ax.set_ylabel('Calories Burned', color=MUTED)
ax.tick_params(colors='white')
ax.spines[:].set_visible(False)
ax.legend(facecolor=BG, labelcolor='white', fontsize=9)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(
    lambda x, _: f'{int(x):,}'))
plt.tight_layout()
plt.savefig(r"C:\Users\abdul\bellabeat-case-study\output\plots\steps_vs_calories.png",
            dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: steps_vs_calories.png")

print("\n✅ All 5 plots saved to output/plots/")

# ══════════════════════════════════════════════
# DEEPER ANALYSIS
# ══════════════════════════════════════════════

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

print("\n── DEEPER ANALYSIS ─────────────────────")

# ── LOAD HOURLY DATA ──────────────────────────
hourly_steps = pd.read_csv(
    os.path.join(DATA_DIR, "hourlySteps_merged.csv"))
hourly_cal = pd.read_csv(
    os.path.join(DATA_DIR, "hourlyCalories_merged.csv"))

hourly_steps['ActivityHour'] = pd.to_datetime(
    hourly_steps['ActivityHour'], format='mixed')
hourly_cal['ActivityHour'] = pd.to_datetime(
    hourly_cal['ActivityHour'], format='mixed')

hourly_steps['Hour'] = hourly_steps['ActivityHour'].dt.hour
hourly_cal['Hour'] = hourly_cal['ActivityHour'].dt.hour

# ══════════════════════════════════════════════
# ANALYSIS 1: TIME OF DAY PATTERNS
# ══════════════════════════════════════════════
print("\n1. TIME OF DAY PATTERNS")

hourly_avg_steps = hourly_steps.groupby('Hour')['StepTotal'].mean().round(1)
hourly_avg_cal = hourly_cal.groupby('Hour')['Calories'].mean().round(1)

peak_step_hour = hourly_avg_steps.idxmax()
peak_cal_hour = hourly_avg_cal.idxmax()

print(f"Peak activity hour (steps): {peak_step_hour}:00")
print(f"Peak calorie burn hour:     {peak_cal_hour}:00")
print(f"Least active hour:          {hourly_avg_steps.idxmin()}:00")
print(f"\nTop 3 most active hours:")
print(hourly_avg_steps.nlargest(3))

# Plot
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
fig.patch.set_facecolor(BG)
fig.suptitle('Activity Patterns by Hour of Day',
             fontsize=14, fontweight='bold',
             color='white', y=0.98)

hours = list(range(24))
step_colors = [GOLD if h == peak_step_hour else
               CORAL if h < 6 else STEEL for h in hours]

ax1.set_facecolor(BG)
ax1.bar(hours, hourly_avg_steps, color=step_colors,
        width=0.8, edgecolor='none')
ax1.axvspan(7, 9, alpha=0.12, color=GOLD, label='Morning peak')
ax1.axvspan(17, 19, alpha=0.12, color=GREEN, label='Evening peak')
ax1.set_ylabel('Avg Steps', color=MUTED)
ax1.set_title('Average Steps by Hour', color='white',
              fontsize=11, pad=8)
ax1.tick_params(colors='white')
ax1.spines[:].set_visible(False)
ax1.legend(facecolor=BG, labelcolor='white', fontsize=8)
ax1.annotate(f'Peak: {peak_step_hour}:00',
             xy=(peak_step_hour,
                 hourly_avg_steps[peak_step_hour]),
             xytext=(peak_step_hour + 1.5,
                     hourly_avg_steps[peak_step_hour] * 0.9),
             color=GOLD, fontsize=9,
             arrowprops=dict(arrowstyle='->',
                             color=GOLD, lw=1.2))

ax2.set_facecolor(BG)
ax2.plot(hours, hourly_avg_cal, color=CORAL,
         linewidth=2.5, marker='o', markersize=4)
ax2.fill_between(hours, hourly_avg_cal,
                 alpha=0.15, color=CORAL)
ax2.axvspan(7, 9, alpha=0.12, color=GOLD)
ax2.axvspan(17, 19, alpha=0.12, color=GREEN)
ax2.set_ylabel('Avg Calories', color=MUTED)
ax2.set_xlabel('Hour of Day', color=MUTED)
ax2.set_title('Average Calories Burned by Hour',
              color='white', fontsize=11, pad=8)
ax2.tick_params(colors='white')
ax2.spines[:].set_visible(False)
ax2.set_xticks(hours)
ax2.set_xticklabels([
    '12am' if h == 0 else f'{h}am' if h < 12
    else '12pm' if h == 12 else f'{h-12}pm'
    for h in hours], rotation=45, fontsize=8)

plt.tight_layout()
plt.savefig(r"C:\Users\abdul\bellabeat-case-study\output\plots\hourly_patterns.png",
            dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: hourly_patterns.png")

# ══════════════════════════════════════════════
# ANALYSIS 2: SLEEP VS ACTIVITY CORRELATION
# ══════════════════════════════════════════════
print("\n2. SLEEP VS ACTIVITY CORRELATION")

# Merge user averages
user_activity = daily_clean.groupby('Id').agg(
    avg_steps=('TotalSteps', 'mean'),
    avg_active_mins=('TotalActiveMinutes', 'mean'),
    avg_sedentary=('SedentaryMinutes', 'mean'),
    avg_calories=('Calories', 'mean')
).round(1)

user_sleep = sleep_clean.groupby('Id').agg(
    avg_sleep_hrs=('TotalMinutesAsleep',
                   lambda x: round(x.mean()/60, 2)),
    avg_efficiency=('SleepEfficiency', 'mean')
).round(2)

sleep_activity = user_activity.join(
    user_sleep, how='inner')

corr_sleep_steps = sleep_activity['avg_sleep_hrs'].corr(
    sleep_activity['avg_steps'])
corr_sleep_active = sleep_activity['avg_sleep_hrs'].corr(
    sleep_activity['avg_active_mins'])
corr_sleep_sedentary = sleep_activity['avg_sleep_hrs'].corr(
    sleep_activity['avg_sedentary'])

print(f"Sleep vs Steps correlation:          {corr_sleep_steps:.3f}")
print(f"Sleep vs Active Minutes correlation: {corr_sleep_active:.3f}")
print(f"Sleep vs Sedentary correlation:      {corr_sleep_sedentary:.3f}")

# Segment by sleep
sleep_activity['SleepGroup'] = pd.cut(
    sleep_activity['avg_sleep_hrs'],
    bins=[0, 6, 7, 8, 24],
    labels=['< 6hrs', '6-7hrs', '7-8hrs', '> 8hrs']
)

print("\nAvg steps by sleep group:")
print(sleep_activity.groupby(
    'SleepGroup', observed=True)['avg_steps'].mean().round(0))

# Plot
fig, axes = plt.subplots(1, 3, figsize=(14, 5))
fig.patch.set_facecolor(BG)
fig.suptitle('Sleep vs Physical Activity',
             fontsize=14, fontweight='bold',
             color='white', y=1.02)

pairs = [
    ('avg_steps', 'Steps', STEEL, corr_sleep_steps),
    ('avg_active_mins', 'Active Minutes', GREEN,
     corr_sleep_active),
    ('avg_sedentary', 'Sedentary Minutes', CORAL,
     corr_sleep_sedentary)
]

for ax, (col, label, color, corr_val) in zip(axes, pairs):
    ax.set_facecolor(BG)
    ax.scatter(sleep_activity['avg_sleep_hrs'],
               sleep_activity[col],
               color=color, s=80, alpha=0.8,
               edgecolors='white', linewidth=0.5)

    z = np.polyfit(sleep_activity['avg_sleep_hrs'],
                   sleep_activity[col], 1)
    p = np.poly1d(z)
    x_line = np.linspace(
        sleep_activity['avg_sleep_hrs'].min(),
        sleep_activity['avg_sleep_hrs'].max(), 50)
    ax.plot(x_line, p(x_line), color='white',
            linewidth=1.5, linestyle='--', alpha=0.5)

    ax.set_title(f'Sleep vs {label}\nr={corr_val:.2f}',
                 color='white', fontsize=10)
    ax.set_xlabel('Avg Sleep (hrs)', color=MUTED,
                  fontsize=9)
    ax.set_ylabel(label, color=MUTED, fontsize=9)
    ax.tick_params(colors='white', labelsize=8)
    ax.spines[:].set_visible(False)

plt.tight_layout()
plt.savefig(
    r"C:\Users\abdul\bellabeat-case-study\output\plots\sleep_vs_activity.png",
    dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: sleep_vs_activity.png")

# ══════════════════════════════════════════════
# ANALYSIS 3: USER CONSISTENCY
# ══════════════════════════════════════════════
print("\n3. USER CONSISTENCY")

user_days = daily_clean.groupby('Id').size().reset_index(
    name='days_tracked')
user_days['consistency_pct'] = (
    user_days['days_tracked'] / 31 * 100).round(1)

print(f"Max days tracked:  {user_days['days_tracked'].max()}")
print(f"Min days tracked:  {user_days['days_tracked'].min()}")
print(f"Avg days tracked:  {user_days['days_tracked'].mean():.1f}")
print(f"\nUsers tracking all 31 days: "
      f"{(user_days['days_tracked'] == 31).sum()}")
print(f"Users tracking < 20 days:   "
      f"{(user_days['days_tracked'] < 20).sum()}")
print(f"Users tracking < 10 days:   "
      f"{(user_days['days_tracked'] < 10).sum()}")

# Consistency segments
user_days['consistency_group'] = pd.cut(
    user_days['days_tracked'],
    bins=[0, 10, 20, 25, 31],
    labels=['Low\n(≤10 days)', 'Moderate\n(11-20)',
            'High\n(21-25)', 'Full\n(26-31)']
)
consistency_counts = user_days['consistency_group'].value_counts()

# Plot
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
fig.patch.set_facecolor(BG)
fig.suptitle('User Tracking Consistency (31-Day Period)',
             fontsize=14, fontweight='bold', color='white')

# Bar chart
ax1.set_facecolor(BG)
groups = ['Low\n(≤10 days)', 'Moderate\n(11-20)',
          'High\n(21-25)', 'Full\n(26-31)']
colors = [CORAL, GOLD, STEEL, GREEN]
vals = [consistency_counts.get(g, 0) for g in groups]
bars = ax1.bar(groups, vals, color=colors,
               width=0.6, edgecolor='none')
for bar, val in zip(bars, vals):
    ax1.text(bar.get_x() + bar.get_width()/2,
             bar.get_height() + 0.15,
             f'{val} users', ha='center',
             color='white', fontsize=10)
ax1.set_ylabel('Number of Users', color=MUTED)
ax1.set_title('Users by Tracking Consistency',
              color='white', fontsize=11)
ax1.tick_params(colors='white')
ax1.spines[:].set_visible(False)
ax1.set_ylim(0, max(vals) + 3)

# Histogram of days tracked
ax2.set_facecolor(BG)
ax2.hist(user_days['days_tracked'], bins=10,
         color=STEEL, edgecolor=BG, linewidth=1.5)
ax2.axvline(user_days['days_tracked'].mean(),
            color=GOLD, linestyle='--', linewidth=2,
            label=f"Avg: {user_days['days_tracked'].mean():.0f} days")
ax2.set_xlabel('Days Tracked', color=MUTED)
ax2.set_ylabel('Number of Users', color=MUTED)
ax2.set_title('Distribution of Days Tracked',
              color='white', fontsize=11)
ax2.tick_params(colors='white')
ax2.spines[:].set_visible(False)
ax2.legend(facecolor=BG, labelcolor='white', fontsize=9)

plt.tight_layout()
plt.savefig(
    r"C:\Users\abdul\bellabeat-case-study\output\plots\user_consistency.png",
    dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: user_consistency.png")

# ══════════════════════════════════════════════
# ANALYSIS 4: SEDENTARY BEHAVIOUR DEEP DIVE
# ══════════════════════════════════════════════
print("\n4. SEDENTARY BEHAVIOUR DEEP DIVE")

daily_clean['SedentaryHours'] = (
    daily_clean['SedentaryMinutes'] / 60).round(1)
daily_clean['ActivePct'] = (
    daily_clean['TotalActiveMinutes'] /
    (daily_clean['TotalActiveMinutes'] +
     daily_clean['SedentaryMinutes']) * 100).round(1)

print(f"Avg sedentary hours per day: "
      f"{daily_clean['SedentaryHours'].mean():.1f}")
print(f"Avg active percentage:       "
      f"{daily_clean['ActivePct'].mean():.1f}%")
print(f"Days with > 20 sedentary hrs:"
      f" {(daily_clean['SedentaryHours'] > 20).sum()}")
print(f"Days with < 8 sedentary hrs: "
      f"{(daily_clean['SedentaryHours'] < 8).sum()}")

# By user segment
seg_sedentary = daily_clean.groupby(
    daily_clean['Id'].map(
        daily_user['Segment']))['SedentaryHours'].mean().round(1)
print(f"\nAvg sedentary hours by segment:\n{seg_sedentary}")

# Active minutes breakdown
print(f"\nAvg Very Active mins:    "
      f"{daily_clean['VeryActiveMinutes'].mean():.1f}")
print(f"Avg Fairly Active mins:  "
      f"{daily_clean['FairlyActiveMinutes'].mean():.1f}")
print(f"Avg Lightly Active mins: "
      f"{daily_clean['LightlyActiveMinutes'].mean():.1f}")
print(f"Avg Sedentary mins:      "
      f"{daily_clean['SedentaryMinutes'].mean():.1f}")

# Plot — stacked time breakdown
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
fig.patch.set_facecolor(BG)
fig.suptitle('How Users Spend Their Day',
             fontsize=14, fontweight='bold', color='white')

# Pie chart of avg time breakdown
ax1.set_facecolor(BG)
avg_times = [
    daily_clean['VeryActiveMinutes'].mean(),
    daily_clean['FairlyActiveMinutes'].mean(),
    daily_clean['LightlyActiveMinutes'].mean(),
    daily_clean['SedentaryMinutes'].mean()
]
labels = ['Very Active', 'Fairly Active',
          'Lightly Active', 'Sedentary']
colors_pie = [GREEN, STEEL, GOLD, CORAL]
explode = (0, 0, 0, 0.05)
wedges, texts, autotexts = ax1.pie(
    avg_times, labels=labels, colors=colors_pie,
    autopct='%1.1f%%', explode=explode,
    textprops={'color': 'white', 'fontsize': 9},
    wedgeprops={'edgecolor': BG, 'linewidth': 2})
for at in autotexts:
    at.set_color('white')
    at.set_fontsize(9)
ax1.set_title('Average Daily Time Distribution',
              color='white', fontsize=11, pad=15)

# Sedentary hours distribution
ax2.set_facecolor(BG)
ax2.hist(daily_clean['SedentaryHours'], bins=12,
         color=CORAL, edgecolor=BG, linewidth=1.5,
         alpha=0.9)
ax2.axvline(daily_clean['SedentaryHours'].mean(),
            color=GOLD, linestyle='--', linewidth=2,
            label=f"Avg: {daily_clean['SedentaryHours'].mean():.1f}hrs")
ax2.axvline(16, color=GREEN, linestyle=':',
            linewidth=1.5, label='16hrs = concern threshold')
ax2.set_xlabel('Sedentary Hours per Day', color=MUTED)
ax2.set_ylabel('Number of Days', color=MUTED)
ax2.set_title('Sedentary Hours Distribution',
              color='white', fontsize=11)
ax2.tick_params(colors='white')
ax2.spines[:].set_visible(False)
ax2.legend(facecolor=BG, labelcolor='white', fontsize=9)

plt.tight_layout()
plt.savefig(
    r"C:\Users\abdul\bellabeat-case-study\output\plots\sedentary_deepdive.png",
    dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: sedentary_deepdive.png")

print("\n✅ All deeper analyses complete")
print(f"Total plots saved: 9")

# ══════════════════════════════════════════════
# BONUS: INTENSITY VS STEPS — WHICH PREDICTS
# CALORIE BURN BETTER?
# ══════════════════════════════════════════════
print("\n── INTENSITY VS STEPS ANALYSIS ─────────")

# Correlations with calories
corr_steps_cal = daily_clean['TotalSteps'].corr(
    daily_clean['Calories'])
corr_active_cal = daily_clean['TotalActiveMinutes'].corr(
    daily_clean['Calories'])
corr_very_active_cal = daily_clean['VeryActiveMinutes'].corr(
    daily_clean['Calories'])
corr_sedentary_cal = daily_clean['SedentaryMinutes'].corr(
    daily_clean['Calories'])

print(f"Steps vs Calories:              {corr_steps_cal:.3f}")
print(f"Total Active Mins vs Calories:  {corr_active_cal:.3f}")
print(f"Very Active Mins vs Calories:   {corr_very_active_cal:.3f}")
print(f"Sedentary Mins vs Calories:     {corr_sedentary_cal:.3f}")

# Which is the strongest predictor?
predictors = {
    'Steps':             corr_steps_cal,
    'Total Active Mins': corr_active_cal,
    'Very Active Mins':  corr_very_active_cal,
    'Sedentary Mins':    corr_sedentary_cal
}
best = max(predictors, key=lambda k: abs(predictors[k]))
print(f"\n✅ Strongest predictor of calories: {best}")
print(f"   Correlation: {predictors[best]:.3f}")

# Plot — 4 scatter plots side by side
fig, axes = plt.subplots(1, 4, figsize=(16, 5))
fig.patch.set_facecolor(BG)
fig.suptitle('What Predicts Calorie Burn?',
             fontsize=14, fontweight='bold',
             color='white', y=1.02)

pairs = [
    ('TotalSteps', 'Total Steps',
     STEEL, corr_steps_cal),
    ('TotalActiveMinutes', 'Active Minutes',
     GREEN, corr_active_cal),
    ('VeryActiveMinutes', 'Very Active Mins',
     GOLD, corr_very_active_cal),
    ('SedentaryMinutes', 'Sedentary Mins',
     CORAL, corr_sedentary_cal)
]

for ax, (col, label, color, corr_val) in zip(axes, pairs):
    ax.set_facecolor(BG)
    ax.scatter(daily_clean[col],
               daily_clean['Calories'],
               color=color, alpha=0.35,
               s=15, edgecolors='none')

    # Trend line
    z = np.polyfit(daily_clean[col],
                   daily_clean['Calories'], 1)
    p = np.poly1d(z)
    x_line = np.linspace(
        daily_clean[col].min(),
        daily_clean[col].max(), 100)
    ax.plot(x_line, p(x_line),
            color='white', linewidth=1.8,
            linestyle='--', alpha=0.7)

    # Colour code by strength
    strength = abs(corr_val)
    if strength > 0.6:
        badge = '★ Strong'
        badge_col = GREEN
    elif strength > 0.4:
        badge = '◆ Moderate'
        badge_col = GOLD
    else:
        badge = '~ Weak'
        badge_col = CORAL

    ax.set_title(f'{label}\nr={corr_val:.2f}  {badge}',
                 color=badge_col, fontsize=9,
                 fontweight='bold')
    ax.set_xlabel(label, color=MUTED, fontsize=8)
    ax.set_ylabel('Calories' if ax == axes[0] else '',
                  color=MUTED, fontsize=8)
    ax.tick_params(colors='white', labelsize=7)
    ax.spines[:].set_visible(False)

plt.tight_layout()
plt.savefig(
    r"C:\Users\abdul\bellabeat-case-study\output\plots\calorie_predictors.png",
    dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print("✅ Saved: calorie_predictors.png")

print("\n" + "="*50)
print("FINAL INSIGHT SUMMARY")
print("="*50)
print(f"1. 51% of users are sedentary or low active")
print(f"2. Peak activity hour: 6pm — time notifications here")
print(f"3. 54% sleep under 7 hours — sleep coaching needed")
print(f"4. 16.5hrs sedentary daily — movement reminders critical")
print(f"5. Monday most sedentary — target Monday campaigns")
print(f"6. 88% track consistently — app is sticky")
print(f"7. Weight logging 76% dropout — automate tracking")
print(f"8. Best calorie predictor: {best} (r={predictors[best]:.2f})")
print("="*50)
print("\n✅ Full analysis complete — ready for presentation")