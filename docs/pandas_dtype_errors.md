# Pandas: Dtype and Type Conversion Errors

## TypeError: unsupported operand type(s)
Usually means you're trying to do math (`+`, `-`, `sum()`, `mean()`) on a
column that's actually stored as text (`object` dtype), even if it looks
numeric. Check dtypes first:
```python
print(df.dtypes)
```

## Converting a column to numeric
```python
df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce')
```
`errors='coerce'` turns any values that can't be converted into `NaN`
instead of raising an exception — useful for messy real-world data, but
be aware it can silently introduce missing values. Check afterward:
```python
print(df['revenue'].isna().sum())
```

## ValueError: could not convert string to float
This happens when a numeric-looking column actually contains non-numeric
characters, e.g. `"$1,200"` or `"12500 USD"`. Clean the string first:
```python
df['revenue'] = df['revenue'].str.replace('$', '').str.replace(',', '')
df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce')
```

## AttributeError: 'Series' object has no attribute 'X'
Usually means one of two things:
1. You called a `.str` or `.dt` method on a column of the wrong dtype
   (e.g. `.str.upper()` on a numeric column)
2. You misspelled the method name

## Checking for and handling missing values
```python
df.isnull().sum()          # count of missing values per column
df.dropna(subset=['revenue'])   # drop rows missing this specific column
df.fillna(0)                    # replace missing values with 0
```

## Checking for duplicate rows
```python
duplicate_count = df.duplicated().sum()
df_deduped = df.drop_duplicates()
```

## Detecting outliers with the IQR method
A standard, simple approach for flagging outliers in a numeric column:
```python
Q1 = df['monthly_spend'].quantile(0.25)
Q3 = df['monthly_spend'].quantile(0.75)
IQR = Q3 - Q1
lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR
outliers = df[(df['monthly_spend'] < lower_bound) | (df['monthly_spend'] > upper_bound)]
```
Values outside `[lower_bound, upper_bound]` are considered outliers under this
convention (1.5x IQR is the standard multiplier; some analyses use 3x for a
stricter "extreme outlier" definition).

## Data quality audit pattern (combining the above)
A typical "audit this data" request should check, at minimum:
```python
missing = df.isnull().sum()
duplicates = df.duplicated().sum()
# then run the IQR check above on each numeric column of interest
```
Report all three (missing values per column, duplicate row count, and any
outlier rows found) rather than just one.
