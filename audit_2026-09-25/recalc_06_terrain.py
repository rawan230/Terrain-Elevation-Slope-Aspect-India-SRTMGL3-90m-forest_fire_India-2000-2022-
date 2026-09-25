"""
Recalculation R6 -- terrain from the SRTMGL3 (3 arc-second) mosaic.

* Elevation: 90 m -> NDVI grid by area averaging (historical convention).
* Slope: Horn (1981) 3x3 (historical) and Zevenbergen & Thorne (1987) 2nd-order
  central difference (sensitivity), both at native 90 m with latitude-dependent dx,
  then area-averaged to the NDVI grid. Aspect: circular mean of Horn aspect.
* Scale dependence of slope (relevant to Biswas et al., who rasterised to 0.25 deg):
  slope computed on the DEM first averaged to 1 km and to 0.25 deg.
* Negative-elevation artefact: location/extent of 1 km pixels < -5 m.
* Independent DEM cross-check: GMTED2010 mean-elevation tile (30N-50N, 90E-120E -- only
  NE India overlaps) vs SRTM-derived elevation on the NDVI grid.
"""
import os
import time

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from rasterio.windows import Window

from audit_common import P, RES, provenance, dump, ndvi_grid, india_geom, compare, save_tif

OUT = os.path.join(RES, "recalculated", "R6_terrain")
os.makedirs(OUT, exist_ok=True)
t0 = time.time()
rep = dict(provenance=provenance(__file__))
R = 6371008.8
DEM = os.path.join(P["terrain_out"], "India_SRTMGL3_DEM_mosaic.tif")
g = ndvi_grid(); H, W = g["shape"]

with rasterio.open(DEM) as src:
    tr, crs, (Hd, Wd), nod = src.transform, src.crs, src.shape, src.nodata
    rep["dem"] = dict(shape=[Hd, Wd], res_deg=tr.a, nodata=nod, dtype=src.dtypes[0])
    land = rasterize([(india_geom("state"), 1)], out_shape=(Hd, Wd), transform=tr, fill=0, dtype=np.uint8).astype(bool)
    dy = np.pi / 180 * R * tr.a
    elev = np.full((Hd, Wd), np.nan, np.float32)
    s_horn = np.full((Hd, Wd), np.nan, np.float32)
    s_zt = np.full((Hd, Wd), np.nan, np.float32)
    sinA = np.full((Hd, Wd), np.nan, np.float32); cosA = np.full((Hd, Wd), np.nan, np.float32)
    TILE = 2048
    for r0 in range(0, Hd, TILE):
        r1 = min(r0 + TILE, Hd)
        a0, a1 = max(r0 - 1, 0), min(r1 + 1, Hd)
        z = src.read(1, window=Window(0, a0, Wd, a1 - a0)).astype(np.float32)
        lm = land[a0:a1]
        z = np.where(lm, z, np.nan)            # ocean / outside India -> NaN (0 is ambiguous: sea level vs void)
        zp = np.pad(z, ((1 if a0 == r0 else 0, 1 if a1 == r1 else 0), (1, 1)), mode="edge")
        lat = tr.f + (np.arange(a0, a1) + 0.5) * tr.e
        if a0 == r0:
            lat = np.r_[lat[0], lat]
        if a1 == r1:
            lat = np.r_[lat, lat[-1]]
        dx = (np.pi / 180 * R * tr.a * np.cos(np.radians(lat)))[1:-1, None]
        A, B, C = zp[:-2, :-2], zp[:-2, 1:-1], zp[:-2, 2:]
        D_, E_, F_ = zp[1:-1, :-2], zp[1:-1, 1:-1], zp[1:-1, 2:]
        G, Hh, I = zp[2:, :-2], zp[2:, 1:-1], zp[2:, 2:]
        dzdx = ((C + 2 * F_ + I) - (A + 2 * D_ + G)) / (8 * dx)
        dzdy = ((G + 2 * Hh + I) - (A + 2 * B + C)) / (8 * dy)
        sh = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
        asp = np.degrees(np.arctan2(dzdy, -dzdx))
        asp = np.where(asp < 0, 90 - asp, np.where(asp > 90, 360 - asp + 90, 90 - asp))
        flat = (np.abs(dzdx) < 1e-6) & (np.abs(dzdy) < 1e-6)
        zx, zy = (F_ - D_) / (2 * dx), (Hh - B) / (2 * dy)
        sz = np.degrees(np.arctan(np.hypot(zx, zy)))
        sl = slice(0, r1 - r0)  # interior row 0 of zp always maps to absolute row r0
        elev[r0:r1] = E_[sl]; s_horn[r0:r1] = sh[sl]; s_zt[r0:r1] = sz[sl]
        ar = np.radians(np.where(flat, np.nan, asp))[sl]
        sinA[r0:r1] = np.sin(ar); cosA[r0:r1] = np.cos(ar)
        print("rows", r1, "/", Hd, round(time.time() - t0), "s", flush=True)
