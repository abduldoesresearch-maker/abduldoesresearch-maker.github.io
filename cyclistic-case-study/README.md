# abduldoesresearch-maker.github.io
Data Analytics Portfolio
# Cyclistic Bike-Share Case Study

## Overview
Analysis of 5.7 million bike rides to understand how casual riders and 
annual members use Cyclistic bikes differently — and identify strategies 
to convert casual riders into members.

**Tools used:** Python · BigQuery · SQL · PowerPoint  
**Data:** 12 months of Cyclistic trip data (May 2025 – Apr 2026)  
**Rides analysed:** 5,697,455

---

## Key Findings

### 1. Ride Duration Gap
Casual riders average **22.4 minutes** per ride vs **12.4 minutes** 
for members — nearly twice as long. This gap holds across every season.

### 2. Commuter vs Leisure Pattern
Members dominate weekday rides (2.8M vs 1.3M for casuals). Casuals 
peak on weekends. Members ride consistently every day — casuals ride 
longer when they have free time.

### 3. Seasonal Drop
Casual ridership drops **82%** from summer peak to winter. Members 
drop only 64% — they have built cycling into their daily routine 
regardless of weather.

### 4. Station Patterns
Casuals cluster at tourist spots — Navy Pier, Millennium Park, 
Shedd Aquarium. Members cluster at transit and office corridors — 
Kingsbury St, Canal St, Clinton St.

### 5. Conversion Opportunity
**543,008 casual rides** show all three commuter signals — weekday, 
commute hours, and under 30 minutes. These are the highest-priority 
conversion targets.

---

## Recommendations

1. **Target commute-hour casuals** — Run digital ads at lakefront 
stations on weekday mornings targeting the 607,562 rides happening 
during commute hours
2. **Show the savings** — Casuals ride 22.4 min avg, well within 
membership value range. A side-by-side cost comparison drives conversion
3. **Campaign timing** — Launch in August before casual ridership 
collapses. A late-summer trial offer creates urgency

---

## Files

| File | Description |
|------|-------------|
| `data_explorer_agent.py` | Interactive Python agent for BigQuery analysis |
| `Cyclistic_Case_Study.pptx` | Executive presentation deck |
| `hourly_patterns.png` | Ride volume by hour of day |
| `seasonal_trends.png` | Seasonal ridership comparison |
| `member_stations.png` | Top stations by rider type |
| `duration_distribution.png` | Ride length distribution |
| `top_stations.png` | Overall top start stations |

---

## How to Run the Analysis Agent

```bash
# Install dependencies
pip install pandas google-cloud-bigquery matplotlib seaborn

# Run interactive mode
python data_explorer_agent.py --interactive

# Available commands
agent> business       # Overall ride summary
agent> weekday        # Weekday vs weekend patterns  
agent> seasonal       # Seasonal trends
agent> hourly         # Hourly ride patterns
agent> member_stations # Top stations by rider type
agent> conversion     # Conversion opportunity analysis
```
## Presentation
[View the full presentation with speaker notes on Google Slides](https://docs.google.com/presentation/d/1QhOgCZR4R2Yzzqz89Ny6BTDqDw6A9qrE7MrnqS8eP5g/edit?usp=sharing)
