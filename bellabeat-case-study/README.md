# Bellabeat App Marketing Strategy
### Google Data Analytics Certificate — Case Study 02

A data analysis project examining smart device usage trends from FitBit fitness tracker data to inform Bellabeat's app marketing strategy.

---

## Business Task

Analyse smart device usage data to identify behavioural trends that can guide Bellabeat's marketing strategy for their app — with a focus on how people use health tracking devices and what this reveals about user needs.

**Key questions:**
- What are the trends in smart device usage?
- How could these trends apply to Bellabeat app users?
- How could these trends influence Bellabeat's marketing strategy?

**Stakeholders:** Urška Sršen (Co-founder & CCO), Sando Mur (Co-founder), Bellabeat marketing analytics team

---

## Dataset

**Source:** [FitBit Fitness Tracker Data](https://www.kaggle.com/datasets/arashnic/fitbit) — Kaggle (CC0 Public Domain)

| File | Rows | Description |
|---|---|---|
| dailyActivity_merged.csv | 940 | Steps, distance, active minutes, calories per user per day |
| sleepDay_merged.csv | 413 | Sleep duration and time in bed per user per night |
| weightLogInfo_merged.csv | 67 | Weight and BMI entries |
| hourlySteps_merged.csv | — | Step counts by hour of day |
| hourlyCalories_merged.csv | — | Calorie burn by hour of day |

**Limitations:** 33 users tracked over 31 days (April–May 2016). Small sample size — findings are directional, not statistically representative.

---

## Tools Used

| Tool | Purpose | Why it was chosen |
|---|---|---|
| Excel | Initial data profiling and exploration | Fastest for visual inspection of small files |
| Python + Pandas | Data cleaning and analysis | Better for multi-file joins and statistical analysis |
| Matplotlib | Data visualisation | Sufficient for clean, consistent charts |
| PowerPoint | Executive presentation | Best format for stakeholder communication |

**Tool elimination story:** Excel was used first for rapid profiling but eliminated once the analysis required joining multiple files and computing correlations across datasets. Python handled everything from that point forward.

---

## Key Findings

| # | Finding | Implication |
|---|---|---|
| 1 | 81% of the day is sedentary (avg 16.5 hrs) | Movement reminders are the #1 opportunity |
| 2 | Peak activity hits at 6pm, not morning | Time campaigns and notifications for 5–7pm |
| 3 | 54% of users sleep under 7 hours | Sleep coaching is an untapped feature gap |
| 4 | Very Active Minutes (r=0.62) predicts calorie burn better than steps (r=0.59) | Market intensity, not step count |
| 5 | Even Very Active users average 16.2 sedentary hours | Short workouts don't offset 16 hours of sitting |
| 6 | Activity tracking retains 100% of users; weight logging retains only 24% | Friction kills adoption — automate everything |
| 7 | 88% of users tracked for 26+ of 31 days | The app creates genuine daily habits |
| 8 | Monday is the most sedentary day (1,028 avg sedentary mins) | Monday morning campaigns are a prime opportunity |

---

## Recommendations

**01 — Launch Hourly Movement Reminders**
Users sit for 81% of the day. Smart movement prompts every 60–90 minutes directly address the #1 health gap. Position as *Bellabeat Balance* — your companion for a more active day.

**02 — Time All Campaigns for 5–7pm**
Peak steps and calorie burn happen at 6pm — not morning. Run challenges, push notifications, and paid campaigns in this window. Target Monday mornings specifically for sedentary intervention.

**03 — Build a Sleep Coaching Feature**
Over half of users sleep under 7 hours — an underserved need in the current app. Bedtime reminders, wind-down routines, and a sleep score would differentiate Bellabeat. Market as a women's recovery and energy tool.

**04 — Market Intensity — Not Just Steps**
Very Active Minutes is the strongest predictor of calorie burn. Reframe app messaging: *"20 intense minutes beats 8,000 casual steps."* Add an intensity score to the daily dashboard.

---

## Files in This Repository

```
bellabeat-case-study/
├── bellabeat_analysis.py      # Full Python analysis script
├── Bellabeat_Case_Study.pptx  # Executive presentation (10 slides)
├── activity_segments.png      # User activity segmentation chart
├── steps_by_day.png           # Average steps by day of week
├── sleep_distribution.png     # Sleep duration histogram
├── feature_engagement.png     # Feature usage funnel
├── steps_vs_calories.png      # Steps vs calorie burn scatter
├── hourly_patterns.png        # Activity patterns by hour of day
├── sleep_vs_activity.png      # Sleep vs physical activity correlations
├── user_consistency.png       # Tracking consistency over 31 days
├── sedentary_deepdive.png     # Sedentary behaviour analysis
└── calorie_predictors.png     # Comparing calorie burn predictors
```

---

## How to Run the Analysis

**Requirements:**
```
pip install pandas matplotlib numpy
```

**Run:**
```bash
cd bellabeat-case-study
python bellabeat_analysis.py
```

**Output:** Analysis results printed to console. Charts saved to `output/plots/`. Cleaned data saved to `data/processed/`.

> **Note:** Update the `DATA_DIR` path in `bellabeat_analysis.py` to point to your local copy of the FitBit dataset before running.

---

## Further Analysis Opportunities

- Weekend vs weekday behaviour by activity segment
- Profile of users who log weight vs those who don't
- Seasonal activity trends (this dataset covers only one month)
- Correlating sleep quality with activity intensity

---

## Presentation
[View the full presentation with speaker notes on Google Slides](https://docs.google.com/presentation/d/1j6CMdKemzKOC3nSjesqWyezLS95Poz0ZkA37ar2hXZE/edit?usp=sharing)


---

*Analysed by Abdul · Tools: Python · Pandas · Matplotlib · Excel · FitBit Dataset via Kaggle*
