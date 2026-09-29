"""End-to-end TEST-only GRIB + NetCDF mechanics fixture; not scientific data."""
from datetime import datetime, timezone
import numpy as np
import pytest, yaml

eccodes=pytest.importorskip("eccodes")
netCDF4=pytest.importorskip("netCDF4")
from ml.research.strikecast.src.ingestion.provider_adapters import ERA5Provider, LISProvider
from strikecast_core.data.real_pipeline import (build_era5_grid, build_lis_observation_grid,
    build_paired_dataset, align_features_to_prediction_time, split_and_normalize, DataLeakageError,
    CanonicalPairedDataset, train_canonical_conv_lstm, canonicalize_lis_records, TargetPolicy,
    TargetPolicyPending, InferenceFeatureAdapter, FeatureCompatibilityError, SERVED_FEATURE_NAMES)

FIXTURE_POLICY=TargetPolicy(frozenset({0,2}),"fixture-explicit-v1",approved=True)
TEST_APPROVED_POLICY=FIXTURE_POLICY


def _tiny_schema(path):
    value={"schema_version":"fixture-schema-v1","grid":{"north":8.5,"south":8,"west":72,"east":73},
      "temporal":{"cadence_minutes":60,"sequence_length":1,"forecast_horizon_steps":1},
      "sources":{"era5_single_levels":{"fields":[{"id":"u10","grib_short_name":"10u","units":"m s-1"}]},
                "era5_pressure_levels":{"levels_hpa":[],"fields":[]}},
      "target":{"schema_version":"fixture-target-v1"}}
    path.write_text(yaml.safe_dump(value),encoding="utf-8"); return value


def _grib(path):
    h=eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        for k,v in {"Ni":2,"Nj":1,"latitudeOfFirstGridPointInDegrees":8.25,
          "longitudeOfFirstGridPointInDegrees":72.25,"latitudeOfLastGridPointInDegrees":8.25,
          "longitudeOfLastGridPointInDegrees":72.75,"iDirectionIncrementInDegrees":0.5,
          "jDirectionIncrementInDegrees":0.5,"shortName":"10u","dataDate":19930101,"dataTime":0}.items():
            eccodes.codes_set(h,k,v)
        eccodes.codes_set_values(h,[4.,6.])
        with path.open("wb") as f: eccodes.codes_write(h,f)
    finally: eccodes.codes_release(h)


def _lis(path, *, partial=False, event_tai=3700.):
    with netCDF4.Dataset(path,"w",format="NETCDF4") as ds:
        ds.createDimension("view",1 if partial else 2); ds.createDimension("event",1)
        ds.createVariable("orbit_summary_UTC_start",str,())[()]="1993-01-01T00:00:00Z"
        ds.createVariable("orbit_summary_TAI93_start","f8",())[()]=0.
        values={"viewtime_lat":([8.25] if partial else [8.25,8.25],"f4"),
          "viewtime_lon":([72.25] if partial else [72.25,72.75],"f4"),
          "viewtime_TAI93_start":([3600.] if partial else [3600.,3600.],"f8"),
          "viewtime_TAI93_end":([5000.] if partial else [7200.,7200.],"f8"),
          "viewtime_effective_obs":([1400.] if partial else [3600.,3600.],"f4"),
          "viewtime_alert_flag":([0] if partial else [0,2],"u1"),
          "lightning_event_lat":([8.25],"f4"),"lightning_event_lon":([72.25],"f4"),
          "lightning_event_TAI93_time":([event_tai],"f8"),"lightning_event_alert_flag":([0],"u1")}
        for name,(array,dtype) in values.items():
            dim="view" if name.startswith("viewtime_") else "event"
            var=ds.createVariable(name,dtype,(dim,)); var[:]=array
            if "alert_flag" in name: var.comment="fixture flag"


