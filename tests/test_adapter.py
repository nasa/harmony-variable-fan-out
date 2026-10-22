"""Tests for VariableFanOutAdapter.invoke."""

from datetime import UTC, datetime
from unittest.mock import patch

import numpy as np
import pytest
import xarray as xr
from harmony_service_lib.message import Message
from pystac import Asset, Catalog, Item

from variable_fan_out.adapter import VariableFanOutAdapter


@pytest.fixture
def netcdf_file(tmp_path):
    """A netCDF file with two variables net2cog will find."""
    path = tmp_path / "variable_file.nc"
    xr.Dataset(
        {
            "var1": (("lat", "lon"), np.zeros((10, 20))),
            "var2": (("lat", "lon"), np.zeros((10, 20))),
            "ungriddable-var": (("time"), np.zeros((10,))),
        }
    ).to_netcdf(path)
    return str(path)


@pytest.fixture
def no_spatial_dims_file(tmp_path):
    """A netCDF file that net2cog finds no variables in."""
    path = tmp_path / "no_spatial_dims.nc"
    xr.Dataset({"var3": (("a", "b"), np.zeros((10, 20)))}).to_netcdf(path)
    return str(path)


def make_message(variables=None):
    """Return a harmony message who's source may or may not have explicit variables."""
    source = {
        "collection": "C123456789-TEST",
        "shortName": "Testname",
        "versionId": "1",
    }
    if variables:
        source["variables"] = [
            {"id": f"Var{i}", "name": v, "fullPath": v} for i, v in enumerate(variables)
        ]
    return Message({"sources": [source]})


def make_catalog(item_ids):
    catalog = Catalog(id="input-catalog", description="test input catalog")
    for item_id in item_ids:
        item = Item(
            id=item_id,
            geometry=None,
            bbox=None,
            datetime=datetime.now(tz=UTC),
            properties={},
        )
        item.add_asset(
            "data", Asset(href=f"https://example.com/{item_id}.nc", roles=["data"])
        )
        catalog.add_item(item)
    return catalog


def test_fans_out_one_catalog_per_variable(netcdf_file):

    catalog = make_catalog(["granule"])

    with patch("variable_fan_out.adapter.download", return_value=netcdf_file):
        _, output_catalogs = VariableFanOutAdapter(make_message(), catalog).invoke()

    for c, expected_var in zip(output_catalogs, ["/var1", "/var2"], strict=True):
        items = list(c.get_items())
        assert len(items) == 1
        assert items[0].properties["harmony:variable"] == expected_var

    # input catalog unchanged.
    assert "harmony:variable" not in next(catalog.get_items("granule")).properties


def test_explicit_variables_return_input_catalog():
    catalog = make_catalog(["granule"])
    message_with_explicit_vars = make_message(variables=["var4", "var5"])

    with patch("variable_fan_out.adapter.download") as download:
        _, output_catalog = VariableFanOutAdapter(
            message_with_explicit_vars, catalog
        ).invoke()

    assert output_catalog is catalog
    download.assert_not_called()


def test_disabled_env_returns_input_catalog(monkeypatch):
    monkeypatch.setenv("VARIABLE_FAN_OUT_DISABLED", "true")
    catalog = make_catalog(["granule"])

    with patch("variable_fan_out.adapter.download") as download:
        _, output_catalog = VariableFanOutAdapter(make_message(), catalog).invoke()

    assert output_catalog is catalog
    download.assert_not_called()


def test_download_error_retuns_input_catalog():
    catalog = make_catalog(["granule"])

    with patch("variable_fan_out.adapter.download", side_effect=Exception("Forbidden")):
        _, output = VariableFanOutAdapter(make_message(), catalog).invoke()

    assert output is catalog


def test_item_without_variables_is_passed_through_alone(
    netcdf_file, no_spatial_dims_file
):
    """Test a multi-item catalog with some that have discoverable variables and one that does not.

    This is an unlikely scenario, but we don't want to drop the item without
    discoverable variables, it should be passed to net2cog and we let it fail
    there.

    """
    catalog = make_catalog(["has-vars", "no-vars", "has-vars2"])

    def fake_download(href, *args, **kwargs):
        return no_spatial_dims_file if "no-vars" in href else netcdf_file

    with patch("variable_fan_out.adapter.download", side_effect=fake_download):
        _, output_catalogs = VariableFanOutAdapter(make_message(), catalog).invoke()

    # We're checking the ids of the Items to see which catalogs are
    # returned. The Items with variables are duplicated for each var, the other
    # is not.
    expected_ids = [
        "has-vars-var-1",
        "has-vars-var-2",
        "no-vars",
        "has-vars2-var-1",
        "has-vars2-var-2",
    ]
    for c, expected_id in zip(output_catalogs, expected_ids, strict=True):
        items = list(c.get_items())
        assert len(items) == 1
        assert items[0].id == expected_id

    # assert the no_vars catalog (the third) wasn't amended.
    no_vars_item = next(output_catalogs[2].get_items())
    assert "harmony:variable" not in no_vars_item.properties