del land


def agg(a, dst_tr=g["transform"], shape=(H, W)):
    d = np.full(shape, np.nan, np.float32)
    reproject(a, d, src_transform=tr, src_crs=crs, dst_transform=dst_tr, dst_crs=g["crs"], src_nodata=np.nan,
              dst_nodata=np.nan, resampling=Resampling.average)
    return d


E1 = agg(elev); SH1 = agg(s_horn); SZ1 = agg(s_zt)
A1 = (np.degrees(np.arctan2(agg(sinA), agg(cosA))) + 360) % 360
rep["native_stats"] = dict(elev_min=float(np.nanmin(elev)), elev_max=float(np.nanmax(elev)),
                           n_native_below_minus10m=int(np.nansum(elev < -10)),
                           slope_horn_mean=float(np.nanmean(s_horn)), slope_zt_mean=float(np.nanmean(s_zt)),
                           slope_horn_max=float(np.nanmax(s_horn)))
del s_horn, s_zt, sinA, cosA
# slope from coarse DEMs (scale dependence): 1 km and 0.25 deg
def slope_of(z, a_deg, lat_rows):
    dxx = (np.pi / 180 * R * a_deg * np.cos(np.radians(lat_rows)))[:, None]
    dyy = np.pi / 180 * R * a_deg
    zp = np.pad(z, 1, mode="edge")
    dzdx = ((zp[:-2, 2:] + 2 * zp[1:-1, 2:] + zp[2:, 2:]) - (zp[:-2, :-2] + 2 * zp[1:-1, :-2] + zp[2:, :-2])) / (8 * dxx)
    dzdy = ((zp[2:, :-2] + 2 * zp[2:, 1:-1] + zp[2:, 2:]) - (zp[:-2, :-2] + 2 * zp[:-2, 1:-1] + zp[:-2, 2:])) / (8 * dyy)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
lat1 = g["transform"].f + (np.arange(H) + 0.5) * g["transform"].e
S_from1km = slope_of(E1, g["transform"].a, lat1)
from rasterio.transform import from_origin
tr25 = from_origin(68.0, 37.5, 0.25, 0.25); H25, W25 = 124, 120
E25 = agg(elev, tr25, (H25, W25))
lat25 = 37.5 - (np.arange(H25) + 0.5) * 0.25
S25 = slope_of(E25, 0.25, lat25)
S25_on1 = np.full((H, W), np.nan, np.float32)
reproject(S25, S25_on1, src_transform=tr25, src_crs="EPSG:4326", dst_transform=g["transform"], dst_crs=g["crs"],
          src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest)
del elev

