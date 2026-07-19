# Pandas: Datetime Handling

## The #1 datetime mistake
When a CSV is loaded, date columns come in as plain strings (`object` dtype),
NOT as actual datetime objects — even if they look like dates. You must
convert them explicitly:
```python
df['date'] = pd.to_datetime(df['date'])
```
Trying to use `.dt` accessor methods (`.dt.month`, `.dt.year`, etc.) on a
string column raises:
```
AttributeError: Can only use .dt accessor with datetimelike values
```
The fix is always to run `pd.to_datetime()` on the column first.

## Extracting date parts
Once converted:
```python
df['month'] = df['date'].dt.month
df['year'] = df['date'].dt.year
df['day_of_week'] = df['date'].dt.day_name()
```

## Grouping by month/period
```python
df['date'] = pd.to_datetime(df['date'])
monthly = df.groupby(df['date'].dt.to_period('M'))['revenue'].sum()
```
`.dt.to_period('M')` groups all dates within the same month together,
regardless of the day.

## Sorting by date
Always sort chronologically before computing trends, rolling averages, or
percentage changes:
```python
df = df.sort_values('date')
```
If this step is skipped, trend calculations (like `.pct_change()` or
`.rolling()`) will be computed against rows in the wrong order and produce
misleading results.

## Common trend calculations
```python
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date')
df['pct_change'] = df['revenue'].pct_change()
df['rolling_avg'] = df['revenue'].rolling(window=3).mean()
```
`rolling(window=3)` computes a 3-period moving average; the first `window-1`
rows will be `NaN` since there isn't enough prior data yet — this is expected
behavior, not a bug.

## Parsing errors
If dates are in a non-standard format, specify it explicitly:
```python
df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y')
```
Without this, `pd.to_datetime` guesses the format and can misinterpret
day/month order (e.g. `03/04/2025` as March 4th vs April 3rd).
