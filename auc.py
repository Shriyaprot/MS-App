def calculate_area(df, x_start, x_end):
    df_range = df[
        (df['x'] >= x_start) &
        (df['x'] <= x_end)
    ]

    if len(df_range) == 0:
        return 0

    area = trapezoid(
        df_range['y'],
        df_range['x']
    )

    return area if not np.isnan(area) else 0