pq = pd.read_parquet(P["parquet"], columns=["lon", "lat", "terrain_elevation", "terrain_slope", "terrain_aspect", "fire_ever"])
rr = np.floor((pq.lat.values - g["transform"].f) / g["transform"].e).astype(int)
cc = np.floor((pq.lon.values - g["transform"].c) / g["transform"].a).astype(int)
v = lambda a: a[rr, cc]
rep["parquet_comparison"] = [compare(v(E1), pq.terrain_elevation.values, name="elevation"),
                             compare(v(SH1), pq.terrain_slope.values, name="slope Horn"),
                             compare(v(A1), pq.terrain_aspect.values, name="aspect (circular mean)")]
from sklearn.metrics import roc_auc_score
y = pq.fire_ever.values
def auc(x):
    ok = np.isfinite(x); a = roc_auc_score(y[ok], x[ok]); return float(a)
rep["slope_algorithm_sensitivity"] = dict(
    corr_horn_vs_zt=float(np.corrcoef(np.nan_to_num(v(SH1)), np.nan_to_num(v(SZ1)))[0, 1]),
    mean_horn=float(np.nanmean(v(SH1))), mean_zt=float(np.nanmean(v(SZ1))),
    mean_abs_diff_deg=float(np.nanmean(np.abs(v(SH1) - v(SZ1)))),
    single_feature_auc_horn=auc(v(SH1)), single_feature_auc_zt=auc(v(SZ1)),
    mean_slope_from_1km_dem=float(np.nanmean(v(S_from1km))), single_feature_auc_slope_from_1km_dem=auc(v(S_from1km)),
    mean_slope_from_025deg_dem=float(np.nanmean(v(S25_on1))), single_feature_auc_slope_from_025deg_dem=auc(v(S25_on1)),
    corr_90m_horn_vs_025deg=float(pd.Series(v(SH1)).corr(pd.Series(v(S25_on1)))))
neg = np.where(np.isfinite(E1) & (E1 < -5))
rep["negative_elevation_artifact"] = dict(
    n_1km_pixels_below_minus5m=int(len(neg[0])), min_1km=float(np.nanmin(E1)),
    locations=[dict(lat=float(g["transform"].f + (r + .5) * g["transform"].e), lon=float(g["transform"].c + (c_ + .5) * g["transform"].a),
                    elev=float(E1[r, c_])) for r, c_ in list(zip(*neg))[:25]])
# GMTED2010 cross-check over overlap
gm = os.path.join(P["osm_dir"], "30n090e_20101117_gmted_mea075.tif")
if os.path.exists(gm):
    with rasterio.open(gm) as s:
        Gd = np.full((H, W), np.nan, np.float32)
        z = s.read(1).astype(np.float32)
        if s.nodata is not None:
            z[z == s.nodata] = np.nan
        z[z <= -32768] = np.nan
        reproject(z, Gd, src_transform=s.transform, src_crs=s.crs, dst_transform=g["transform"], dst_crs=g["crs"],
                  src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.average)
    rep["gmted_crosscheck"] = compare(v(E1), v(Gd), name="SRTM-derived vs GMTED2010 mean (NE India overlap only)")
for name, a in (("elevation", E1), ("slope_horn", SH1), ("slope_zt", SZ1), ("aspect", A1), ("slope_from_025deg_dem", S25_on1)):
    save_tif(a, os.path.join(OUT, f"{name}_ndvi_grid.tif"))
pd.DataFrame({"elevation": v(E1), "slope_horn": v(SH1), "slope_zt": v(SZ1), "aspect": v(A1),
              "slope_from_1km_dem": v(S_from1km), "slope_from_025deg_dem": v(S25_on1)}).to_parquet(
    os.path.join(OUT, "terrain_pixels.parquet"), index=False)
rep["runtime_sec"] = time.time() - t0
dump(rep, os.path.join(OUT, "R6_report.json"))
print(rep["parquet_comparison"]); print(rep["slope_algorithm_sensitivity"]); print(rep["negative_elevation_artifact"]["n_1km_pixels_below_minus5m"], rep["negative_elevation_artifact"]["locations"][:3])
