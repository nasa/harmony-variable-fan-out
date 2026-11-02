# Command line examples


This directory contains a sample input catalog that points to an [EEDTEST granule](https://harmony.uat.earthdata.nasa.gov/service-results/harmony-uat-eedtest-data/C1256108792-EEDTEST/SMAP_L4_SM_lmc_00000000T000000_Vv6030_001.h5) for SPL4SMLM data that has 39 net2cog processible variables in it.  The following requests invoke the service from the commandline demonstrating the mechanism used by the service.

## Directory structure

```text
example/
├── 📄 fan-out-message.json                    Harmony message with no variables
├── 📄 explicit-variable-message.json          Harmony message with two variables
├── 📁 input-catalog/                          Example STAC catalog
│   ├── 📄 catalog0.json                       Catalog linking to the one granule item
│   └── 📄 granule_G1256108793-EEDTEST.json    Item whose data asset is the SPL4SMLM granule
├── 📁 fanned-out-output/                      (created by the fan-out example) one catalogN.json per variable
└── 📁 explicit-variable-output/               (created by the explicit example) the unchanged catalog
```

Run the commands below from the root of the repository, with a UAT bearer token in `UAT_BEARER`.
*Note: Running these commands will write a copy of your UAT_BEARER token into the output directory's message.json*

## Fan Out Example

To make a URL request to Harmony UAT that demonstrates fan out behavior you would use:

`https://harmony.uat.earthdata.nasa.gov/C1256108792-EEDTEST/ogc-api-coverages/1.0.0/collections/parameter_vars/coverage/rangeset?forceAsync=true&label=net2cog-test&granuleId=G1256108793-EEDTEST&format=image%2Ftiff&maxResults=1&variable=all`

Running the command below will invoke the adapter the same way locally.  It uses a message with no input variables and the sample catalog. The output catalogs are written to `fanned-out-output`


```shell
SHARED_SECRET_KEY= STAGING_BUCKET=unused STAGING_PATH=unused \
uv run python -m variable_fan_out \
  --harmony-action invoke \
  --harmony-input "$(jq -c --arg t "$UAT_BEARER" '.accessToken = $t' example/fan-out-message.json)" \
  --harmony-sources example/input-catalog/catalog0.json \
  --harmony-metadata-dir example/fanned-out-output
```

You can examine the output catalogs to see the amended property field with `"harmony:variable"` included.

You can see all of the catalogs with updated variables with:
```
grep -r '"harmony:variable"' example/fanned-out-output
```


## Explicit Variables

A request that contains one or more variables explicitly requested will not fan out but pass through unchanged. A Harmony URL request would look like:

`https://harmony.uat.earthdata.nasa.gov/C1256108792-EEDTEST/ogc-api-coverages/1.0.0/collections/parameter_vars/coverage/rangeset?forceAsync=true&label=net2cog-test&granuleId=G1256108793-EEDTEST&format=image%2Ftiff&maxResults=1&variable=%2FLand-Model-Constants_Data%2Fmwrtm_rghhmin&variable=cell_lon`

In this case we call the command on the same Catalog but our Harmony Message now contains explicit variables.


```shell
SHARED_SECRET_KEY= STAGING_BUCKET=unused STAGING_PATH=unused \
uv run python -m variable_fan_out \
  --harmony-action invoke \
  --harmony-input "$(jq -c --arg t "$UAT_BEARER" '.accessToken = $t' example/explicit-variable-message.json)" \
  --harmony-sources example/input-catalog/catalog0.json \
  --harmony-metadata-dir example/explicit-variable-output
```

You can see the output includes a loggging line:
`"message": "explicit variables requested; exiting without creating fan out catalogs"`

And if you look in the output directory, `example/explicit-variable-output`, you will see just the single Catalog.
