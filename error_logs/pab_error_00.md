  File "/home/xavier/miniconda3/envs/os_313/bin/pab", line 33, in <module>
    sys.exit(load_entry_point('pab', 'console_scripts', 'pab')())
             ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/mnt/tank/Oceanography/python/PAB/pab/pipeline.py", line 370, in main
    summary = run(store, config, stages=stages)
  File "/mnt/tank/Oceanography/python/PAB/pab/pipeline.py", line 313, in run
    summary[stage] = func(store, config, **kwargs)
                     ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/tank/Oceanography/python/PAB/pab/pipeline.py", line 198, in match
    return build_matchups(
        store, opener=opener, config=config.matchup, replace=config.replace
    )
  File "/mnt/tank/Oceanography/python/PAB/pab/matchup/engine.py", line 372, in build_matchups
    result = find_matchup(profile, candidates, opener=opener, config=config)
  File "/mnt/tank/Oceanography/python/PAB/pab/matchup/engine.py", line 182, in find_matchup
    ds = cloud.open_granule(g["source"], opener=opener)
  File "/mnt/tank/Oceanography/python/PAB/pab/pace/cloud.py", line 127, in open_granule
    return open_s3(source)
  File "/mnt/tank/Oceanography/python/PAB/pab/pace/cloud.py", line 62, in open_s3
    return read_datatree(fileset[0])
  File "/mnt/tank/Oceanography/python/PAB/pab/pace/cloud.py", line 86, in read_datatree
    "Rrs_unc": (dims, geo["Rrs_unc"].values),
                      ^^^^^^^^^^^^^^^^^^^^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/dataarray.py", line 797, in values
    return self.variable.values
           ^^^^^^^^^^^^^^^^^^^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/variable.py", line 556, in values
    return _as_array_or_item(self._data)
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/variable.py", line 336, in _as_array_or_item
    data = np.asarray(data)
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/indexing.py", line 577, in __array__
    return np.asarray(self.get_duck_array(), dtype=dtype, copy=copy)
                      ~~~~~~~~~~~~~~~~~~~^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/indexing.py", line 943, in get_duck_array
    duck_array = self.array.get_duck_array()
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/indexing.py", line 897, in get_duck_array
    return self.array.get_duck_array()
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/coding/common.py", line 80, in get_duck_array
    return self.func(self.array.get_duck_array())
                     ~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/coding/common.py", line 80, in get_duck_array
    return self.func(self.array.get_duck_array())
                     ~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/indexing.py", line 737, in get_duck_array
    array = self.array[self.key]
            ~~~~~~~~~~^^^^^^^^^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/backends/h5netcdf_.py", line 64, in __getitem__
    return indexing.explicit_indexing_adapter(
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        key, self.shape, indexing.IndexingSupport.OUTER_1VECTOR, self._getitem
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/core/indexing.py", line 1129, in explicit_indexing_adapter
    result = raw_indexing_method(raw_key.tuple)
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/xarray/backends/h5netcdf_.py", line 71, in _getitem
    return array[key]
           ~~~~~^^^^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/h5netcdf/core.py", line 558, in __getitem__
    return h5ds[key]
           ~~~~^^^^^
  File "h5py/_objects.pyx", line 54, in h5py._objects.with_phil.wrapper
  File "h5py/_objects.pyx", line 55, in h5py._objects.with_phil.wrapper
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/h5py/_hl/dataset.py", line 802, in __getitem__
    return self._fast_reader.read(args)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "h5py/_selector.pyx", line 376, in h5py._selector.Reader.read
  File "h5py/h5fd.pyx", line 162, in h5py.h5fd.H5FD_fileobj_read
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/fsspec/spec.py", line 2129, in readinto
    data = self.read(out.nbytes)
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/fsspec/spec.py", line 2111, in read
    out = self.cache._fetch(self.loc, self.loc + length)
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/fsspec/caching.py", line 560, in _fetch
    new = self.fetcher(self.end, bend)
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/fsspec/asyn.py", line 118, in wrapper
    return sync(self.loop, func, *args, **kwargs)
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/fsspec/asyn.py", line 103, in sync
    raise return_result
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/fsspec/asyn.py", line 56, in _runner
    result[0] = await coro
                ^^^^^^^^^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/fsspec/implementations/http.py", line 692, in async_fetch_range
    r.raise_for_status()
    ~~~~~~~~~~~~~~~~~~^^
  File "/home/xavier/miniconda3/envs/os_313/lib/python3.13/site-packages/aiohttp/client_reqrep.py", line 629, in raise_for_status
    raise ClientResponseError(
    ...<5 lines>...
    )