def test_real_format_decode_to_pair_and_dataset(tmp_path):
    schema_path=tmp_path/"schema.yaml"; schema=_tiny_schema(schema_path)
    gp=tmp_path/"tiny.grib"; _grib(gp)
    lp=tmp_path/"tiny.nc"; _lis(lp)
    g=ERA5Provider.decode(None,gp); l=LISProvider.decode(None,lp)
    canonical_lis=canonicalize_lis_records(l)
    assert canonical_lis["events"][0]["timestamp"]==datetime(1993,1,1,tzinfo=timezone.utc)+__import__('datetime').timedelta(seconds=3700)
    assert canonical_lis["viewtime"][0]["source_hash"]==l["source_sha256"]
    assert len(g["records"])==1 and g["records"][0]["short_name"]=="10u"
    grid=build_era5_grid(g["records"],schema,resolution=.5)
    assert grid["tensor"].shape==(1,1,1,2) and grid["tensor"][0,0,0].tolist()==[4.,6.]
    t=datetime(1993,1,1,tzinfo=timezone.utc)
    target=build_lis_observation_grid([l],t.replace(hour=1),t.replace(hour=2),grid["latitude"],grid["longitude"],policy=FIXTURE_POLICY)
    assert target["target"].tolist()==[[1.,0.]] and target["observation_mask"].tolist()==[[True,True]]
    paired=build_paired_dataset(g["records"],[l],schema_path=schema_path,sequence_length=1,resolution=.5,target_policy=FIXTURE_POLICY)
    assert paired.manifest["status"]=="READY" and paired.counts["positive_cells"]==1
    assert paired.counts["negative_cells"]==1 and paired.samples[0]["feature_tensor"].shape==(1,1,1,2)
    assert paired.samples[0]["source_hashes"] and paired.manifest["target_interval_semantics"].startswith("[")


def test_unknown_and_partial_coverage_never_become_negative(tmp_path):
    p=tmp_path/"tiny.nc"; _lis(p,partial=True); l=LISProvider.decode(None,p)
    lat=np.asarray([8.25]); lon=np.asarray([72.25,72.75]); t=datetime(1993,1,1,tzinfo=timezone.utc)
    target=build_lis_observation_grid([l],t+__import__('datetime').timedelta(hours=1),t+__import__('datetime').timedelta(hours=2),lat,lon,policy=FIXTURE_POLICY)
    assert target["target"].tolist()==[[1.,0.]]
    assert target["observation_mask"].tolist()==[[True,False]]


def test_event_at_target_end_is_outside_half_open_interval(tmp_path):
    p=tmp_path/"end.nc"; _lis(p,partial=True,event_tai=7200.); l=LISProvider.decode(None,p)
    t=datetime(1993,1,1,tzinfo=timezone.utc)
    target=build_lis_observation_grid([l],t+__import__('datetime').timedelta(hours=1),t+__import__('datetime').timedelta(hours=2),np.asarray([8.25]),np.asarray([72.25,72.75]),policy=FIXTURE_POLICY)
    assert not target["observation_mask"].any()
    assert not target["target"].any()


def test_target_policy_pending_fails_closed():
    with pytest.raises(TargetPolicyPending,match="PENDING_APPROVAL"):
        build_lis_observation_grid([],datetime.now(timezone.utc),datetime.now(timezone.utc)+__import__('datetime').timedelta(hours=1),np.asarray([8.25]),np.asarray([72.25]))


def test_inference_adapter_requires_explicit_complete_research_mapping():
    mapping={name:name for name in SERVED_FEATURE_NAMES}
    adapter=InferenceFeatureAdapter(mapping)
    x=np.zeros((2,6,8,3,3),dtype=np.float32)
    research_names=["t2m","relative_humidity@1000hPa","msl","u10","tcc","tp","sp","blh"]
    with pytest.raises(FeatureCompatibilityError,match="cannot be derived"):
        adapter.adapt(x,research_names,feature_schema_version="strikecast-era5-feature-schema-v1",normalization_version="point-feature-minmax-v1")
    with pytest.raises(FeatureCompatibilityError,match="expected"):
        adapter.adapt(np.zeros((2,5,8,3,3)),list(SERVED_FEATURE_NAMES),feature_schema_version="strikecast-era5-feature-schema-v1",normalization_version="point-feature-minmax-v1")


