# Pandas: KeyError and Column Access

## KeyError on column access
A `KeyError` when doing `df['column_name']` or `df.groupby('column_name')` almost
always means the column name doesn't match exactly. Common causes:
- Case mismatch: `'Region'` vs `'region'`
- Extra whitespace: `'region '` vs `'region'`
- Typo in the column name

## How to check available columns
Always verify column names before referencing them:
```python
print(df.columns.tolist())
```

## Safe column access pattern
Instead of assuming a column exists, check first:
```python
if 'region' in df.columns:
    result = df.groupby('region')['revenue'].sum()
else:
    raise ValueError(f"Expected 'region' column, found: {df.columns.tolist()}")
```

## KeyError in groupby with multiple columns
When grouping by multiple columns, pass a list:
```python
df.groupby(['region', 'product'])['revenue'].sum()
```
Passing a single string when you meant multiple columns, or vice versa, is a
common source of KeyError or unexpected output shape.

## .loc vs .iloc
- `.loc[]` is label-based (uses column/index names)
- `.iloc[]` is position-based (uses integer positions)
Mixing them up causes `KeyError` (using .loc with an integer that isn't a valid
label) or `IndexError` (using .iloc with an out-of-range position).
