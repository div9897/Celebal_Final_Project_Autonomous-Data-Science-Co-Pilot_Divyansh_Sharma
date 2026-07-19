# Pandas: GroupBy and Aggregation

## Basic groupby + single aggregation
```python
df.groupby('region')['revenue'].sum()
```
Returns a Series indexed by `region`.

## Multiple aggregations at once
```python
df.groupby('region')['revenue'].agg(['sum', 'mean', 'count'])
```
Returns a DataFrame with one column per aggregation function.

## Aggregating multiple columns differently
```python
df.groupby('region').agg({
    'revenue': 'sum',
    'units_sold': 'mean'
})
```

## Common groupby errors

### "DataFrameGroupBy object has no attribute ..."
This happens when you call a method on the GroupBy object that doesn't exist,
or forget to select a column/aggregation first. Always follow `.groupby(...)`
with either a column selection (`['revenue']`) or an aggregation method
(`.sum()`, `.agg(...)`).

### Result has unexpected MultiIndex
Grouping by multiple columns produces a MultiIndex. To flatten it back into
regular columns for plotting or display:
```python
result = df.groupby(['region', 'product'])['revenue'].sum().reset_index()
```
`reset_index()` is the standard fix when a chart or downstream function
expects flat columns instead of a MultiIndex.

## Sorting groupby results
```python
df.groupby('region')['revenue'].sum().sort_values(ascending=False)
```
Note: `sort_values()` works on the resulting Series/DataFrame ONLY, not
inside the groupby call itself.

## Pivot tables (an alternative to groupby for 2D summaries)
```python
pivot = df.pivot_table(
    values='revenue',
    index='region',
    columns='product',
    aggfunc='sum',
    fill_value=0
)
```
`fill_value=0` prevents NaN values from appearing when a region/product
combination has no rows.
