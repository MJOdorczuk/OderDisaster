def calculate_ndci(profile, median_window=51):
    ndci = (profile["B05 VNIR"] - profile["B04 Red"]) / (profile["B05 VNIR"] + profile["B04 Red"])
    profile["NDCI"] = ndci
    profile["local median NDCI"] = (
        profile["NDCI"]
        .rolling(window=median_window, center=True, min_periods=1)
        .median()
    )