def test_inference_adapter_valid_mapping_and_tensor_validation():
    names=list(SERVED_FEATURE_NAMES); adapter=InferenceFeatureAdapter({n:n for n in names})
    x=np.zeros((1,6,8,3,3),dtype=np.float32)
    y=adapter.adapt(x,names,feature_schema_version="strikecast-era5-feature-schema-v1",normalization_version="point-feature-minmax-v1")
    assert y.shape==(1,6,8,3,3)
    with pytest.raises(FeatureCompatibilityError,match="schema"):
        adapter.adapt(x,names,feature_schema_version="wrong",normalization_version="point-feature-minmax-v1")
    with pytest.raises(FeatureCompatibilityError,match="normalization"):
        adapter.adapt(x,names,feature_schema_version="strikecast-era5-feature-schema-v1",normalization_version="wrong")
    for malformed in (np.zeros((1,6,7,3,3),dtype=np.float32),np.zeros((1,6,8,2,3),dtype=np.float32)):
        with pytest.raises(FeatureCompatibilityError,match="expected"):
            adapter.adapt(malformed,names,feature_schema_version="strikecast-era5-feature-schema-v1",normalization_version="point-feature-minmax-v1")
    with pytest.raises(FeatureCompatibilityError,match="research normalization"):
        adapter.adapt(x,names,feature_schema_version="strikecast-era5-feature-schema-v1",normalization_version="train_only_zscore_v1")
    for value in (np.nan,np.inf):
        bad=x.copy(); bad[0,0,0,0,0]=value
        with pytest.raises(FeatureCompatibilityError,match="finite"):
            adapter.adapt(bad,names,feature_schema_version="strikecast-era5-feature-schema-v1",normalization_version="point-feature-minmax-v1")


def test_lis_index_exact_and_time_range_lookup(tmp_path):
    p=tmp_path/"indexed.nc"; _lis(p); l=LISProvider.decode(None,p)
    from strikecast_core.data.real_pipeline import LISIndex
    index=LISIndex([l],np.asarray([8.25]),np.asarray([72.25,72.75]),.5)
    t=datetime(1993,1,1,tzinfo=timezone.utc)+__import__('datetime').timedelta(seconds=3700)
    assert len(index.query(t,(0,0)))==1
    assert len(index.query_time_range(t-__import__('datetime').timedelta(seconds=1),t+__import__('datetime').timedelta(seconds=1),(0,0)))==1
    assert index.granules_for(t,t+__import__('datetime').timedelta(minutes=1))==[l]
    for _ in range(100): index.query(t,(0,0))
    assert index.lookup_calls==101 and index.records_returned==101


def test_persistence_uses_latest_prior_valid_grid_and_never_future():
    from strikecast_core.data.real_pipeline import PersistenceBaseline
    from datetime import timedelta
    base=datetime(2024,1,1,tzinfo=timezone.utc)
    def row(i,observed=True):
        t=base+timedelta(hours=i)
        return {"sample_id":f"T{i}","prediction_time":t,"target_interval_utc":[t+timedelta(hours=1),t+timedelta(hours=2)],
                "target":np.asarray([[i%2]],dtype=np.float32),"observation_mask":np.asarray([[observed]])}
    t1=row(1); t2=row(2,False); t3=row(4); t4=row(5)
    result=PersistenceBaseline.for_sample(t3,[t1,t2,t4])
    assert result["status"]=="READY" and result["source_sample_id"]=="T1"
    assert PersistenceBaseline.for_sample(row(0),[t1])["status"]=="NOT_APPLICABLE"


def test_pipeline_limits_fail_closed():
    from strikecast_core.data.real_pipeline import PipelineLimits
    limits=PipelineLimits(max_grid_cells=1)
    schema={"schema_version":"s","grid":{"north":9,"south":8,"west":72,"east":73},"sources":{"era5_single_levels":{"fields":[]},"era5_pressure_levels":{"levels_hpa":[],"fields":[]}}}
    with pytest.raises(ValueError,match="MAX_GRID_CELLS"):
        build_era5_grid([],schema,resolution=.5,limits=limits)
    with pytest.raises(ValueError,match="MAX_SEQUENCE_LENGTH"):
        align_features_to_prediction_time({"times":[],"tensor":np.zeros((0,1,1,1)),"mask":np.zeros((0,1,1,1),bool)},datetime.now(timezone.utc),25)


