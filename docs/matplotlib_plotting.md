# Matplotlib: Plotting Patterns and Common Errors

## Standard figure/axes pattern
Always create a Figure and Axes explicitly rather than relying on the
implicit global state — this is essential when running headless (no
display), which is how this project's sandbox executes code:
```python
fig, ax = plt.subplots(figsize=(8, 5))
df.groupby('region')['revenue'].sum().plot(kind='bar', ax=ax)
ax.set_title('Revenue by Region')
```

## "RuntimeError: main thread is not in main loop" or blank charts
This happens when matplotlib tries to open an interactive display window
in an environment with no display (like a subprocess or server). Fix by
setting a non-interactive backend BEFORE importing pyplot:
```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
```

## Plotting a Series directly vs a DataFrame
```python
series.plot(kind='bar', ax=ax)       # Series -> single set of bars
dataframe.plot(kind='bar', ax=ax)    # DataFrame -> grouped/multi-series bars
```
If you get more or fewer bars than expected, check whether you're plotting
a Series (one column) or a full DataFrame (multiple columns).

## Line charts for trends
```python
fig, ax = plt.subplots(figsize=(10, 5))
df.plot(x='date', y='revenue', kind='line', ax=ax)
```
Requires `date` to already be a datetime dtype (see datetime handling docs)
for the x-axis to render in proper chronological order.

## Multiple series on one chart
```python
fig, ax = plt.subplots(figsize=(10, 5))
pivot = df.pivot_table(values='revenue', index='date', columns='region', aggfunc='sum')
pivot.plot(ax=ax)
```

## Heatmaps
```python
import seaborn as sns
fig, ax = plt.subplots(figsize=(8, 6))
pivot = df.pivot_table(values='revenue', index='region', columns='product', aggfunc='sum', fill_value=0)
sns.heatmap(pivot, annot=True, fmt='.0f', ax=ax, cmap='Blues')
```

## Common error: "no numeric data to plot"
This means you tried to plot a column that's still a string/object dtype
(often a date column that wasn't converted with `pd.to_datetime`, or a
column containing mixed text and numbers). Check `df.dtypes` before plotting.

## Rotating x-axis labels for readability
```python
plt.xticks(rotation=45)
plt.tight_layout()  # prevents labels from being cut off
```