def test_spatial_mapping_refuses_outside_points():
    from strikecast_core.data.real_pipeline import align_spatial_cell
    assert align_spatial_cell(8.25,72.25,np.asarray([8.25]),np.asarray([72.25]),.5)==(0,0)
    assert align_spatial_cell(8.75,72.25,np.asarray([8.25]),np.asarray([72.25]),.5) is None


def test_temporal_alignment_refuses_future_or_missing_input():
    t=datetime(2024,1,1,tzinfo=timezone.utc)
    data={"times":[t,t.replace(hour=1)],"tensor":np.zeros((2,1,1,1)),"mask":np.ones((2,1,1,1),bool)}
    with pytest.raises(Exception,match="missing"):
        align_features_to_prediction_time(data,t.replace(hour=1),3)
    _,_,used=align_features_to_prediction_time({**data,"times":[t,t.replace(hour=2)]},t,1)
    assert used==[t] and max(used)<=t


def test_split_is_chronological_disjoint_and_normalizer_uses_train_only():
    rows=[]; epoch=datetime(2024,1,1,tzinfo=timezone.utc)
    for i in range(10):
        t=epoch+__import__('datetime').timedelta(hours=i)
        rows.append({"sample_id":str(i),"prediction_time":t,"input_times":[t],
          "target_interval_utc":[t+__import__('datetime').timedelta(hours=1),t+__import__('datetime').timedelta(hours=2)],
          "feature_tensor":np.asarray([[[[float(i)]]]],dtype=np.float32),"feature_mask":np.ones((1,1,1,1),bool),
          "target":np.asarray([[i%2]],dtype=np.float32),"observation_mask":np.ones((1,1),bool)})
    d=CanonicalPairedDataset(rows,np.asarray([8.25]),np.asarray([72.25]),["x"],"f1","t1",{"dataset_version":"fixture"})
    prepared=split_and_normalize(d)
    splits=prepared["splits"]
    assert all(splits[k] for k in ("train","validation","test"))
    max_train=max(s["target_interval_utc"][1] for s in splits["train"])
    min_val=min(s["input_times"][0] for s in splits["validation"])
    max_val=max(s["target_interval_utc"][1] for s in splits["validation"])
    min_test=min(s["input_times"][0] for s in splits["test"])
    assert max_train<=min_val and max_val<=min_test
    expected=np.mean([float(s["sample_id"]) for s in splits["train"]])
    assert prepared["normalization"]["feature_stats"]["x"]["mean"]==pytest.approx(expected)


def test_fixture_training_evaluation_calibration_candidate_artifact(tmp_path):
    rows=[]; epoch=datetime(2024,1,1,tzinfo=timezone.utc)
    for i in range(140):
        t=epoch+__import__('datetime').timedelta(hours=i)
        rows.append({"sample_id":str(i),"prediction_time":t,"input_times":[t],
          "target_interval_utc":[t+__import__('datetime').timedelta(hours=1),t+__import__('datetime').timedelta(hours=2)],
          "feature_tensor":np.asarray([[[[float(i%3)]]]],dtype=np.float32),"feature_mask":np.ones((1,1,1,1),bool),
          "target":np.asarray([[i%2]],dtype=np.float32),"observation_mask":np.ones((1,1),bool)})
    d=CanonicalPairedDataset(rows,np.asarray([8.25]),np.asarray([72.25]),["x"],"fixture-feature-v1","fixture-target-v1",
      {"dataset_version":"fixture-mechanics-v1","target_interval_semantics":"half-open fixture","feature_units":{"x":"1"}})
    result=train_canonical_conv_lstm(d,training_config={"seed":3,"batch_size":16,"max_epochs":2,"learning_rate":.01,
      "optimizer":"adam","scheduler":"none","conv_hidden_dims":[2],"conv_kernel_size":3,"early_stopping_patience":2},output_root=tmp_path/"candidate")
    assert result["status"]=="CANDIDATE_VALIDATED_NOT_PROMOTED"
    assert result["registry_validation"]["status"]=="VALID_CANDIDATE"
    assert result["metrics"]["split"]=="test" if "split" in result["metrics"] else result["metrics"]["population"]=="observed target-mask cells only"
    assert result["calibration"]["fit_split"]=="validation"
